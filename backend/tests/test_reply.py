from app.langchain_agent import customer_reply
from app.schemas import DishOut, OrderItemOut, OrderOut

BLOB = (
    'relaxed": null, "dishes": [{"dish_id": "ap-zero", "name": "Açaí Zero Lactose", '
    '"prep_minutes": 8}]'
)


def _dish() -> DishOut:
    return DishOut(
        id="ap-zero",
        restaurant_id="acai-praia",
        restaurant_name="Açaí da Praia",
        cuisine="Açaí",
        name="Açaí Zero Lactose",
        description="Açaí sem leite.",
        price=24.0,
        prep_minutes=8,
        kind="dessert",
        category="Açaí",
        badges=["vegano"],
    )


def _order() -> OrderOut:
    return OrderOut(
        status="draft",
        restaurant_id="acai-praia",
        restaurant_name="Açaí da Praia",
        zone="centro",
        zone_label="Centro",
        items=[OrderItemOut(dish_id="ap-vitamina", name="Vitamina de Banana", qty=1, unit_price=14.0)],
        subtotal=14.0,
        delivery_fee=5.9,
        total=19.9,
        prep_minutes=6,
    )


def test_json_blob_becomes_a_sentence():
    reply = customer_reply(BLOB, [_dish()], None)
    assert "dish_id" not in reply
    assert "{" not in reply
    assert "Açaí Zero Lactose" in reply
    assert "R$ 24,00" in reply


def test_markdown_order_becomes_a_sentence():
    raw = (
        "Aqui está o resumo do seu pedido:\n\n"
        "- **Item:** 1x Vitamina de Banana — R$ 14,00 - **Taxa de entrega:** R$ 5,90 - **Total:** R$ 19,90"
    )
    reply = customer_reply(raw, [], _order())
    assert "**" not in reply
    assert "Vitamina de Banana" in reply
    assert "R$ 19,90" in reply
    assert "Centro" in reply
