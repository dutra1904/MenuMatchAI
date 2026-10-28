import json
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Order, OrderItem
from app.schemas import AnalyticsOut, RecentOrder, TopDish
from app.search import MenuIndex


class LatencyLog:
    def __init__(self) -> None:
        self.samples: list[int] = []

    def add(self, elapsed_ms: int) -> None:
        self.samples.append(elapsed_ms)
        del self.samples[:-100]

    def average(self) -> int | None:
        if not self.samples:
            return None
        return int(round(sum(self.samples) / len(self.samples)))


def snapshot(session: Session, index: MenuIndex, latency: LatencyLog) -> AnalyticsOut:
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    today = session.scalars(
        select(Order).where(Order.created_at >= start, Order.status == "confirmed")
    ).all()
    revenue = round(sum(order.total for order in today), 2)
    count = len(today)
    with_notes = sum(1 for order in today if json.loads(order.dietary_notes or "[]"))
    rows = session.execute(
        select(OrderItem.name, Order.restaurant_name, func.sum(OrderItem.qty))
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.created_at >= week_ago, Order.status == "confirmed")
        .group_by(OrderItem.name, Order.restaurant_name)
        .order_by(func.sum(OrderItem.qty).desc())
        .limit(5)
    ).all()
    recent = session.scalars(select(Order).order_by(Order.created_at.desc()).limit(8)).all()
    recent_orders: list[RecentOrder] = []
    for order in recent:
        items = session.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
        summary = ", ".join(f"{item.qty}× {item.name}" for item in items)
        recent_orders.append(
            RecentOrder(
                id=order.id,
                restaurant_name=order.restaurant_name,
                total=order.total,
                item_summary=summary,
                dietary_notes=json.loads(order.dietary_notes or "[]"),
                created_at=order.created_at.isoformat(),
                status=order.status,
            )
        )
    restaurants = len({dish.restaurant_id for dish in index.dishes})
    return AnalyticsOut(
        orders_today=count,
        revenue_today=revenue,
        avg_ticket=round(revenue / count, 2) if count else 0,
        minutes_saved=round(count * (settings.browse_minutes - settings.agent_minutes), 1),
        restriction_rate=round(with_notes / count, 2) if count else 0,
        browse_minutes=settings.browse_minutes,
        agent_minutes=settings.agent_minutes,
        avg_latency_ms=latency.average(),
        top_dishes=[
            TopDish(name=name, restaurant_name=restaurant, qty=int(qty))
            for name, restaurant, qty in rows
        ],
        recent_orders=recent_orders,
        dishes_indexed=index.meta.get("documents", 0),
        restaurants_indexed=restaurants,
        embedder=index.meta.get("provider", "tfidf"),
        dimensions=index.meta.get("dimensions", 0),
    )
