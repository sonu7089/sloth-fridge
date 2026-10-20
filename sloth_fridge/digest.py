from __future__ import annotations

from . import config
from .ollama_client import OllamaClient
from .planner import build_list

DIGEST_SYSTEM = "You are a laconic assistant. You write extremely short summaries. You never pad."

DIGEST_PROMPT = """Here is the current state of someone's kitchen.

Shopping list:
{list_text}

Pantry snapshot (in stock): {pantry_text}

Write exactly two short lines for the person who opens their eyes in the morning.
Line 1: what they need to pick up, in the most natural phrasing.
Line 2: one encouraging, slightly funny observation about the fridge.
Rules: no bullet points, no numbering, no preamble, no quotes, maximum 90 characters per line, plain text only."""


def _fallback_digest(items: list[dict], pantry_count: int) -> str:
    if not items:
        return f"Fridge scan: nothing to buy, {pantry_count} things still in there.\nThe fridge says you can go back to sleep."
    names = ", ".join(item["name"] for item in items[:6])
    extra = f" and {len(items) - 6} more" if len(items) > 6 else ""
    return f"Grab: {names}{extra}.\nYour fridge is running on fumes and low effort, same as you."


def morning_digest(store, client: OllamaClient | None = None, model: str | None = None) -> str:
    items = build_list(store)
    pantry = store.pantry_items(state="in_stock")
    pantry_text = ", ".join(f"{row['canonical']} x{row['qty']}" for row in pantry) or "nothing detected"
    if client is None:
        return _fallback_digest(items, len(pantry))
    try:
        raw = client.chat(
            model or config.TEXT_MODEL,
            DIGEST_PROMPT.format(list_text=_plain(items), pantry_text=pantry_text),
            system=DIGEST_SYSTEM,
            temperature=0.3,
            num_predict=120,
        )
    except Exception:
        return _fallback_digest(items, len(pantry))
    lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
    if not lines:
        return _fallback_digest(items, len(pantry))
    while len(lines) < 2:
        lines.append(_fallback_digest(items, len(pantry)).splitlines()[1])
    return "\n".join(lines[:2])


def _plain(items: list[dict]) -> str:
    if not items:
        return "(empty)"
    return "\n".join(f"- {item['name']} x{item['qty']} {item['unit']} ({item['reason']})" for item in items)


PLAN_SYSTEM = "You are a practical home cook. You suggest simple meals that use up food that is about to go bad."

PLAN_PROMPT = """Someone's fridge contains:
{pantry_text}

Things they need to buy:
{list_text}

Suggest exactly 3 simple meals that use the ingredients most likely to spoil first.
One meal per line, format: "Meal name - ingredients used". Maximum 100 characters per line, plain text only, no numbering, no preamble."""


def use_up_plan(store, client: OllamaClient | None = None, model: str | None = None) -> str:
    items = build_list(store)
    pantry = store.pantry_items(state="in_stock")
    pantry_text = ", ".join(f"{row['canonical']} x{row['qty']}" for row in pantry) or "nothing detected"
    if client is None:
        return "Install Ollama and pull a text model to get meal suggestions."
    try:
        raw = client.chat(
            model or config.TEXT_MODEL,
            PLAN_PROMPT.format(pantry_text=pantry_text, list_text=_plain(items)),
            system=PLAN_SYSTEM,
            temperature=0.4,
            num_predict=200,
        )
    except Exception as exc:
        return f"Could not generate a plan: {exc}"
    lines = [line.strip() for line in raw.strip().splitlines() if line.strip()][:3]
    return "\n".join(lines) if lines else "No plan generated."
