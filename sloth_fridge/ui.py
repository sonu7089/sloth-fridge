from __future__ import annotations

import streamlit as st

from sloth_fridge import config, planner
from sloth_fridge.digest import morning_digest
from sloth_fridge.extractor import extract_fridge_items, extract_receipt_items
from sloth_fridge.imaging import hash_bytes
from sloth_fridge.normalize import canonicalize_name, canonicalize_unit, infer_category
from sloth_fridge.ollama_client import OllamaClient
from sloth_fridge.store import Store

st.set_page_config(page_title="Sloth Fridge", page_icon="🦥", layout="wide")


def get_store() -> Store:
    if "store" not in st.session_state:
        st.session_state.store = Store()
    return st.session_state.store


def get_client() -> OllamaClient:
    if "client" not in st.session_state:
        st.session_state.client = OllamaClient()
    return st.session_state.client


st.title("🦥 Sloth Fridge")
st.caption("Snap a photo of your fridge. Get a shopping list. Pay nothing. Send nothing to anybody.")

client = get_client()
store = get_store()

try:
    server_ok = client.version()
    st.sidebar.success(f"Ollama {server_ok} · {client.host}")
except Exception as exc:
    st.sidebar.error(f"Ollama unreachable: {exc}")
    server_ok = None

with st.sidebar:
    st.subheader("Model")
    vision_model = st.text_input("Vision model", value=config.VISION_MODEL)
    st.subheader("Staples")
    st.caption("Edit `staples.json` in your data dir to change thresholds.")

tab_scan, tab_list, tab_pantry = st.tabs(["📸 Scan", "🛒 List", "🫙 Pantry"])

with tab_scan:
    uploaded = st.file_uploader(
        "Fridge photo",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )
    receipt_upload = st.file_uploader(
        "Receipt photo (optional: marks items as bought)",
        type=["jpg", "jpeg", "png", "webp"],
    )

    if uploaded and server_ok:
        for file in uploaded:
            data = file.getvalue()
            sha = hash_bytes(data)
            if store.photo_exists(sha):
                st.info(f"already scanned: {file.name}")
                continue
            with st.spinner(f"Looking at {file.name}..."):
                photo_id = store.add_photo(sha, file.name, kind="fridge")
                try:
                    items = extract_fridge_items(client, data, model=vision_model)
                except Exception as exc:
                    st.error(f"could not read that photo: {exc}")
                    continue
                store.mark_photo_processed(photo_id, items)
                store.apply_pantry_scan(photo_id, items)
            st.success(f"{file.name}: {len(items)} item(s) found")
            for item in items:
                st.write(f"- {item['name']} x{item['qty']:g} {item['unit']} · {item['category']}")

    if receipt_upload and server_ok:
        for file in receipt_upload:
            data = file.getvalue()
            with st.spinner(f"Reading receipt {file.name}..."):
                photo_id = store.add_photo(hash_bytes(data), file.name, kind="receipt")
                try:
                    items = extract_receipt_items(client, data, model=vision_model)
                except Exception as exc:
                    st.error(f"could not read that receipt: {exc}")
                    continue
                store.mark_photo_processed(photo_id, items)
                for item in items:
                    canonical = canonicalize_name(item["name"])
                    if canonical:
                        row = store.mark_bought(canonical)
                        store.stock_item(
                            canonical,
                            canonical,
                            float(row["qty"]) if row is not None else float(item["qty"]),
                            row["unit"] if row is not None else item["unit"],
                            row["category"] if row is not None else item["category"],
                        )
            st.success(f"{file.name}: {len(items)} receipt line(s)")

with tab_list:
    items = planner.build_list(store)
    st.markdown(planner.render_markdown(items))
    with st.expander("Add something by hand"), st.form("add_item"):
        name = st.text_input("Item")
        qty = st.number_input("Quantity", min_value=0.5, value=1.0, step=0.5)
        unit = st.text_input("Unit", value="piece")
        if st.form_submit_button("Add to list") and name.strip():
            canonical = canonicalize_name(name)
            store.upsert_grocery(
                canonical,
                canonical,
                qty,
                canonicalize_unit(unit),
                infer_category(canonical),
                "added by hand",
                "manual",
            )
            st.rerun()
    if items:
        st.download_button(
            "Download as markdown",
            planner.render_markdown(items),
            file_name="shopping-list.md",
            mime="text/markdown",
        )

with tab_pantry:
    rows = store.pantry_items()
    if not rows:
        st.info("No fridge scan yet.")
    else:
        st.dataframe(
            [
                {
                    "item": row["canonical"],
                    "qty": row["qty"],
                    "unit": row["unit"],
                    "category": row["category"],
                    "state": row["state"],
                    "times seen": row["seen_count"],
                }
                for row in rows
            ],
            use_container_width=True,
        )

st.divider()
if server_ok:
    st.subheader("Morning digest")
    st.code(morning_digest(store, client), language=None)
