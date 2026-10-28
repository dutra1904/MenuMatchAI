"""Texto do cardápio e embeddings locais.

O índice ativo é TF-IDF (vetor esparso + cosseno). O contrato fit/transform é o
ponto de troca para um provedor de embeddings de API, no mesmo pipeline.
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from typing import Protocol

from sklearn.feature_extraction.text import TfidfVectorizer

from app.catalog import DishView

STOPWORDS = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos",
    "e", "ou", "que", "em", "no", "na", "nos", "nas", "por", "para", "pra", "com",
    "sem", "ao", "aos", "eu", "me", "te", "se", "voce", "você", "quero", "queria",
    "gostaria", "algo", "algum", "alguma", "favor", "menos", "mais", "muito",
    "pouco", "bem", "so", "só", "tambem", "também", "ate", "até", "pelo", "pela",
    "como", "quando", "onde", "porque", "isso", "isto", "tem", "ter", "pode",
    "fazer", "ser", "esta", "está", "ja", "já", "ainda", "ne", "né",
}

EXPANSIONS = [
    (r"rapid\w*", " rapido rapida express pronto "),
    (r"barat\w*|econom\w*", " barato economico "),
    (r"leve", " leve saudavel salada bowl "),
    (r"japon\w*|sushi|poke", " japones sushi poke salmao "),
    (r"pizza\w*", " pizza italiana "),
    (r"hamburguer|burger|smash", " hamburguer burger smash "),
    (r"acai", " acai sobremesa "),
    (r"doce|sobremesa", " doce sobremesa acai "),
]


def fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def expand_query(text: str) -> str:
    folded = fold(text)
    extra = []
    for pattern, addition in EXPANSIONS:
        if re.search(pattern, folded):
            extra.append(addition)
    return text + " " + " ".join(extra)


def document_text(dish: DishView) -> str:
    """Texto indexado do prato.

    Restrições (alérgeno, preço, tempo, zona) não entram aqui como atalho:
    a busca aplica esses limites como filtro. O vetor representa o prato em si.
    """
    parts = [
        dish.name,
        dish.name,
        dish.description,
        " ".join(dish.ingredients),
        dish.category,
        dish.restaurant_name,
        dish.cuisine,
        " ".join(dish.tags),
    ]
    if "vegan" in dish.tags:
        parts.append("vegano vegana")
    if "vegetarian" in dish.tags:
        parts.append("vegetariano vegetariana")
    return " ".join(parts)


class Embedder(Protocol):
    dimensions: int

    def fit(self, texts: list[str]) -> None: ...

    def transform(self, texts: list[str]): ...


class TfidfEmbedder:
    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=768,
            lowercase=False,
            preprocessor=fold,
            stop_words=sorted(STOPWORDS),
        )
        self.dimensions = 0
        self._fitted = False

    def fit(self, texts: list[str]) -> None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            matrix = self.vectorizer.fit_transform(texts)
        self.dimensions = int(matrix.shape[1]) if matrix.shape[0] else 0
        self._fitted = True
        self._matrix = matrix

    def transform(self, texts: list[str]):
        if not self._fitted:
            raise RuntimeError("O embedder precisa ser ajustado no catálogo antes da busca.")
        return self.vectorizer.transform(texts)

    @property
    def fitted_matrix(self):
        return self._matrix
