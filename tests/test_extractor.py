from sloth_fridge.extractor import (
    Vote,
    _canonical_for,
    _coerce,
    _finalize,
    _merge_votes,
)
from sloth_fridge.imaging import extract_json


def test_extract_json_from_plain_output():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_from_fenced_output():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_trailing_text():
    assert extract_json('here you go: {"a": 1} hope that helps') == {"a": 1}


def test_extract_json_repairs_trailing_comma():
    assert extract_json('{"a": 1,}') == {"a": 1}


def test_extract_json_returns_none_for_garbage():
    assert extract_json("not json at all") is None


def test_coerce_filters_unusable_rows():
    payload = {"items": [{"name": "milk", "qty": 1, "unit": "container"}, "nonsense", {"name": ""}]}
    items = _coerce(payload)
    assert len(items) == 1
    assert items[0]["canonical"] == "milk"


def test_canonical_for_rejects_vague_labels():
    assert _canonical_for("jar of pickles") == "pickle"
    assert _canonical_for("unspecified container") == ""
    assert _canonical_for("bottle or") == ""
    assert _canonical_for("") == ""


def test_canonical_for_picks_the_first_alternative():
    assert _canonical_for("syrup or honey") == "syrup"


def test_merge_votes_counts_views():
    votes = {}
    item = {"canonical": "milk", "name": "milk", "qty": 1, "unit": "container", "category": "dairy", "confidence": 0.9}
    _merge_votes(votes, [item], "r0c0")
    _merge_votes(votes, [item], "r1c1")
    assert votes["milk"].views == 2


def test_finalize_keeps_the_highest_confidence():
    votes = {}
    _merge_votes(votes, [{"canonical": "milk", "name": "milk", "qty": 1, "unit": "container", "category": "dairy", "confidence": 0.4}], "a")
    _merge_votes(votes, [{"canonical": "milk", "name": "milk", "qty": 2, "unit": "container", "category": "dairy", "confidence": 0.95}], "b")
    results = _finalize(votes, type("Opts", (), {"max_items": 10})())
    assert len(results) == 1
    assert results[0]["confidence"] == 0.95
    assert results[0]["qty"] == 2


def test_finalize_drops_implausible_quantities():
    votes = {"tea": Vote(canonical="tea", name="tea", qty=300, unit="piece", category="beverage", confidence=0.9, views=2)}
    assert _finalize(votes, type("Opts", (), {"max_items": 10})()) == []
