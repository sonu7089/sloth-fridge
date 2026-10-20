import pytest

from sloth_fridge.store import Store


@pytest.fixture()
def store(tmp_path):
    store = Store(tmp_path / "test.db")
    yield store
    store.close()


def test_photo_dedupe_by_hash(store):
    first = store.add_photo("abc", "a.jpg")
    second = store.add_photo("abc", "b.jpg")
    assert first == second
    assert store.photo_exists("abc")


def test_pantry_scan_marks_unseen_items(store):
    photo = store.add_photo("one", "one.jpg")
    store.apply_pantry_scan(photo, [
        {"canonical": "milk", "name": "milk", "qty": 1, "unit": "container", "category": "dairy", "confidence": 0.9},
        {"canonical": "eggs", "name": "eggs", "qty": 6, "unit": "piece", "category": "eggs", "confidence": 0.8},
    ])
    assert store.pantry_summary()["in_stock"] == 2

    photo2 = store.add_photo("two", "two.jpg")
    store.apply_pantry_scan(photo2, [
        {"canonical": "milk", "name": "milk", "qty": 1, "unit": "container", "category": "dairy", "confidence": 0.9},
    ])
    states = {row["canonical"]: row["state"] for row in store.pantry_items()}
    assert states["milk"] == "in_stock"
    assert states["eggs"] == "not_seen"


def test_seen_count_grows_across_scans(store):
    first = store.add_photo("a", "a.jpg")
    store.apply_pantry_scan(first, [
        {"canonical": "milk", "name": "milk", "qty": 1, "unit": "container", "category": "dairy", "confidence": 0.9},
    ])
    second = store.add_photo("b", "b.jpg")
    store.apply_pantry_scan(second, [
        {"canonical": "milk", "name": "milk", "qty": 1, "unit": "container", "category": "dairy", "confidence": 0.9},
    ])
    row = store.pantry_items()[0]
    assert row["seen_count"] == 2


def test_grocery_items_merge_instead_of_duplicating(store):
    store.upsert_grocery("milk", "milk", 1, "container", "dairy", "out of stock")
    store.upsert_grocery("milk", "milk", 2, "container", "dairy", "out of stock")
    rows = store.grocery_items()
    assert len(rows) == 1
    assert rows[0]["qty"] == 2


def test_mark_bought_removes_item_from_open_list(store):
    store.upsert_grocery("milk", "milk", 1, "container", "dairy", "out of stock")
    assert store.mark_bought("milk") is not None
    assert store.grocery_items() == []
    assert store.mark_bought("milk") is None


def test_stock_item_adds_to_the_pantry(store):
    store.stock_item("milk", "milk", 2, "container", "dairy")
    store.stock_item("milk", "milk", 1, "container", "dairy")
    count, exact = store.count_pantry("milk", "container")
    assert count == 3
    assert exact is True


def test_count_pantry_respects_unit_families(store):
    photo = store.add_photo("x", "x.jpg")
    store.apply_pantry_scan(photo, [
        {"canonical": "milk", "name": "milk", "qty": 2, "unit": "carton", "category": "dairy", "confidence": 0.9},
    ])
    count, exact = store.count_pantry("milk", "container")
    assert count == 2
    assert exact is False
