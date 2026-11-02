"""Busca semântica: filtros duros (restrição, preço, tempo, zona) e cosseno no índice."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sklearn.metrics.pairwise import cosine_similarity

from app.catalog import DishView, _catalog_hash
from app.config import BACKEND, settings
from app.embeddings import TfidfEmbedder, document_text, expand_query, fold
from app.services.sentence_embeddings import SentenceEmbedder
from app.services.vector_store import VectorStore

CACHE_DIR = BACKEND / ".cache"
KIND_HINTS = {
    "drink": r"suco|bebida|vitamina|milkshake|refrigerante|beber",
    "dessert": r"sobremesa|doce|acai|fruta",
    "side": r"batata|entrada|bruschetta|sunomono|acompanhamento",
}
FOOD_TERMS = (
    "poke", "sushi", "temaki", "pizza", "frango", "tapioca", "acai",
    "hamburguer", "burger", "smash", "salmao", "camarao", "picanha",
    "moqueca", "omelete", "cuscuz", "falafel", "quinoa", "penne", "massa",
)
FOOD_ALIASES = {
    "sushi": ("sushi", "japonesa", "temaki", "poke", "sashimi"),
    "poke": ("poke", "japonesa"),
    "pizza": ("pizza", "italiana"),
    "hamburguer": ("hamburguer", "burger", "smash"),
    "burger": ("hamburguer", "burger", "smash"),
    "smash": ("smash", "hamburguer", "burger"),
}


def _mentions_food(dish: DishView, folded_query: str) -> bool:
    mentioned = [term for term in FOOD_TERMS if term in folded_query]
    if not mentioned:
        return True
    blob = fold(f"{dish.name} {dish.description} {dish.category} {dish.cuisine}")
    for term in mentioned:
        options = FOOD_ALIASES.get(term, (term,))
        if any(option in blob for option in options):
            return True
    return False


class MenuIndex:
    def __init__(self) -> None:
        self.provider = settings.embedding_provider.strip().lower() or "minilm"
        self.model_name = settings.embedding_model
        self.embedder = TfidfEmbedder() if self.provider == "tfidf" else SentenceEmbedder(self.model_name)
        self.store = VectorStore(CACHE_DIR / "vectors")
        self.dishes: list[DishView] = []
        self.meta: dict = {
            "provider": self.provider,
            "model": self.model_name,
            "documents": 0,
            "dimensions": 0,
            "metric": "cosine",
            "built_at": None,
        }

    def build(self, dishes: list[DishView]) -> None:
        self.dishes = list(dishes)
        texts = [document_text(dish) for dish in self.dishes]
        if self.provider == "minilm":
            signature = f"{_catalog_hash()}:{self.model_name}:minilm"
            ids = [dish.id for dish in self.dishes]
            loaded = self.store.try_load(signature)
            if loaded is None or loaded.ids != ids:
                vectors = self.embedder.embed(texts)
                self.store.save(ids, vectors, signature)
            self.embedder.dimensions = int(self.store.vectors.shape[1]) if self.store.vectors.size else 0
            backend = self.store.backend
        else:
            self.embedder.fit(texts)
            backend = "tfidf"
        self.meta = {
            "provider": self.provider,
            "model": self.model_name if self.provider == "minilm" else "tfidf",
            "documents": len(self.dishes),
            "dimensions": self.embedder.dimensions,
            "metric": "cosine",
            "vector_backend": backend,
            "built_at": datetime.now(timezone.utc).isoformat(),
        }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / "index_meta.json").write_text(
            json.dumps(self.meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def search(
        self,
        query: str,
        *,
        max_price: float | None = None,
        max_prep: int | None = None,
        exclude_allergens: list[str] | None = None,
        diet: str | None = None,
        zone: str | None = None,
        exclude_ids: list[str] | None = None,
        limit: int = 4,
        relax: bool = True,
    ) -> tuple[list[DishView], str | None]:
        results = self._rank(
            query,
            max_price=max_price,
            max_prep=max_prep,
            exclude_allergens=exclude_allergens or [],
            diet=diet,
            zone=zone,
            exclude_ids=set(exclude_ids or []),
            limit=limit,
        )
        if results or not relax:
            return results, None
        if max_prep is not None:
            widened = self._rank(
                query,
                max_price=max_price,
                max_prep=None,
                exclude_allergens=exclude_allergens or [],
                diet=diet,
                zone=zone,
                exclude_ids=set(exclude_ids or []),
                limit=limit,
            )
            if widened:
                return widened, "prep"
        if max_price is not None:
            widened = self._rank(
                query,
                max_price=max_price + 15,
                max_prep=max_prep,
                exclude_allergens=exclude_allergens or [],
                diet=diet,
                zone=zone,
                exclude_ids=set(exclude_ids or []),
                limit=limit,
            )
            if widened:
                return widened, "price"
        return [], None

    def _rank(
        self,
        query: str,
        *,
        max_price: float | None,
        max_prep: int | None,
        exclude_allergens: list[str],
        diet: str | None,
        zone: str | None,
        exclude_ids: set[str],
        limit: int,
    ) -> list[DishView]:
        pool = [dish for dish in self.dishes if self._allows(
            dish,
            max_price=max_price,
            max_prep=max_prep,
            exclude_allergens=exclude_allergens,
            diet=diet,
            zone=zone,
            exclude_ids=exclude_ids,
        )]
        if not pool:
            return []
        if not query.strip():
            pool.sort(key=lambda dish: (-dish.rating, dish.prep_minutes, dish.price))
            return pool[:limit]

        folded_query = fold(expand_query(query))
        folded_original = fold(query)
        pool = [dish for dish in pool if _mentions_food(dish, folded_original)]
        if not pool:
            return []
        position = {dish.id: index for index, dish in enumerate(self.dishes)}
        if self.provider == "minilm":
            similarities = self.store.cosine(self.embedder.embed([expand_query(query)]))
        else:
            similarities = cosine_similarity(
                self.embedder.transform([expand_query(query)]),
                self.embedder.fitted_matrix,
            ).ravel()
        scored: list[tuple[float, DishView]] = []
        for dish in pool:
            similarity = float(similarities[position[dish.id]])
            scored.append((self._score(dish, similarity, folded_query), dish))
        scored.sort(key=lambda item: (-item[0], item[1].prep_minutes, item[1].price, item[1].name))
        return [dish for _score, dish in scored[:limit]]

    def _allows(
        self,
        dish: DishView,
        *,
        max_price: float | None,
        max_prep: int | None,
        exclude_allergens: list[str],
        diet: str | None,
        zone: str | None,
        exclude_ids: set[str],
    ) -> bool:
        if dish.id in exclude_ids:
            return False
        if max_price is not None and dish.price > max_price:
            return False
        if max_prep is not None and dish.prep_minutes > max_prep:
            return False
        if any(allergen in dish.allergens for allergen in exclude_allergens):
            return False
        if diet == "vegan" and "vegan" not in dish.tags:
            return False
        if diet == "vegetarian" and not ({"vegan", "vegetarian"} & set(dish.tags)):
            return False
        if zone and zone not in dish.zones:
            return False
        return True

    def _score(self, dish: DishView, similarity: float, folded_query: str) -> float:
        # Cosseno baixo significa que a frase quase só tem restrição.
        # Nesse caso o filtro já fez o trabalho e o perfil do prato desempata.
        semantic = similarity * (0.15 if similarity < 0.15 else 1.6)
        score = semantic
        if dish.kind == "main":
            score += 0.22 + min(dish.price, 48) / 160
        else:
            hinted = any(dish.kind == kind and re.search(pattern, folded_query) for kind, pattern in KIND_HINTS.items())
            score += 0.18 if hinted else -0.28
        score += (dish.rating - 4.5) * 0.5
        description = fold(dish.description)
        if re.search(r"rapid", folded_query) and re.search(r"rapid", description):
            score += 0.16
            score += max(0.0, 18 - dish.prep_minutes) / 90
        if "lactose" in folded_query and "lactose" in description:
            score += 0.16
        if "gluten" in folded_query and "gluten" in description:
            score += 0.16
        if re.search(r"vegan", folded_query) and ("vegan" in dish.tags or "vegan" in description):
            score += 0.14
        return score

    def find_named(self, message: str) -> DishView | None:
        folded = fold(message)
        matches = [dish for dish in self.dishes if fold(dish.name) in folded]
        if not matches:
            return None
        return max(matches, key=lambda dish: len(dish.name))
