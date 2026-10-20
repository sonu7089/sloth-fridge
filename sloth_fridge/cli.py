from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import config, planner
from .digest import morning_digest, use_up_plan
from .extractor import extract_fridge_items, extract_receipt_items
from .imaging import hash_bytes, load_image_bytes
from .normalize import canonicalize_name, canonicalize_unit, infer_category
from .ollama_client import OllamaClient, OllamaError
from .store import Store

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def _store() -> Store:
    return Store()


def _client(model: str | None = None) -> OllamaClient:
    return OllamaClient()


def cmd_doctor(args: argparse.Namespace) -> int:
    client = _client()
    print(f"data dir : {config.data_dir()}")
    print(f"database : {config.db_path()}")
    print(f"ollama   : {client.host} (v{client.version()})")
    if not client.host.startswith("http://127.0.0.1") and not client.host.startswith("http://localhost"):
        print("          WARNING: this host is not loopback. Your photos would leave this machine.")
    try:
        models = client.list_models()
        print(f"models   : {', '.join(models) if models else 'none installed'}")
    except OllamaError as exc:
        print(f"ollama   : NOT REACHABLE -> {exc}")
        print()
        print("Install it with:  winget install --id Ollama.Ollama -e")
        print("Then pull the models:")
        print(f"  ollama pull {config.VISION_MODEL}")
        print(f"  ollama pull {config.TEXT_MODEL}")
        return 1
    for label, model in (("vision", config.VISION_MODEL), ("text", config.TEXT_MODEL)):
        state = "present" if client.has_model(model) else "MISSING"
        print(f"{label:<9}: {model} -> {state}")
    print()
    print("Everything runs on this machine. No photo leaves your computer.")
    print("Set OLLAMA_NO_CLOUD=1 to keep Ollama fully offline.")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    store = _store()
    client = _client()
    model = args.model or config.VISION_MODEL
    photos = _collect_photos(args.paths)
    if not photos:
        print("No images found.")
        return 1
    for path in photos:
        data = load_image_bytes(path)
        sha = hash_bytes(data)
        if store.photo_exists(sha) and not args.force:
            print(f"skip (already scanned): {path}")
            continue
        photo_id = store.add_photo(sha, str(path), kind="fridge")
        try:
            items = extract_fridge_items(client, data, model=model)
        except OllamaError as exc:
            print(f"error on {path}: {exc}")
            return 1
        store.mark_photo_processed(photo_id, items)
        store.apply_pantry_scan(photo_id, items)
        print(f"scanned {path} -> {len(items)} item(s)")
        for item in items:
            votes = f" (seen in {item['votes']} views)" if item.get("votes") else ""
            print(f"   - {item['name']} x{item['qty']:g} {item['unit']} [{item['category']}]{votes}")
    items = planner.build_list(store)
    print()
    print(planner.render_plain(items))
    return 0


def cmd_receipt(args: argparse.Namespace) -> int:
    store = _store()
    client = _client()
    model = args.model or config.VISION_MODEL
    photos = _collect_photos(args.paths)
    if not photos:
        print("No images found.")
        return 1
    for path in photos:
        data = load_image_bytes(path)
        sha = hash_bytes(data)
        photo_id = store.add_photo(sha, str(path), kind="receipt")
        try:
            items = extract_receipt_items(client, data, model=model)
        except OllamaError as exc:
            print(f"error on {path}: {exc}")
            return 1
        store.mark_photo_processed(photo_id, items)
        for item in items:
            canonical = canonicalize_name(item["name"])
            if not canonical:
                continue
            matched = store.mark_bought(canonical)
            if matched is not None:
                store.stock_item(
                    canonical,
                    canonical,
                    float(matched["qty"]),
                    matched["unit"],
                    matched["category"],
                )
            else:
                store.stock_item(
                    canonical,
                    canonical,
                    float(item["qty"]),
                    item["unit"],
                    item["category"],
                )
        print(f"receipt {path} -> {len(items)} line(s)")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    store = _store()
    items = planner.build_list(store, include_missing=not args.hide_missing)
    if args.format == "json":
        print(json.dumps(items, indent=2))
    elif args.format == "markdown":
        print(planner.render_markdown(items))
    else:
        print(planner.render_plain(items))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    store = _store()
    canonical = canonicalize_name(args.name)
    if not canonical:
        print("Could not understand that item name.")
        return 1
    unit = canonicalize_unit(args.unit or "piece")
    category = infer_category(canonical, args.category)
    store.upsert_grocery(
        canonical=canonical,
        name=canonical,
        qty=float(args.qty),
        unit=unit,
        category=category,
        reason=args.reason or "added by hand",
        source="manual",
    )
    print(f"added {canonical} x{args.qty} {unit}")
    return 0


def cmd_bought(args: argparse.Namespace) -> int:
    store = _store()
    canonical = canonicalize_name(args.name)
    row = store.mark_bought(canonical)
    if row is None:
        print(f"{canonical} was not on the list")
        return 1
    store.stock_item(
        row["canonical"],
        row["name"],
        float(row["qty"]),
        row["unit"],
        row["category"],
    )
    print(f"checked off {canonical} (and stocked the pantry)")
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    store = _store()
    canonical = canonicalize_name(args.name)
    if store.remove_grocery(canonical):
        print(f"removed {canonical}")
        return 0
    print(f"{canonical} was not on the list")
    return 1


def cmd_clear(args: argparse.Namespace) -> int:
    store = _store()
    store.clear_grocery()
    print("shopping list cleared")
    return 0


def cmd_pantry(args: argparse.Namespace) -> int:
    store = _store()
    rows = store.pantry_items()
    if not rows:
        print("Pantry is empty. Run `sloth-fridge scan <photo>`.")
        return 0
    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row["category"], []).append(row)
    for category in config.CATEGORY_ORDER:
        if category not in groups:
            continue
        print(category.upper())
        for row in groups[category]:
            marker = " " if row["state"] == "in_stock" else "?"
            print(f" {marker} {row['canonical']} x{row['qty']} {row['unit']}  (seen {row['seen_count']}x)")
        print()
    return 0


def cmd_staples(args: argparse.Namespace) -> int:
    store = _store()
    for staple in store.staples():
        count, _ = store.count_pantry(staple["canonical"], staple["unit"])
        state = "ok" if count > float(staple["threshold"]) else "LOW"
        print(f"[{state}] {staple['canonical']:<12} have {count:g} {staple['unit']}, restock at {staple['threshold']:g}")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    store = _store()
    client = _client()
    try:
        print(morning_digest(store, client))
    except OllamaError as exc:
        print(f"error: {exc}")
        return 1
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    store = _store()
    client = _client()
    print(use_up_plan(store, client))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    store = _store()
    items = planner.build_list(store)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(planner.render_markdown(items), encoding="utf-8")
    print(f"wrote {target}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    watch_dir = Path(args.directory)
    watch_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    client = _client()
    model = args.model or config.VISION_MODEL
    print(f"watching {watch_dir} for new fridge photos (ctrl-c to stop)")
    while True:
        try:
            for path in sorted(watch_dir.iterdir()):
                if path.suffix.lower() not in IMAGE_SUFFIXES or path.name in seen:
                    continue
                seen.add(path.name)
                data = load_image_bytes(path)
                sha = hash_bytes(data)
                store = _store()
                if store.photo_exists(sha):
                    continue
                photo_id = store.add_photo(sha, str(path), kind="fridge")
                try:
                    items = extract_fridge_items(client, data, model=model)
                except OllamaError as exc:
                    print(f"error on {path}: {exc}")
                    continue
                store.mark_photo_processed(photo_id, items)
                store.apply_pantry_scan(photo_id, items)
                print(f"[{time.strftime('%H:%M')}] scanned {path.name} -> {len(items)} item(s)")
                store.close()
        except KeyboardInterrupt:
            print("\nstopped")
            return 0
        time.sleep(args.interval)


def _collect_photos(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES))
        elif path.exists():
            found.append(path)
    return found


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sloth-fridge", description="Fridge photo to grocery list, locally.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check Ollama and model availability").set_defaults(func=cmd_doctor)
    sub.add_parser("init", help="create the local database and config").set_defaults(func=cmd_init)

    scan = sub.add_parser("scan", help="scan fridge photos")
    scan.add_argument("paths", nargs="+")
    scan.add_argument("--model", default=None)
    scan.add_argument("--force", action="store_true", help="rescan photos already seen")
    scan.set_defaults(func=cmd_scan)

    receipt = sub.add_parser("receipt", help="read receipts and mark items bought")
    receipt.add_argument("paths", nargs="+")
    receipt.add_argument("--model", default=None)
    receipt.set_defaults(func=cmd_receipt)

    listing = sub.add_parser("list", help="show the shopping list")
    listing.add_argument("--format", choices=["plain", "markdown", "json"], default="plain")
    listing.add_argument("--hide-missing", action="store_true")
    listing.set_defaults(func=cmd_list)

    add = sub.add_parser("add", help="add an item to the list by hand")
    add.add_argument("name")
    add.add_argument("-q", "--qty", type=float, default=1)
    add.add_argument("-u", "--unit", default="piece")
    add.add_argument("-c", "--category", default=None)
    add.add_argument("-r", "--reason", default=None)
    add.set_defaults(func=cmd_add)

    bought = sub.add_parser("bought", help="check an item off the list")
    bought.add_argument("name")
    bought.set_defaults(func=cmd_bought)

    remove = sub.add_parser("rm", help="remove an item from the list")
    remove.add_argument("name")
    remove.set_defaults(func=cmd_rm)

    sub.add_parser("clear", help="clear the shopping list").set_defaults(func=cmd_clear)

    pantry = sub.add_parser("pantry", help="show the last fridge snapshot")
    pantry.set_defaults(func=cmd_pantry)

    sub.add_parser("staples", help="show staple levels").set_defaults(func=cmd_staples)
    sub.add_parser("digest", help="two-line morning summary").set_defaults(func=cmd_digest)
    sub.add_parser("plan", help="meals that use up what is about to spoil").set_defaults(func=cmd_plan)

    export = sub.add_parser("export", help="write the list to a markdown file")
    export.add_argument("output")
    export.set_defaults(func=cmd_export)

    watch = sub.add_parser("watch", help="poll a folder and scan new photos")
    watch.add_argument("directory")
    watch.add_argument("--interval", type=int, default=20)
    watch.add_argument("--model", default=None)
    watch.set_defaults(func=cmd_watch)

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    store = _store()
    store.close()
    print(f"initialised {config.data_dir()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except OllamaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
