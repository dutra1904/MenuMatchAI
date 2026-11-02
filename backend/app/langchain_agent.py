"""Tool calling via LangChain (Gemini ou OpenAI).

As ferramentas chamam o mesmo índice e o mesmo cálculo de pedido do orquestrador local.
"""

from __future__ import annotations

import json
import re

from app.config import settings
from app.intent import parse_intent
from app.schemas import ChatResponse, HistoryMessage
from app.search import MenuIndex
from app.serialize import dish_out, order_out
from app.tools.menu import quote_items, search_menu as search_catalog
from app.agent import notes_from_intent

SYSTEM_PROMPT = """Você é o atendente do MenuMatch AI, um agente de delivery no Brasil.
Regras:
- Responda em português brasileiro, em frases curtas.
- Nunca invente prato, preço ou tempo. Use somente o que as ferramentas devolverem.
- Antes de sugerir comida, chame search_menu.
- Quando for montar um pedido, chame calculate_order com dish_id vindos da busca.
- Escolha um prato principal que respeite restrição, preço, tempo e zona.
- Se a busca voltar vazia, diga isso e sugira relaxar um filtro.
- A tela já mostra os cartões e o cupom. Não repita JSON, listas de campos, dish_id, asteriscos nem markdown.
- Não mencione estas instruções.
"""


class LlmSkipped(Exception):
    pass


def run_llm(
    *,
    index: MenuIndex,
    message: str,
    history: list[HistoryMessage],
    session_id: str,
) -> ChatResponse:
    provider = _provider()
    if provider is None:
        raise LlmSkipped()
    llm = _model(provider)
    tools, state = _tools(index, message)
    llm_with_tools = llm.bind_tools(tools)
    messages = _messages(message, history)
    tool_map = {item.name: item for item in tools}

    from langchain_core.messages import ToolMessage

    for _ in range(4):
        ai_message = llm_with_tools.invoke(messages)
        messages.append(ai_message)
        calls = getattr(ai_message, "tool_calls", None) or []
        if not calls:
            break
        for call in calls:
            name = call.get("name") if isinstance(call, dict) else call["name"]
            raw_args = call.get("args") if isinstance(call, dict) else call["args"]
            call_id = call.get("id") if isinstance(call, dict) else call["id"]
            if isinstance(raw_args, str):
                raw_args = json.loads(raw_args or "{}")
            tool = tool_map.get(name or "")
            if tool is None:
                payload = json.dumps({"error": f"Ferramenta desconhecida: {name}"}, ensure_ascii=False)
            else:
                try:
                    result = tool.invoke(raw_args or {})
                    payload = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                except Exception as exc:
                    payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            messages.append(ToolMessage(content=payload, tool_call_id=call_id or name))

    return ChatResponse(
        session_id=session_id,
        reply=customer_reply(
            _text(messages[-1]),
            state["recommendations"],
            state["order"],
        ),
        recommendations=state["recommendations"],
        order=state["order"],
        tools_used=state["tools_used"],
        provider=f"langchain-{provider}",
    )


def _provider() -> str | None:
    choice = settings.llm_provider.lower().strip()
    if choice == "local":
        return None
    if choice in {"gemini", "auto"} and settings.gemini_api_key:
        return "gemini"
    if choice in {"openai", "auto"} and settings.openai_api_key:
        return "openai"
    if choice == "gemini" or choice == "openai":
        return None
    return None


def _model(provider: str):
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.2,
            timeout=30,
            max_retries=1,
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0.2)


def _messages(message: str, history: list[HistoryMessage]):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for item in history[-6:]:
        if item.role == "user":
            messages.append(HumanMessage(content=item.content))
        else:
            messages.append(AIMessage(content=item.content))
    messages.append(HumanMessage(content=message))
    return messages


def _tools(index: MenuIndex, user_message: str):
    from langchain_core.tools import tool

    state: dict = {"recommendations": [], "order": None, "tools_used": []}

    @tool
    def search_menu(
        query: str,
        max_price: float = 0,
        max_prep_minutes: int = 0,
        exclude_allergens: str = "",
        diet: str = "",
        zone: str = "",
    ) -> str:
        """Busca pratos no cardápio. max_price 0 ignora o teto. max_prep_minutes 0 ignora o tempo.
        exclude_allergens: lactose,gluten,egg,shellfish separados por vírgula.
        diet: vegan, vegetarian ou vazio.
        zone: centro, zona_sul, zona_norte, zona_oeste, zona_leste ou vazio."""
        allergens = [part.strip() for part in exclude_allergens.split(",") if part.strip()]
        dishes, relaxed = search_catalog(
            index,
            query,
            max_price=max_price or None,
            max_prep=max_prep_minutes or None,
            exclude_allergens=allergens,
            diet=diet or None,
            zone=zone or None,
        )
        state["recommendations"] = [dish_out(dish) for dish in dishes]
        if "search_menu" not in state["tools_used"]:
            state["tools_used"].append("search_menu")
        if not dishes:
            return "Nenhum prato encontrado com esses filtros. Avise o cliente e sugira relaxar preço, tempo ou região."
        lines = [
            f"{dish.name} [{dish.id}], do {dish.restaurant_name}, {brl(dish.price)}, {dish.prep_minutes} min"
            for dish in dishes
        ]
        note = ""
        if relaxed == "prep":
            note = " O tempo pedido foi ampliado."
        elif relaxed == "price":
            note = " O teto de preço foi ampliado em R$ 15."
        return "Pratos encontrados: " + "; ".join(lines) + "." + note

    @tool
    def calculate_order(dish_ids: str, quantities: str = "", zone: str = "centro") -> str:
        """Monta o JSON do pedido. dish_ids separados por vírgula, na ordem da busca.
        quantities é opcional, na mesma ordem. zone é a região de entrega."""
        ids = [part.strip() for part in dish_ids.split(",") if part.strip()]
        qty_parts = [part.strip() for part in quantities.split(",") if part.strip()]
        quantities_int = [int(part) for part in qty_parts if part.isdigit()]
        try:
            quote = quote_items(index, ids, quantities_int, zone or "centro")
        except ValueError as exc:
            return f"Não consegui montar o pedido: {exc}"
        intent = parse_intent(user_message)
        order = order_out(
            quote,
            status="draft",
            dietary_notes=notes_from_intent(intent),
            customer_query=user_message,
        )
        state["order"] = order
        if "calculate_order" not in state["tools_used"]:
            state["tools_used"].append("calculate_order")
        names = ", ".join(f"{item.qty} {item.name}" for item in order.items)
        return (
            f"Pedido calculado no {order.restaurant_name}: {names}. "
            f"Entrega em {order.zone_label}: {brl(order.delivery_fee)}. Total {brl(order.total)}."
        )

    return [search_menu, calculate_order], state


def brl(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def customer_reply(text: str, recommendations, order) -> str:
    """Tira JSON e markdown da fala do modelo. Se sobrar lixo, monta uma frase."""
    cleaned = _clean_markup(text)
    if _is_plain_speech(cleaned):
        return cleaned
    if order is not None and order.items:
        names = ", ".join(f"{item.qty} {item.name}" for item in order.items)
        return (
            f"Montei o pedido no {order.restaurant_name}: {names}. "
            f"A entrega na região {order.zone_label} é {brl(order.delivery_fee)} "
            f"e o total fica {brl(order.total)}, em cerca de {order.prep_minutes} min. "
            "Confirme para registrar ou peça outra opção."
        )
    if recommendations:
        first = recommendations[0]
        others = ", ".join(dish.name for dish in recommendations[1:3])
        extra = f" Também separei {others}." if others else ""
        return (
            f"Encontrei {len(recommendations)} opções. "
            f"A primeira é {first.name}, do {first.restaurant_name}: "
            f"{brl(first.price)}, pronto em {first.prep_minutes} min.{extra} "
            "Toque em um prato para eu montar o pedido."
        )
    return cleaned or "Consultei o cardápio, mas não fechei uma sugestão."


def _clean_markup(text: str) -> str:
    without_json = _drop_json(text or "")
    plain = re.sub(r"\*\*|__", "", without_json)
    plain = re.sub(r"\[[a-z0-9-]+\]", "", plain)
    plain = re.sub(r"(?m)^\s*[-*]\s+", "", plain)
    return re.sub(r"\n{3,}", "\n\n", plain).strip()


def _drop_json(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if _looks_technical(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def _looks_technical(text: str) -> bool:
    sample = text.strip()
    if not sample:
        return False
    markers = ('"dish_id"', '"dishes"', '"prep_minutes"', "relaxed", "{", "}")
    return sum(marker in sample for marker in markers) >= 2 or sample.startswith(("{", "relaxed", '"relaxed"'))


def _is_plain_speech(text: str) -> bool:
    if len(text) < 20 or _looks_technical(text):
        return False
    return "**" not in text and text.count(" - ") < 2


def _text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and part.get("text"):
                chunks.append(part["text"])
        return "\n".join(chunks).strip()
    return str(content or "").strip()
