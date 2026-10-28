import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db import Order, OrderItem
from app.pricing import Quote


def save_order(
    session: Session,
    quote: Quote,
    *,
    dietary_notes: list[str],
    customer_query: str,
    created_at: datetime | None = None,
) -> str:
    order_id = "mm_" + uuid.uuid4().hex[:8]
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
            dietary_notes=json.dumps(dietary_notes, ensure_ascii=False),
            customer_query=customer_query,
            status="confirmed",
            created_at=created_at or datetime.now(),
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
    return order_id


def order_payload(order: Order, items: list[OrderItem]) -> dict:
    return {
        "id": order.id,
        "restaurant_name": order.restaurant_name,
        "total": order.total,
        "dietary_notes": json.loads(order.dietary_notes or "[]"),
        "created_at": order.created_at.isoformat(),
        "status": order.status,
        "items": items,
    }
