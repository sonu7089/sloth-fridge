import pytest

from sloth_fridge.planner import (
    build_list,
    group_by_aisle,
    render_markdown,
    render_plain,
)
from sloth_fridge.store import Store


@pytest.fixture()
def store(tmp_path):
    store = Store(tmp_path / "test.db")
    yield store
    store.close()


def _scan(store, items):
    photo = store.add_photo("hash", "photo.jpg")
    store.apply_pantry_scan(photo, items)


def test_out_of_stock_staple_lands_on_the_list(store):
    _scan(store, [
        {"canonical": "milk", "name": "milk", "qty": 2, "unit": "container", "category": "dairy", "confidence": 0.9},
    ])
    items = build_list(store)
    names = {item["canonical"] for item in items}
    assert "milk" not in names
    assert "eggs" in names
    eggs = next(item for item in items if item["canonical"] == "eggs")
    assert "stock" in eggs["reason"]


def test_running_low_staple_lands_on_the_list(store):
    _scan(store, [
        {"canonical": "eggs", "name": "eggs", "qty": 2, "unit": "piece", "category": "eggs", "confidence": 0.9},
    ])
    items = build_list(store)
    eggs = next(item for item in items if item["canonical"] == "eggs")
    assert "low" in eggs["reason"]


def test_well_stocked_staple_is_left_off_the_list(store):
    _scan(store, [
        {"canonical": "milk", "name": "milk", "qty": 4, "unit": "container", "category": "dairy", "confidence": 0.9},
        {"canonical": "eggs", "name": "eggs", "qty": 12, "unit": "piece", "category": "eggs", "confidence": 0.9},
    ])
    items = build_list(store)
    names = {item["canonical"] for item in items}
    assert "milk" not in names
    assert "eggs" not in names


def test_bought_item_is_stocked_in_the_pantry(store):
    store.upsert_grocery("milk", "milk", 2, "container", "dairy", "running low", "auto")
    row = store.mark_bought("milk")
    assert row is not None
    store.stock_item(row["canonical"], row["name"], float(row["qty"]), row["unit"], row["category"])
    items = build_list(store)
    assert "milk" not in {item["canonical"] for item in items}


def test_manual_items_survive_an_auto_rebuild(store):
    store.upsert_grocery("chocolate", "chocolate", 1, "piece", "snack", "added by hand", "manual")
    build_list(store)
    items = build_list(store)
    assert "chocolate" in {item["canonical"] for item in items}


def test_items_missing_from_the_latest_scan_are_suggested(store):
    first = store.add_photo("one", "one.jpg")
    store.apply_pantry_scan(first, [
        {"canonical": "pickle", "name": "pickle", "qty": 1, "unit": "jar", "category": "produce", "confidence": 0.9},
    ])
    second = store.add_photo("two", "two.jpg")
    store.apply_pantry_scan(second, [
        {"canonical": "milk", "name": "milk", "qty": 1, "unit": "container", "category": "dairy", "confidence": 0.9},
    ])
    items = build_list(store, include_missing=True)
    pickle = next((item for item in items if item["canonical"] == "pickle"), None)
    assert pickle is not None
    assert "not seen" in pickle["reason"]


def test_hiding_missing_items_drops_them(store):
    first = store.add_photo("one", "one.jpg")
    store.apply_pantry_scan(first, [
        {"canonical": "pickle", "name": "pickle", "qty": 1, "unit": "jar", "category": "produce", "confidence": 0.9},
    ])
    second = store.add_photo("two", "two.jpg")
    store.apply_pantry_scan(second, [
        {"canonical": "milk", "name": "milk", "qty": 1, "unit": "container", "category": "dairy", "confidence": 0.9},
    ])
    items = build_list(store, include_missing=False)
    assert "pickle" not in {item["canonical"] for item in items}


def test_list_is_grouped_by_aisle(store):
    store.upsert_grocery("milk", "milk", 1, "container", "dairy", "low", "manual")
    store.upsert_grocery("apple", "apple", 2, "piece", "produce", "low", "manual")
    items = build_list(store)
    grouped = group_by_aisle(items)
    categories = [category for category, _ in grouped]
    assert categories.index("produce") < categories.index("dairy")


def test_markdown_renders_a_checklist(store):
    store.upsert_grocery("milk", "milk", 1, "container", "dairy", "out of stock", "manual")
    items = build_list(store)
    markdown = render_markdown(items)
    assert "# Shopping list" in markdown
    assert "- [ ] milk" in markdown
    assert "## Dairy" in markdown


def test_plain_render_of_an_empty_list():
    assert "Nothing to buy" in render_plain([])
