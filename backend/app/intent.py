from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from app.embeddings import fold

ALLERGEN_PATTERNS = [
    ("lactose", r"sem\s+lactose|intoleran\w+\s+a\s+lactose|zero\s+lactose"),
    ("gluten", r"sem\s+gluten|celiac\w*"),
    ("egg", r"sem\s+ovos?"),
    ("shellfish", r"sem\s+camarao|sem\s+frutos\s+do\s+mar|alergi\w+\s+a\s+camarao"),
]

ZONE_PATTERNS = [
    ("zona_sul", r"zona\s+sul"),
    ("zona_norte", r"zona\s+norte"),
    ("zona_oeste", r"zona\s+oeste"),
    ("zona_leste", r"zona\s+leste"),
    ("centro", r"\bcentro\b"),
]

ALLERGEN_LABELS = {
    "lactose": "lactose",
    "gluten": "glúten",
    "egg": "ovo",
    "shellfish": "frutos do mar",
}


@dataclass
class Intent:
    query: str
    exclude_allergens: list[str] = field(default_factory=list)
    diet: str | None = None
    max_price: float | None = None
    max_prep: int | None = None
    zone: str | None = None
    zone_assumed: bool = False
    wants_order: bool = False
    exclude_ids: list[str] = field(default_factory=list)

    def clone(self) -> Intent:
        return replace(
            self,
            exclude_allergens=list(self.exclude_allergens),
            exclude_ids=list(self.exclude_ids),
        )


def _money(raw: str) -> float:
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")
    return float(raw)


def parse_intent(message: str) -> Intent:
    folded = fold(message)
    allergens: list[str] = []
    for code, pattern in ALLERGEN_PATTERNS:
        if re.search(pattern, folded):
            allergens.append(code)

    diet = None
    if re.search(r"\bveganas?\b|\bveganos?\b", folded):
        diet = "vegan"
    elif re.search(r"\bvegetarian\w*\b|\bsem carne\b", folded):
        diet = "vegetarian"

    max_price = None
    for pattern in (
        r"(?:por\s+)?menos\s+de\s+r\$\s*(\d+(?:[.,]\d{1,2})?)",
        r"(?:por\s+)?menos\s+de\s+(\d+(?:[.,]\d{1,2})?)\s*reais",
        r"ate\s+r\$\s*(\d+(?:[.,]\d{1,2})?)",
        r"abaixo\s+de\s+r\$\s*(\d+(?:[.,]\d{1,2})?)",
        r"r\$\s*(\d+(?:[.,]\d{1,2})?)",
        r"(\d+(?:[.,]\d{1,2})?)\s*reais",
    ):
        match = re.search(pattern, folded)
        if match:
            max_price = _money(match.group(1))
            break

    max_prep = None
    prep_match = re.search(r"(?:ate|em)\s+(\d{1,3})\s*min", folded)
    if prep_match:
        max_prep = int(prep_match.group(1))
    elif re.search(r"\brapid", folded):
        max_prep = 20

    zone = None
    for code, pattern in ZONE_PATTERNS:
        if re.search(pattern, folded):
            zone = code
            break

    asks_list = bool(re.search(r"\b(quais|o que tem|cardapio|opcoes|lista)\b", folded))
    has_constraint = bool(allergens or diet or max_price or max_prep or zone)
    wants_order = (not asks_list) and (
        bool(re.search(r"\b(quero|pedido|recomend\w*|suger\w*|monta|me ve)\b", folded))
        or has_constraint
    )
    return Intent(
        query=message.strip(),
        exclude_allergens=allergens,
        diet=diet,
        max_price=max_price,
        max_prep=max_prep,
        zone=zone,
        wants_order=wants_order,
    )


def is_confirm(message: str) -> bool:
    folded = fold(message).strip(" !.?,")
    if len(folded) > 40:
        return False
    return bool(
        re.fullmatch(
            r"(sim[, ]*)?(confirm\w+( o pedido)?|fechar( o)? pedido|fecha o pedido|manda o pedido|pode mandar o pedido|pode fechar)",
            folded,
        )
    )


def is_followup(message: str) -> bool:
    folded = fold(message.strip())
    if len(folded.split()) > 8:
        return False
    return bool(re.search(r"\b(outra|outro|mais barat\w*|mais rapid\w*|troca)\b", folded))


def merge_followup(message: str, previous: Intent, last_price: float | None, last_id: str | None) -> Intent:
    parsed = parse_intent(message)
    merged = previous.clone()
    merged.query = message.strip()
    if parsed.exclude_allergens:
        merged.exclude_allergens = parsed.exclude_allergens
    if parsed.diet:
        merged.diet = parsed.diet
    if parsed.max_price:
        merged.max_price = parsed.max_price
    if parsed.max_prep:
        merged.max_prep = parsed.max_prep
    if parsed.zone:
        merged.zone = parsed.zone
        merged.zone_assumed = False
    folded = fold(message)
    if re.search(r"mais barat", folded):
        base = last_price if last_price is not None else (merged.max_price or 40)
        merged.max_price = max(15.0, round(base - 8, 2))
    if re.search(r"mais rapid", folded):
        merged.max_prep = 12
    if re.search(r"\b(outra|outro|troca)\b", folded) and last_id:
        merged.exclude_ids = [last_id]
    merged.wants_order = True
    return merged
