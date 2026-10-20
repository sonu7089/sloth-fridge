from sloth_fridge.normalize import (
    canonicalize_name,
    canonicalize_unit,
    clean_name,
    infer_category,
    is_specific_name,
    units_compatible,
)


def test_singularizes_and_strips_accents():
    assert canonicalize_name("Tomatoes") == "tomato"
    assert canonicalize_name("Crème fraîche") == "creme fraiche"
    assert canonicalize_name("Bananas") == "banana"


def test_known_synonyms_collapse():
    assert canonicalize_name("Whole Milk") == "milk"
    assert canonicalize_name("2% milk") == "milk"
    assert canonicalize_name("Greek yoghurt") == "yogurt"
    assert canonicalize_name("ground beef") == "beef"
    assert canonicalize_name("Egg") == "eggs"


def test_brand_tokens_are_dropped():
    assert canonicalize_name("Kikkoman soy sauce") == "soy sauce"
    assert canonicalize_name("Heinz ketchup") == "tomato ketchup"
    assert canonicalize_name("Kirkland Signature mayonnaise") == "mayo"


def test_units_normalise_to_families():
    assert canonicalize_unit("Cans") == "container"
    assert canonicalize_unit("btl") == "container"
    assert canonicalize_unit("pcs") == "piece"
    assert canonicalize_unit("") == "piece"


def test_units_compatible_across_synonyms():
    assert units_compatible("carton", "container")
    assert units_compatible("bottle", "container")
    assert not units_compatible("piece", "container")


def test_category_inference():
    assert infer_category("milk") == "dairy"
    assert infer_category("chicken breast") == "meat"
    assert infer_category("spinach") == "produce"
    assert infer_category("feta cheese") == "dairy"
    assert infer_category("unobtainium") == "other"


def test_stated_category_wins():
    assert infer_category("milk", "produce") == "produce"
    assert infer_category("milk", "nonsense") == "dairy"


def test_clean_name_strips_containers_and_brands():
    assert canonicalize_name(clean_name("jar of pickles")) == "pickle"
    assert canonicalize_name(clean_name("unopened bottle of mustard, yellow label")) == "mustard"
    assert clean_name("bottle with red cap") == "red cap"


def test_receipt_lines_canonicalise():
    assert canonicalize_name("whole milk 1l") == "milk"
    assert canonicalize_name("greek yogurt 500g") == "yogurt"
    assert canonicalize_name("free range eggs 12") == "eggs"
    assert canonicalize_name("cheddar cheese block") == "cheese"
    assert canonicalize_name("sourdough loaf") == "bread"
    assert canonicalize_name("bananas 1kg") == "banana"
    assert canonicalize_name("lime 4 pack") == "lime"
    assert canonicalize_name("olive oil 500ml") == "olive oil"
    assert canonicalize_name("coffee beans 250g") == "coffee"
    assert canonicalize_name("6 pack eggs") == "eggs"


def test_container_phrases_are_stripped():
    assert canonicalize_name("loaf of bread") == "bread"
    assert canonicalize_name("slice of cheese") == "cheese"
    assert canonicalize_name("piece of chicken") == "chicken"
    assert canonicalize_name("bottle of hot sauce") == "hot sauce"


def test_staple_thresholds_drive_the_list():
    import tempfile
    from pathlib import Path

    from sloth_fridge.planner import build_list
    from sloth_fridge.store import Store

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.db")
        photo = store.add_photo("x", "x.jpg")
        store.apply_pantry_scan(photo, [
            {"canonical": "eggs", "name": "eggs", "qty": 12, "unit": "piece", "category": "eggs", "confidence": 0.9},
        ])
        items = build_list(store)
        assert "eggs" not in {item["canonical"] for item in items}
        store.close()


def test_specificity_rejects_vague_labels():
    assert is_specific_name("milk")
    assert is_specific_name("hot sauce")
    assert not is_specific_name("unspecified container")
    assert not is_specific_name("bottle or")
    assert not is_specific_name("citrus-based product")
    assert not is_specific_name("white plastic tub")
    assert not is_specific_name("yellow lid")
