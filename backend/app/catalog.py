"""Ingestão do cardápio fictício: JSON -> registros -> PostgreSQL/SQLite."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import Dish, Meta, Order, OrderItem, Restaurant

DATA_DIR = Path(__file__).resolve().parent / "data"
MENUS_PATH = DATA_DIR / "menus.json"
SEED_ORDERS_PATH = DATA_DIR / "seed_orders.json"


@dataclass(frozen=True)
class DishView:
    id: str
    restaurant_id: str
    restaurant_name: str
    cuisine: str
    rating: float
    zones: tuple[str, ...]
    name: str
    description: str
    ingredients: tuple[str, ...]
    allergens: tuple[str, ...]
    tags: tuple[str, ...]
    category: str
    kind: str
    price: float
    prep_minutes: int


def load_payload() -> dict:
    return json.loads(MENUS_PATH.read_text(encoding="utf-8"))


def load_catalog() -> tuple[list[dict], list[DishView]]:
    payload = load_payload()
    restaurants = {item["id"]: item for item in payload["restaurants"]}
    if len(restaurants) != len(payload["restaurants"]):
        raise ValueError("Há restaurantes com id repetido.")

    dishes: list[DishView] = []
    seen: set[str] = set()
    for raw in payload["dishes"]:
        if raw["id"] in seen:
            raise ValueError(f"Prato duplicado: {raw['id']}")
        seen.add(raw["id"])
        restaurant = restaurants[raw["restaurant_id"]]
        dishes.append(
            DishView(
                id=raw["id"],
                restaurant_id=raw["restaurant_id"],
                restaurant_name=restaurant["name"],
                cuisine=restaurant["cuisine"],
                rating=float(restaurant["rating"]),
                zones=tuple(restaurant["zones"]),
                name=raw["name"],
                description=raw["description"],
                ingredients=tuple(raw["ingredients"]),
                allergens=tuple(raw["allergens"]),
                tags=tuple(raw["tags"]),
                category=raw["category"],
                kind=raw["kind"],
                price=float(raw["price"]),
                prep_minutes=int(raw["prep_minutes"]),
            )
        )
    return payload["restaurants"], dishes


def _catalog_hash() -> str:
    digest = hashlib.sha256(MENUS_PATH.read_bytes()).hexdigest()
    return digest[:16]


def sync_catalog(session: Session) -> list[DishView]:
    restaurants, dishes = load_catalog()
    current = session.get(Meta, "catalog_hash")
    digest = _catalog_hash()
    if current and current.value == digest and session.scalar(select(Restaurant).limit(1)):
        return dishes

    session.execute(delete(Dish))
    session.execute(delete(Restaurant))
    for restaurant in restaurants:
        session.add(
            Restaurant(
                id=restaurant["id"],
                name=restaurant["name"],
                cuisine=restaurant["cuisine"],
                rating=float(restaurant["rating"]),
                zones=json.dumps(restaurant["zones"]),
            )
        )
    session.flush()
    for dish in dishes:
        session.add(
            Dish(
                id=dish.id,
                restaurant_id=dish.restaurant_id,
                name=dish.name,
                description=dish.description,
                ingredients=json.dumps(list(dish.ingredients), ensure_ascii=False),
                allergens=json.dumps(list(dish.allergens)),
                tags=json.dumps(list(dish.tags)),
                category=dish.category,
                kind=dish.kind,
                price=dish.price,
                prep_minutes=dish.prep_minutes,
            )
        )
    if current:
        current.value = digest
    else:
        session.add(Meta(key="catalog_hash", value=digest))
    session.commit()
    return dishes


def _stamp(day: str, slot: float) -> datetime:
    now = datetime.now().replace(microsecond=0)
    if day == "today":
        start = now.replace(hour=0, minute=20, second=0)
        if start >= now:
            start = now - timedelta(hours=2)
        return start + (now - start) * min(max(slot, 0.02), 0.98)
    yesterday = (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    return yesterday + timedelta(hours=slot * 4)


def seed_orders_if_empty(session: Session, dishes: list[DishView], quote_for) -> None:
    existing = session.scalar(select(Order).limit(1))
    if existing:
        return
    by_id = {dish.id: dish for dish in dishes}
    raw_orders = json.loads(SEED_ORDERS_PATH.read_text(encoding="utf-8"))
    for index, raw in enumerate(raw_orders, start=1):
        pairs = [(by_id[item["dish_id"]], int(item["qty"])) for item in raw["items"]]
        quote = quote_for(pairs, raw["zone"])
        order_id = f"seed_{index:03d}"
        session.add(
            Order(
                id=order_id,
                restaurant_id=quote.restaurant_id,
                restaurant_name=quote.restaurant_name,
                zone=quote.zone,
                subtotal=quote.subtotal,
                delivery_fee=quote.delivery_fee,
                total=quote.total,
                prep_minutes=quote.prep_minutes,
                dietary_notes=json.dumps(raw.get("dietary_notes", []), ensure_ascii=False),
                customer_query=raw.get("customer_query", ""),
                status="confirmed",
                created_at=_stamp(raw["day"], float(raw["slot"])),
            )
        )
        for item in quote.items:
            session.add(
                OrderItem(
                    order_id=order_id,
                    dish_id=item["dish_id"],
                    name=item["name"],
                    qty=item["qty"],
                    unit_price=item["unit_price"],
                )
            )
    session.commit()
