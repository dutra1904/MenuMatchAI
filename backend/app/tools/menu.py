"""As duas ferramentas do atendimento, sem depender do modelo de linguagem."""

from __future__ import annotations

from app.catalog import DishView
from app.pricing import Quote, build_quote
from app.search import MenuIndex


def search_menu(
    index: MenuIndex,
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
    return index.search(
        query,
        max_price=max_price,
        max_prep=max_prep,
        exclude_allergens=exclude_allergens,
        diet=diet,
        zone=zone,
        exclude_ids=exclude_ids,
        limit=limit,
        relax=relax,
    )


def quote_items(index: MenuIndex, dish_ids: list[str], quantities: list[int], zone: str) -> Quote:
    by_id = {dish.id: dish for dish in index.dishes}
    pairs: list[tuple[DishView, int]] = []
    for position, dish_id in enumerate(dish_ids):
        dish = by_id.get(dish_id)
        if dish is None:
            raise ValueError(f"Prato desconhecido: {dish_id}")
        quantity = quantities[position] if position < len(quantities) else 1
        pairs.append((dish, quantity))
    if not pairs:
        raise ValueError("O pedido precisa de ao menos um prato.")
    return build_quote(pairs, zone)
