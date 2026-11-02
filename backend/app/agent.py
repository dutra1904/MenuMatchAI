"""Orquestrador do MenuMatch.

Com chave de API, delega ao LangChain (tool calling). Sem chave, ou se o modelo
não consultar as ferramentas, executa a mesma busca e o mesmo cálculo de pedido.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.catalog import DishView
from app.config import settings
from app.embeddings import fold
from app.intent import (
    ALLERGEN_LABELS,
    Intent,
    is_confirm,
    is_followup,
    merge_followup,
    parse_intent,
)
from app.orders import save_order
from app.schemas import ChatRequest, ChatResponse, OrderOut
from app.search import MenuIndex
from app.serialize import dish_out, order_out
from app.tools.menu import quote_items, search_menu as search_catalog

logger = logging.getLogger("menumatch")


def brl(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def notes_from_intent(intent: Intent) -> list[str]:
    notes: list[str] = []
    if intent.diet == "vegan":
        notes.append("vegano")
    elif intent.diet == "vegetarian":
        notes.append("vegetariano")
    for code in intent.exclude_allergens:
        notes.append(f"sem {ALLERGEN_LABELS[code]}")
    return notes


def configured_provider() -> str:
    choice = settings.llm_provider.lower().strip()
    if choice == "local":
        return "local"
    if choice == "gemini":
        return "langchain-gemini" if settings.gemini_api_key else "local"
    if choice == "openai":
        return "langchain-openai" if settings.openai_api_key else "local"
    if settings.gemini_api_key:
        return "langchain-gemini"
    if settings.openai_api_key:
        return "langchain-openai"
    return "local"


def handle_chat(
    *,
    db: Session,
    index: MenuIndex,
    sessions: dict[str, dict],
    body: ChatRequest,
) -> ChatResponse:
    session_id = body.session_id or _new_session_id()
    session = sessions.setdefault(session_id, {})
    if configured_provider() != "local":
        try:
            from app.langchain_agent import LlmSkipped, run_llm

            result = run_llm(
                index=index,
                message=body.message,
                history=body.history,
                session_id=session_id,
            )
            if result.tools_used:
                if result.order and result.order.status == "draft":
                    session["draft"] = result.order.model_dump()
                return result
            logger.info("LLM não chamou ferramentas; usando o orquestrador local.")
        except LlmSkipped:
            pass
        except Exception:
            logger.exception("Falha no LLM; usando o orquestrador local.")
    return _local(db=db, index=index, session=session, session_id=session_id, body=body)


def _new_session_id() -> str:
    from uuid import uuid4

    return uuid4().hex[:12]


def _local(
    *,
    db: Session,
    index: MenuIndex,
    session: dict,
    session_id: str,
    body: ChatRequest,
) -> ChatResponse:
    message = body.message.strip()
    if is_confirm(message):
        return _confirm(db, index, session, session_id)

    previous = Intent(**session["intent"]) if session.get("intent") else None
    if previous and is_followup(message):
        intent = merge_followup(message, previous, session.get("last_price"), session.get("last_id"))
        if len(message.split()) <= 3:
            intent.query = previous.query
    else:
        intent = parse_intent(message)

    dishes, relaxed = search_catalog(
        index,
        intent.query,
        max_price=intent.max_price,
        max_prep=intent.max_prep,
        exclude_allergens=intent.exclude_allergens,
        diet=intent.diet,
        zone=intent.zone,
        exclude_ids=intent.exclude_ids,
    )
    named = index.find_named(message)
    conflict = None
    pinned = None
    if named:
        allowed = index._allows(
            named,
            max_price=intent.max_price,
            max_prep=intent.max_prep,
            exclude_allergens=intent.exclude_allergens,
            diet=intent.diet,
            zone=intent.zone,
            exclude_ids=set(intent.exclude_ids),
        )
        if allowed:
            dishes = [named] + [dish for dish in dishes if dish.id != named.id]
            dishes = dishes[:4]
            pinned = named
        else:
            conflict = named

    tools = ["search_menu"]
    order = None
    zone_assumed = False
    if intent.wants_order and dishes:
        if pinned:
            chosen, zone, zone_assumed = _zone_for(pinned, intent.zone)
        else:
            chosen, zone, zone_assumed = _choose(dishes, intent.zone)
        try:
            quote = quote_items(index, [chosen.id], [_quantity(message)], zone)
            order = order_out(
                quote,
                status="draft",
                dietary_notes=notes_from_intent(intent),
                customer_query=message,
            )
            tools.append("calculate_order")
            session["draft"] = order.model_dump()
        except ValueError as exc:
            conflict = conflict or exc

    session["intent"] = asdict(intent)
    if dishes:
        session["last_price"] = dishes[0].price
        session["last_id"] = dishes[0].id

    return ChatResponse(
        session_id=session_id,
        reply=_reply(intent, dishes, order, relaxed, zone_assumed, conflict),
        recommendations=[dish_out(dish) for dish in dishes],
        order=order,
        tools_used=tools,
        provider="local",
    )


def _confirm(db: Session, index: MenuIndex, session: dict, session_id: str) -> ChatResponse:
    raw = session.get("draft")
    if not raw:
        return ChatResponse(
            session_id=session_id,
            reply="Ainda não montei um pedido. Me diga o que você quer comer, com restrição, pressa ou teto de preço.",
            recommendations=[],
            order=None,
            tools_used=[],
            provider="local",
        )
    draft = OrderOut.model_validate(raw)
    if draft.status == "confirmed" and draft.id:
        return ChatResponse(
            session_id=session_id,
            reply=f"O pedido {draft.id} já está confirmado. Se quiser outro, é só dizer o que vai querer.",
            recommendations=[],
            order=draft,
            tools_used=[],
            provider="local",
        )
    quote = quote_items(
        index,
        [item.dish_id for item in draft.items],
        [item.qty for item in draft.items],
        draft.zone,
    )
    order_id = save_order(
        db,
        quote,
        dietary_notes=draft.dietary_notes,
        customer_query=draft.customer_query,
    )
    confirmed = order_out(
        quote,
        status="confirmed",
        dietary_notes=draft.dietary_notes,
        customer_query=draft.customer_query,
        order_id=order_id,
    )
    session["draft"] = confirmed.model_dump()
    return ChatResponse(
        session_id=session_id,
        reply=(
            f"Pedido {order_id} confirmado no {confirmed.restaurant_name}. "
            f"Total {brl(confirmed.total)}, entrega na região {confirmed.zone_label}. "
            "O painel do restaurante já conta essa venda."
        ),
        recommendations=[],
        order=confirmed,
        tools_used=["create_order"],
        provider="local",
    )


def _zone_for(dish: DishView, zone: str | None) -> tuple[DishView, str, bool]:
    target = zone or "centro"
    if target in dish.zones:
        return dish, target, zone is None
    return dish, dish.zones[0], True


def _choose(dishes: list[DishView], zone: str | None) -> tuple[DishView, str, bool]:
    target = zone or "centro"
    assumed = zone is None
    for dish in dishes:
        if dish.kind == "main" and target in dish.zones:
            return dish, target, assumed
    for dish in dishes:
        if target in dish.zones:
            return dish, target, assumed
    fallback = dishes[0]
    return fallback, fallback.zones[0], True


def _quantity(message: str) -> int:
    match = re.search(r"\b(\d)\s+(?:unidades|porcoes|pratos)\b", fold(message))
    if not match:
        return 1
    return max(1, min(10, int(match.group(1))))


def _filters(intent: Intent) -> str:
    parts: list[str] = []
    if intent.diet == "vegan":
        parts.append("veganas")
    elif intent.diet == "vegetarian":
        parts.append("vegetarianas")
    for code in intent.exclude_allergens:
        parts.append(f"sem {ALLERGEN_LABELS[code]}")
    if intent.max_prep:
        parts.append(f"em até {intent.max_prep} min")
    if intent.max_price:
        parts.append(f"até {brl(intent.max_price)}")
    if intent.zone:
        from app.pricing import zone_label

        parts.append(zone_label(intent.zone))
    return ", ".join(parts)


def _reply(intent, dishes, order, relaxed, zone_assumed, conflict) -> str:
    if not dishes:
        return (
            "Não encontrei pratos com essas restrições nos cardápios indexados. "
            "Dá para ampliar o preço, o tempo ou a região."
        )
    filtros = _filters(intent)
    opening = f"Separei {len(dishes)} opções"
    if filtros:
        opening += f" ({filtros})"
    opening += "."
    if relaxed == "prep":
        opening += " Nada ficava pronto no tempo pedido, então abri o limite."
    elif relaxed == "price":
        opening += " Nada coube no teto, então ampliei a faixa em R$ 15."
    best = dishes[0]
    paragraphs = [
        opening,
        (
            f"A melhor pedida é {best.name}, do {best.restaurant_name}: "
            f"{brl(best.price)}, pronto em {best.prep_minutes} min."
        ),
    ]
    if len(dishes) > 1:
        alts = "; ".join(f"{dish.name} ({brl(dish.price)})" for dish in dishes[1:3])
        paragraphs.append(f"Também combinam: {alts}.")
    if isinstance(conflict, DishView):
        paragraphs.append(f"{conflict.name} ficou de fora porque não cabe no filtro desta conversa.")
    elif isinstance(conflict, ValueError):
        paragraphs.append(str(conflict))
    if order:
        zone_bit = (
            f" Considerei entrega na região {order.zone_label}."
            if zone_assumed
            else f" Entrega na região {order.zone_label}."
        )
        paragraphs.append(
            f"Montei o pedido com taxa de {brl(order.delivery_fee)}.{zone_bit} "
            f"Total {brl(order.total)}. Confirme para registrar ou peça outra opção."
        )
    else:
        paragraphs.append("Se quiser, eu monto o pedido com uma dessas opções.")
    return "\n\n".join(paragraphs)
