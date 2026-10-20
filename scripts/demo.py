"""End-to-end demo: scan the sample fridge photos and print the shopping list."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sloth_fridge import planner
from sloth_fridge.digest import morning_digest
from sloth_fridge.extractor import (
    ScanOptions,
    extract_fridge_items,
    extract_receipt_items,
)
from sloth_fridge.imaging import hash_bytes, load_image_bytes
from sloth_fridge.normalize import canonicalize_name
from sloth_fridge.ollama_client import OllamaClient
from sloth_fridge.store import Store

SAMPLES = sorted((Path(__file__).resolve().parents[1] / "sample_photos").glob("*.jpg"))


def main() -> int:
    client = OllamaClient()
    store = Store()
    options = ScanOptions(grid=3, include_full=True, verify=True)

    for path in SAMPLES:
        print(f"scanning {path.name} ...")
        started = time.time()
        data = load_image_bytes(path)
        sha = hash_bytes(data)
        if store.photo_exists(sha):
            print("  already scanned, skipping")
            continue
        photo_id = store.add_photo(sha, str(path), kind="fridge")
        items = extract_fridge_items(client, data, options=options)
        store.mark_photo_processed(photo_id, items)
        store.apply_pantry_scan(photo_id, items)
        print(f"  {len(items)} item(s) in {time.time() - started:.0f}s")
        for item in items:
            print(f"    - {item['name']} x{item['qty']:g} {item['unit']} [{item['category']}]")

    items = planner.build_list(store)
    print()
    print(planner.render_plain(items))
    print()
    print("Morning digest")
    print(morning_digest(store, client))
    print()
    print("Now a receipt: everything on it gets ticked off and stocked in the pantry.")
    receipt = Path(__file__).resolve().parents[1] / "sample_photos" / "receipt.png"
    if receipt.exists():
        for item in extract_receipt_items(client, load_image_bytes(receipt)):
            canonical = canonicalize_name(item["name"])
            if not canonical:
                continue
            row = store.mark_bought(canonical)
            store.stock_item(
                canonical,
                canonical,
                float(row["qty"]) if row is not None else float(item["qty"]),
                row["unit"] if row is not None else item["unit"],
                row["category"] if row is not None else item["category"],
            )
            print(f"    bought {canonical}")
    print()
    print("Shopping list after the receipt")
    print(planner.render_plain(planner.build_list(store)))
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
