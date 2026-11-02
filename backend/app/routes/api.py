import json
import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import configured_provider, handle_chat
from app.db import Restaurant, get_session
from app.errors import DishNotFound, RestaurantMismatch
from app.schemas import (
    AnalyticsOut,
    ChatRequest,
    ChatResponse,
    ClassifyRequest,
    ClassifyResponse,
    CreateOrderRequest,
    DishOut,
    OrderOut,
    RestaurantOut,
)
from app.search import MenuIndex
from app.serialize import dish_out, order_out
from app.services.classifier import LABELS, predict_scores, predict_tags
from app.orders import save_order
from app.tools.menu import quote_items, search_menu

router = APIRouter()


@router.get("/")
def root() -> dict:
    return {"service": "MenuMatch AI", "docs": "/docs", "health": "/api/health"}


@router.get("/api/health")
def health(request: Request) -> dict:
    index: MenuIndex = request.app.state.index
    return {
        "status": "ok",
        "dishes": index.meta.get("documents", 0),
        "restaurants": len({dish.restaurant_id for dish in index.dishes}),
        "embedder": index.meta.get("provider"),
        "embedding_model": index.meta.get("model"),
        "vector_backend": index.meta.get("vector_backend"),
        "metric": index.meta.get("metric", "cosine"),
        "dimensions": index.meta.get("dimensions", 0),
        "classifier": "tfidf-multioutput",
        "classifier_labels": list(LABELS),
        "llm": configured_provider(),
    }


@router.get("/api/restaurants", response_model=list[RestaurantOut])
def restaurants(db: Session = Depends(get_session)) -> list[RestaurantOut]:
    rows = db.scalars(select(Restaurant).order_by(Restaurant.name)).all()
    return [
        RestaurantOut(
            id=row.id,
            name=row.name,
            cuisine=row.cuisine,
            rating=row.rating,
            zones=json.loads(row.zones),
        )
        for row in rows
    ]


@router.get("/api/menu", response_model=list[DishOut])
def menu(
    request: Request,
    q: str = "",
    max_price: float | None = None,
    max_prep: int | None = None,
    diet: str | None = None,
    zone: str | None = None,
) -> list[DishOut]:
    index: MenuIndex = request.app.state.index
    dishes, _relaxed = search_menu(
        index,
        q,
        max_price=max_price,
        max_prep=max_prep,
        diet=diet,
        zone=zone,
        relax=False,
        limit=8,
    )
    return [dish_out(dish) for dish in dishes]


@router.post("/api/classify", response_model=ClassifyResponse)
def classify(body: ClassifyRequest) -> ClassifyResponse:
    return ClassifyResponse(tags=predict_tags(body.text), scores=predict_scores(body.text))


@router.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request, db: Session = Depends(get_session)) -> ChatResponse:
    started = time.perf_counter()
    result = handle_chat(
        db=db,
        index=request.app.state.index,
        sessions=request.app.state.sessions,
        body=body,
    )
    result.latency_ms = int((time.perf_counter() - started) * 1000)
    request.app.state.latency.add(result.latency_ms)
    return result


@router.post("/api/orders", response_model=OrderOut)
def create_order(
    body: CreateOrderRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> OrderOut:
    index: MenuIndex = request.app.state.index
    by_id = {dish.id: dish for dish in index.dishes}
    for item in body.items:
        dish = by_id.get(item.dish_id)
        if dish is None:
            raise DishNotFound(item.dish_id)
        if dish.restaurant_id != body.restaurant_id:
            raise RestaurantMismatch()
    quote = quote_items(
        index,
        [item.dish_id for item in body.items],
        [item.qty for item in body.items],
        body.zone,
    )
    order_id = save_order(
        db,
        quote,
        dietary_notes=body.dietary_notes,
        customer_query=body.customer_query,
    )
    return order_out(
        quote,
        status="confirmed",
        dietary_notes=body.dietary_notes,
        customer_query=body.customer_query,
        order_id=order_id,
    )


@router.get("/api/analytics", response_model=AnalyticsOut)
def analytics(request: Request, db: Session = Depends(get_session)) -> AnalyticsOut:
    from app.analytics import snapshot

    return snapshot(db, request.app.state.index, request.app.state.latency)
