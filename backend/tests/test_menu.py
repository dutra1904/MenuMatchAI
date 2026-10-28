from app.catalog import load_catalog
from app.intent import is_confirm, parse_intent
from app.pricing import build_quote
from app.search import MenuIndex

HERO = "quero algo sem lactose, rápido e por menos de R$ 40"


def _index() -> MenuIndex:
    _restaurants, dishes = load_catalog()
    index = MenuIndex()
    index.build(dishes)
    return index


def test_canonical_intent():
    intent = parse_intent(HERO)
    assert intent.exclude_allergens == ["lactose"]
    assert intent.max_price == 40
    assert intent.max_prep == 20
    assert intent.wants_order is True
    assert intent.zone is None


def test_confirm_phrases():
    assert is_confirm("confirma")
    assert is_confirm("Confirmar o pedido")
    assert not is_confirm(HERO)
    assert not is_confirm("pode mandar um suco")


def test_hero_search_respects_filters():
    results, relaxed = _index().search(
        HERO,
        max_price=40,
        max_prep=20,
        exclude_allergens=["lactose"],
    )
    assert relaxed is None
    assert results
    assert results[0].kind == "main"
    assert "bn-margherita" not in {dish.id for dish in results}
    for dish in results:
        assert "lactose" not in dish.allergens
        assert dish.price <= 40
        assert dish.prep_minutes <= 20


def test_vegan_excludes_omelete():
    results, _relaxed = _index().search("almoço vegano e leve", diet="vegan")
    ids = {dish.id for dish in results}
    assert "vl-omelete" not in ids
    assert "vl-quinoa" in ids


def test_zone_blocks_restaurant():
    results, _relaxed = _index().search("poke de salmão", zone="zona_leste", relax=False)
    assert all(dish.restaurant_id != "sushi-zen" for dish in results)


def test_quote_adds_delivery_fee():
    _restaurants, dishes = load_catalog()
    bowl = next(dish for dish in dishes if dish.id == "vl-bowl-frango")
    quote = build_quote([(bowl, 1)], "centro")
    assert quote.subtotal == 32.9
    assert quote.delivery_fee == 5.9
    assert quote.total == 38.8
    assert quote.zone_label == "Centro"
