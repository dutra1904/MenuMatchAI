import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import configured_provider, handle_chat
from app.analytics import LatencyLog, snapshot
from app.catalog import seed_orders_if_empty, sync_catalog
from app.db import Restaurant, get_session, init_db, SessionLocal
from app.pricing import build_quote
from app.schemas import (
    AnalyticsOut,
    ChatRequest,
    ChatResponse,
    CreateOrderRequest,
    DishOut,
    OrderOut,
    RestaurantOut,
)
from app.search import MenuIndex
from app.serialize import dish_out, order_out
from app.orders import save_order
from app.config import settings

logger = logging.getLogger("menumatch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as session:
        dishes = sync_catalog(session)
        seed_orders_if_empty(session, dishes, build_quote)
    index = MenuIndex()
    index.build(dishes)
    app.state.index = index
    app.state.sessions = {}
    app.state.latency = LatencyLog()
    logger.info(
        "Índice pronto: %s pratos, %s dimensões (%s)",
        index.meta["documents"],
        index.meta["dimensions"],
        index.meta["provider"],
    )
    yield


app = FastAPI(title="MenuMatch AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {"service": "MenuMatch AI", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health(request: Request) -> dict:
    index: MenuIndex = request.app.state.index
    return {
        "status": "ok",
        "dishes": index.meta.get("documents", 0),
        "restaurants": len({dish.restaurant_id for dish in index.dishes}),
        "embedder": index.meta.get("provider"),
        "dimensions": index.meta.get("dimensions", 0),
        "llm": configured_provider(),
    }


@app.get("/api/restaurants", response_model=list[RestaurantOut])
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


@app.get("/api/menu", response_model=list[DishOut])
def menu(
    request: Request,
    q: str = "",
    max_price: float | None = None,
    max_prep: int | None = None,
    diet: str | None = None,
    zone: str | None = None,
) -> list[DishOut]:
    index: MenuIndex = request.app.state.index
    dishes, _relaxed = index.search(
        q,
        max_price=max_price,
        max_prep=max_prep,
        diet=diet,
        zone=zone,
        relax=False,
        limit=8,
    )
    return [dish_out(dish) for dish in dishes]


@app.post("/api/chat", response_model=ChatResponse)
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


@app.post("/api/orders", response_model=OrderOut)
def create_order(
    body: CreateOrderRequest,
    request: Request,
    db: Session = Depends(get_session),
) -> OrderOut:
    index: MenuIndex = request.app.state.index
    by_id = {dish.id: dish for dish in index.dishes}
    pairs = []
    for item in body.items:
        dish = by_id.get(item.dish_id)
        if dish is None:
            raise HTTPException(status_code=404, detail=f"Prato não encontrado: {item.dish_id}")
        if dish.restaurant_id != body.restaurant_id:
            raise HTTPException(status_code=400, detail="Os pratos precisam ser do mesmo restaurante.")
        pairs.append((dish, item.qty))
    try:
        quote = build_quote(pairs, body.zone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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


@app.get("/api/analytics", response_model=AnalyticsOut)
def analytics(request: Request, db: Session = Depends(get_session)) -> AnalyticsOut:
    return snapshot(db, request.app.state.index, request.app.state.latency)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
