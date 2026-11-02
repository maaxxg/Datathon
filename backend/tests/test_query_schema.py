from pathlib import Path

import yaml

from app.query_schema import QUERY_JSON_SCHEMA, Intent, ParsedQuery, validate_against_catalogue

CATALOGUE = yaml.safe_load((Path(__file__).resolve().parents[1] / "app" / "layers.yaml").read_text(encoding="utf-8"))
TESTSET = yaml.safe_load((Path(__file__).resolve().parents[1] / "app" / "nl_testset.yaml").read_text(encoding="utf-8"))


def test_json_schema_has_required_structure():
    assert "properties" in QUERY_JSON_SCHEMA
    props = QUERY_JSON_SCHEMA["properties"]
    for key in ("intent", "region", "filters", "locations", "layer", "unsupported"):
        assert key in props


def test_all_22_benchmark_queries_validate():
    queries = TESTSET["queries"]
    assert len(queries) >= 20
    intents = set()
    for item in queries:
        parsed = ParsedQuery.model_validate(item["expected"])
        intents.add(parsed.intent)
    # Must cover all 3 intents from Decision D7
    assert intents == {Intent.FIND_AREA, Intent.COMPARE_LOCATIONS, Intent.SHOW_LAYER}


def test_catalogue_validator_allows_banovina_geohazards():
    q = ParsedQuery.model_validate({
        "intent": "find_area",
        "region": "petrinja",
        "filters": [
            {"hazard": "flood", "max_level": "nema_prema_karti"},
            {"hazard": "landslide", "max_level": "nisko"},
        ],
        "unsupported": ["cijene nekretnina"],
    })
    res = validate_against_catalogue(q, CATALOGUE)
    assert res["in_banovina"] is True
    assert len(res["supported_filters"]) == 2
    assert len(res["warnings"]) == 1
    assert "cijene nekretnina" in res["warnings"][0]


def test_catalogue_validator_flags_banovina_only_layers_outside_banovina():
    # Split is outside Banovina -> flood is supported nationally, landslide is flagged with a warning
    q = ParsedQuery.model_validate({
        "intent": "find_area",
        "region": "split",
        "filters": [
            {"hazard": "flood", "max_level": "nema_prema_karti"},
            {"hazard": "landslide", "max_level": "nisko"},
        ],
    })
    res = validate_against_catalogue(q, CATALOGUE)
    assert res["in_banovina"] is False
    assert res["supported_filters"] == [{"hazard": "flood", "max_level": "nema_prema_karti"}]
    assert len(res["warnings"]) == 1
    assert "Banovine" in res["warnings"][0]
