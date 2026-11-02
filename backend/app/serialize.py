from app.catalog import DishView
from app.pricing import Quote
from app.schemas import DishOut, OrderItemOut, OrderOut
from app.services.classifier import predict_tags


def dish_out(dish: DishView) -> DishOut:
    badges: list[str] = []
    if "vegan" in dish.tags:
        badges.append("vegano")
    elif "vegetarian" in dish.tags:
        badges.append("vegetariano")
    if "lactose" not in dish.allergens:
        badges.append("sem lactose")
    if "gluten" not in dish.allergens:
        badges.append("sem glúten")
    return DishOut(
        id=dish.id,
        restaurant_id=dish.restaurant_id,
        restaurant_name=dish.restaurant_name,
        cuisine=dish.cuisine,
        name=dish.name,
        description=dish.description,
        price=dish.price,
        prep_minutes=dish.prep_minutes,
        kind=dish.kind,
        category=dish.category,
        badges=badges[:3],
        predicted_tags=predict_tags(f"{dish.name}. {dish.description}"),
    )


def order_out(
    quote: Quote,
    *,
    status: str,
    dietary_notes: list[str],
    customer_query: str,
    order_id: str | None = None,
) -> OrderOut:
    return OrderOut(
        id=order_id,
        status=status,  # type: ignore[arg-type]
        restaurant_id=quote.restaurant_id,
        restaurant_name=quote.restaurant_name,
        zone=quote.zone,
        zone_label=quote.zone_label,
        items=[OrderItemOut(**item) for item in quote.items],
        subtotal=quote.subtotal,
        delivery_fee=quote.delivery_fee,
        total=quote.total,
        prep_minutes=quote.prep_minutes,
        dietary_notes=dietary_notes,
        customer_query=customer_query,
    )
