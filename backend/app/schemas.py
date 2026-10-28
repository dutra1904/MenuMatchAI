from typing import Literal

from pydantic import BaseModel, Field


class DishOut(BaseModel):
    id: str
    restaurant_id: str
    restaurant_name: str
    cuisine: str
    name: str
    description: str
    price: float
    prep_minutes: int
    kind: str
    category: str
    badges: list[str]


class RestaurantOut(BaseModel):
    id: str
    name: str
    cuisine: str
    rating: float
    zones: list[str]


class OrderItemOut(BaseModel):
    dish_id: str
    name: str
    qty: int
    unit_price: float


class OrderOut(BaseModel):
    id: str | None = None
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["draft", "confirmed"]
    restaurant_id: str
    restaurant_name: str
    zone: str
    zone_label: str
    items: list[OrderItemOut]
    subtotal: float
    delivery_fee: float
    total: float
    prep_minutes: int
    dietary_notes: list[str] = []
    customer_query: str = ""


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None
    history: list[HistoryMessage] = []


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    recommendations: list[DishOut]
    order: OrderOut | None = None
    tools_used: list[str]
    latency_ms: int = 0
    provider: str


class CreateOrderItem(BaseModel):
    dish_id: str
    qty: int = Field(default=1, ge=1, le=10)


class CreateOrderRequest(BaseModel):
    restaurant_id: str
    zone: str
    items: list[CreateOrderItem] = Field(min_length=1)
    dietary_notes: list[str] = []
    customer_query: str = ""


class TopDish(BaseModel):
    name: str
    restaurant_name: str
    qty: int


class RecentOrder(BaseModel):
    id: str
    restaurant_name: str
    total: float
    item_summary: str
    dietary_notes: list[str]
    created_at: str
    status: str


class AnalyticsOut(BaseModel):
    orders_today: int
    revenue_today: float
    avg_ticket: float
    minutes_saved: float
    restriction_rate: float
    browse_minutes: float
    agent_minutes: float
    avg_latency_ms: int | None
    top_dishes: list[TopDish]
    recent_orders: list[RecentOrder]
    dishes_indexed: int
    restaurants_indexed: int
    embedder: str
    dimensions: int
