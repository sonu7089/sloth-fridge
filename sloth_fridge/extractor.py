from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .imaging import crop_views, extract_json
from .normalize import (
    canonicalize_name,
    clean_name,
    is_specific_name,
    normalize_item,
)
from .ollama_client import OllamaClient

VISION_SYSTEM = (
    "You are a careful kitchen inventory assistant. You look at photos of a refrigerator "
    "and report only what you can actually see. You never invent items."
)

DESCRIBE_PROMPT = """Look at this photo of a refrigerator shelf. Tell me which food and drink items you can actually see.
Describe the shelf, then list each item by name and how many of it you see.
Only mention items that are clearly visible. If you cannot see any food, say so."""

EXTRACT_SYSTEM = "You turn refrigerator descriptions into tidy ingredient lists. You only use foods that are mentioned."

EXTRACT_PROMPT = """Extract the food items from this description of one part of a refrigerator.

{text}

Return only JSON: {{"items": [{{"name": "...", "qty": 1, "unit": "piece|pack|container|bunch|loaf|slice", "category": "produce|dairy|meat|seafood|eggs|bread|frozen|pantry_staple|beverage|condiment|snack|other", "confidence": 0.8}}]}}

Rules:
- Use only foods that are actually mentioned in the description. Never add a food that is not mentioned.
- name: the food as a shopper would say it, lowercase, no brand prefix.
- qty: how many are described. Default 1.
- unit: piece for individual items like eggs, fruit, vegetables and bottles. pack for boxes and bags. container for jars, tubs and cans. bunch for herbs and bananas. loaf for bread.
- category: produce, dairy, meat, seafood, eggs, bread, frozen, pantry_staple, beverage, condiment, snack or other.
- confidence: how sure you are the food is really there, between 0 and 1.
- Skip shelves, lids, caps, labels, containers and packaging."""

VERIFY_PROMPT = "Look carefully at this refrigerator photo. Is there {name} in it? Answer with only yes or no."

RECEIPT_SYSTEM = (
    "You are a receipt reader for a grocery list app. You read a photo of a receipt and "
    "list the purchased products. You never invent products that are not printed."
)

RECEIPT_PROMPT = """Read this photo of a grocery receipt and list the food products that were bought.

Rules:
- Only list lines that are clearly printed on the receipt. Skip store totals, taxes, card numbers, loyalty numbers, coupons and barcodes.
- Skip non-food items such as detergent, paper bags, batteries or plastic cutlery.
- name: the product as printed, lowercased, no brand prefix unless needed to tell products apart.
- qty: the quantity printed, use 1 if only a price is shown.
- category must be one of: {categories}.
- confidence is how sure you are the line was read correctly, between 0 and 1.
- If the image is not a receipt, return an empty items list.

Return only JSON: {{"items": [{{"name": "oat milk", "qty": 2, "unit": "container", "category": "dairy", "confidence": 0.85}}]}}""".format(
    categories=", ".join(config.CATEGORIES)
)

EXPIRY_PATTERN = ("expiry", "expires", "use by", "use-by", "best before", "bb", "exp ")

MAX_PLAUSIBLE_QTY = 24
MAX_QTY = 12


def looks_like_expiry(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in EXPIRY_PATTERN)


def _coerce(payload: object, max_qty: float | None = None) -> list[dict]:
    if isinstance(payload, dict):
        items = payload.get("items", payload.get("products", payload.get("lines", [])))
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    if not isinstance(items, list):
        return []
    cleaned: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = normalize_item(raw)
        if item is None:
            continue
        if max_qty is not None and item["qty"] > max_qty:
            item["qty"] = 1.0
        expiry = str(raw.get("expiry_text", "") or "").strip()
        item["expiry_text"] = expiry if looks_like_expiry(expiry) else ""
        cleaned.append(item)
    return cleaned


@dataclass
class ScanOptions:
    grid: int = 3
    include_full: bool = True
    verify: bool = True
    max_items: int = 40
    text_model: str | None = None


@dataclass
class Vote:
    canonical: str = ""
    name: str = ""
    qty: float = 0.0
    unit: str = "piece"
    category: str = "other"
    confidence: float = 0.0
    views: int = 0
    labels: list[str] = field(default_factory=list)
    verified: bool | None = None


def _canonical_for(name: str) -> str:
    cleaned = clean_name(name)
    if not cleaned:
        return ""
    if " or " in cleaned:
        parts = [part for part in cleaned.split(" or ") if part.strip()]
        cleaned = parts[0] if parts else ""
    canonical = canonicalize_name(cleaned)
    if not canonical or not is_specific_name(canonical):
        return ""
    return canonical


def _merge_votes(votes: dict[str, Vote], items: list[dict], view_label: str) -> None:
    for item in items:
        canonical = _canonical_for(item.get("name", ""))
        if not canonical:
            continue
        vote = votes.get(canonical)
        if vote is None:
            vote = Vote(canonical=canonical)
            votes[canonical] = vote
        vote.views += 1
        vote.labels.append(view_label)
        vote.name = canonical
        vote.category = item["category"]
        vote.unit = item["unit"]
        if item["confidence"] > vote.confidence:
            vote.confidence = item["confidence"]
            vote.qty = item["qty"]
        elif vote.qty < item["qty"] and item["qty"] <= MAX_PLAUSIBLE_QTY:
            vote.qty = item["qty"]


def _describe(client: OllamaClient, model: str, payload: bytes) -> str:
    import base64

    data_url = base64.b64encode(payload).decode("ascii")
    return client.chat(
        model,
        DESCRIBE_PROMPT,
        system=VISION_SYSTEM,
        images=[data_url],
        temperature=0.3,
        num_predict=300,
        options={"repeat_penalty": 1.15, "top_p": 0.9},
    )


def _extract_from_text(client: OllamaClient, text: str, text_model: str) -> list[dict]:
    raw = client.chat(
        text_model,
        EXTRACT_PROMPT.format(text=text),
        system=EXTRACT_SYSTEM,
        json_mode=True,
        temperature=0.1,
        num_predict=1200,
        options={"repeat_penalty": 1.1},
    )
    parsed = extract_json(raw)
    if parsed is None:
        return []
    return _coerce(parsed)


def _verify(client: OllamaClient, model: str, payload: bytes, name: str) -> bool:
    import base64

    data_url = base64.b64encode(payload).decode("ascii")
    try:
        raw = client.chat(
            model,
            VERIFY_PROMPT.format(name=name),
            images=[data_url],
            temperature=0.1,
            num_predict=8,
        )
    except Exception:
        return True
    answer = raw.strip().lower()
    if answer.startswith("yes"):
        return True
    if answer.startswith("no"):
        return False
    return True


def _finalize(votes: dict[str, Vote], options: ScanOptions) -> list[dict]:
    results: list[dict] = []
    for vote in votes.values():
        if vote.qty > MAX_PLAUSIBLE_QTY:
            continue
        qty = min(vote.qty, MAX_QTY)
        if qty <= 0:
            qty = 1.0
        confidence = vote.confidence
        if vote.views == 1:
            confidence *= 0.8
        if vote.verified is False:
            confidence *= 0.5
        results.append(
            {
                "name": vote.name,
                "canonical": vote.canonical,
                "qty": qty,
                "unit": vote.unit,
                "category": vote.category,
                "confidence": round(max(0.0, min(1.0, confidence)), 3),
                "votes": vote.views,
                "views": vote.labels,
                "verified": vote.verified,
            }
        )
    results.sort(key=lambda item: (-item["votes"], -item["confidence"], item["canonical"]))
    return results[: options.max_items]


def extract_fridge_items(
    client: OllamaClient,
    image_payload: bytes,
    model: str | None = None,
    options: ScanOptions | None = None,
    progress=None,
) -> list[dict]:
    options = options or ScanOptions()
    model = model or config.VISION_MODEL
    text_model = options.text_model or config.TEXT_MODEL

    views = crop_views(image_payload, grid=options.grid, include_full=options.include_full)
    votes: dict[str, Vote] = {}
    described: list[tuple[str, bytes, str]] = []

    for label, payload in views:
        try:
            description = _describe(client, model, payload)
        except Exception:
            continue
        if not description.strip():
            continue
        described.append((label, payload, description.strip()))
        if progress:
            progress(label, description.strip())

    if not described:
        return []

    for label, _payload, description in described:
        try:
            items = _extract_from_text(client, description, text_model)
        except Exception:
            items = []
        if items:
            _merge_votes(votes, items, label)

    if options.verify and described:
        full_payload = described[0][1]
        for vote in votes.values():
            if vote.views == 1:
                vote.verified = _verify(client, model, full_payload, vote.canonical)

    return _finalize(votes, options)


def extract_receipt_items(client: OllamaClient, image_payload: bytes, model: str | None = None) -> list[dict]:
    import base64

    data_url = base64.b64encode(image_payload).decode("ascii")
    raw = client.chat(
        model or config.VISION_MODEL,
        RECEIPT_PROMPT,
        system=RECEIPT_SYSTEM,
        images=[data_url],
        json_mode=True,
        temperature=0.1,
        num_predict=900,
        options={"repeat_penalty": 1.1},
    )
    parsed = extract_json(raw)
    if parsed is None:
        return []
    return _coerce(parsed, max_qty=12)
