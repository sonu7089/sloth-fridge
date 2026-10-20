from __future__ import annotations

from .config import CATEGORY_ORDER
from .store import Store

REASON_MISSING = "not seen in the latest scan"


def _auto_item(store: Store, canonical: str, qty: float, unit: str, category: str, reason: str) -> None:
    store.upsert_grocery(
        canonical=canonical,
        name=canonical,
        qty=qty,
        unit=unit,
        category=category,
        reason=reason,
        source="auto",
    )


def rebuild_auto_items(store: Store, include_missing: bool = True, min_confidence: float = 0.55) -> None:
    store.conn.execute("DELETE FROM grocery_items WHERE source = 'auto' AND status = 'needed'")
    store.conn.commit()

    for staple in store.staples():
        count, _exact = store.count_pantry(staple["canonical"], staple["unit"])
        threshold = float(staple["threshold"])
        buy_qty = float(staple["buy_qty"])
        if count >= threshold:
            continue
        if count <= 0:
            reason = "out of stock"
        else:
            reason = f"running low ({_fmt(count)} {staple['unit']} left)"
        _auto_item(store, staple["canonical"], buy_qty, staple["unit"], staple["category"], reason)

    if include_missing:
        for row in store.pantry_items(state="not_seen"):
            if row["seen_count"] < 1:
                continue
            if row["confidence"] < min_confidence:
                continue
            if store.conn.execute(
                "SELECT id FROM grocery_items WHERE canonical = ? AND status = 'needed'", (row["canonical"],)
            ).fetchone():
                continue
            _auto_item(
                store,
                row["canonical"],
                float(row["qty"]),
                row["unit"],
                row["category"],
                REASON_MISSING,
            )
    store.conn.commit()


def _fmt(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.1f}"


def build_list(store: Store, include_missing: bool = True) -> list[dict]:
    rebuild_auto_items(store, include_missing=include_missing)
    rows = store.grocery_items()
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "canonical": row["canonical"],
                "name": row["name"],
                "qty": row["qty"],
                "unit": row["unit"],
                "category": row["category"],
                "reason": row["reason"] or "",
                "source": row["source"],
            }
        )
    items.sort(key=lambda item: (CATEGORY_ORDER.index(item["category"]) if item["category"] in CATEGORY_ORDER else 99, item["canonical"]))
    return items


def group_by_aisle(items: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item["category"], []).append(item)
    ordered = [category for category in CATEGORY_ORDER if category in grouped]
    return [(category, grouped[category]) for category in ordered]


def render_markdown(items: list[dict], title: str = "Shopping list") -> str:
    lines = [f"# {title}", ""]
    for category, category_items in group_by_aisle(items):
        lines.append(f"## {category.replace('_', ' ').title()}")
        for item in category_items:
            reason = f"  <!-- {item['reason']} -->" if item["reason"] else ""
            lines.append(f"- [ ] {item['name']} — {_fmt(item['qty'])} {item['unit']}{reason}")
        lines.append("")
    if not items:
        lines.append("_Nothing to buy. The fridge is looking smug._")
        lines.append("")
    return "\n".join(lines)


def render_plain(items: list[dict]) -> str:
    lines = []
    for category, category_items in group_by_aisle(items):
        lines.append(f"{category.upper()}")
        for item in category_items:
            reason = f"  ({item['reason']})" if item["reason"] else ""
            lines.append(f"  [ ] {item['name']} x{_fmt(item['qty'])} {item['unit']}{reason}")
        lines.append("")
    if not items:
        lines.append("Nothing to buy. The fridge is looking smug.")
    return "\n".join(lines).rstrip()
