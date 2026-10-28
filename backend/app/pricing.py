from dataclasses import dataclass

ZONES: dict[str, tuple[str, float]] = {
    "centro": ("Centro", 5.90),
    "zona_sul": ("Zona Sul", 8.90),
    "zona_norte": ("Zona Norte", 7.50),
    "zona_oeste": ("Zona Oeste", 9.90),
    "zona_leste": ("Zona Leste", 8.50),
}


def zone_label(zone: str) -> str:
    return ZONES.get(zone, ZONES["centro"])[0]


def delivery_fee(zone: str) -> float:
    return ZONES.get(zone, ZONES["centro"])[1]


@dataclass
class Quote:
    restaurant_id: str
    restaurant_name: str
    zone: str
    zone_label: str
    items: list[dict]
    subtotal: float
    delivery_fee: float
    total: float
    prep_minutes: int


def build_quote(pairs: list[tuple], zone: str) -> Quote:
    if not pairs:
        raise ValueError("O pedido precisa de ao menos um item.")
    zone_key = zone if zone in ZONES else "centro"
    restaurant_ids = {dish.restaurant_id for dish, _qty in pairs}
    if len(restaurant_ids) > 1:
        raise ValueError("Um pedido reúne pratos de um único restaurante.")
    dish0 = pairs[0][0]
    if zone_key not in dish0.zones:
        served = ", ".join(zone_label(item) for item in dish0.zones)
        raise ValueError(f"{dish0.restaurant_name} não entrega em {zone_label(zone_key)}. Atende: {served}.")

    items = []
    subtotal = 0.0
    prep = 0
    for dish, qty in pairs:
        qty = int(qty)
        if qty < 1:
            raise ValueError("A quantidade precisa ser pelo menos 1.")
        line = round(dish.price * qty, 2)
        subtotal = round(subtotal + line, 2)
        prep = max(prep, dish.prep_minutes)
        items.append(
            {
                "dish_id": dish.id,
                "name": dish.name,
                "qty": qty,
                "unit_price": round(dish.price, 2),
            }
        )
    fee = delivery_fee(zone_key)
    return Quote(
        restaurant_id=dish0.restaurant_id,
        restaurant_name=dish0.restaurant_name,
        zone=zone_key,
        zone_label=zone_label(zone_key),
        items=items,
        subtotal=subtotal,
        delivery_fee=fee,
        total=round(subtotal + fee, 2),
        prep_minutes=prep,
    )
