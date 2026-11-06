"""Tests for Ollama LLM adapter, JSON query parsing, report explanations, and Q&A (SPEC SHOULD #10 & #12, D5, D7, D9, D18)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

import h3

from app.h3_grid import evaluate_region_grid
from app.llm import (
    _extract_unsupported,
    fallback_answer_report_question,
    fallback_explain_report,
    fallback_parse_nl_query,
    sanitize_report_for_llm,
)
from app.main import CATALOGUE
from app.query_schema import ParsedQuery, validate_against_catalogue

TESTSET = yaml.safe_load((Path(__file__).resolve().parents[1] / "app" / "nl_testset.yaml").read_text(encoding="utf-8"))

SAMPLE_REPORT = {
    "location": {"lat": 45.4375, "lon": 16.2739},
    "most_significant": {
        "hazard": "liquefaction",
        "level": "visoko",
        "source": "liquefaction",
        "detail": {"podloznost": "Visoka"},
        "notes": [],
        "explanation": "Prema studiji geohazarda MPGI-ja (2021.) lokacija je u zoni visoke podložnosti likvefakciji tla (razred u studiji: Visoka).",
    },
    "hazards": [
        {
            "hazard": "flood",
            "level": "nisko",
            "source": "flood_hv",
            "detail": {"velika": "outside", "srednja": "outside", "mala": "d_0_5_1_5", "hv_status": "ok"},
            "notes": [],
            "explanation": "Prema karti opasnosti od poplava Hrvatskih voda (2019.) lokacija je u zoni male vjerojatnosti poplave, procijenjena dubina vode: 0,5 – 1,5 m; izvan zona velike i srednje vjerojatnosti.",
            "source": {
                "title": "Karte opasnosti od poplava 2019.",
                "publisher": "Hrvatske vode",
                "year": 2019,
                "resolution": "render WMS-a (GetMap), dubina u razredima",
                "note": None,
            },
        },
        {
            "hazard": "liquefaction",
            "level": "visoko",
            "source": "liquefaction",
            "detail": {"podloznost": "Visoka"},
            "notes": [],
            "explanation": "Prema studiji geohazarda MPGI-ja (2021.) lokacija je u zoni visoke podložnosti likvefakciji tla (razred u studiji: Visoka).",
            "source": {
                "title": "Podložnost likvefakciji",
                "publisher": "Ministarstvo prostornoga uređenja, graditeljstva i državne imovine",
                "year": 2021,
                "resolution": "poligoni studije (preliminarna identifikacija)",
                "note": None,
            },
        },
        {
            "hazard": "landslide",
            "level": "nema_podataka",
            "source": "landslide",
            "detail": {},
            "notes": ["Točka nije unutar poligona studije."],
            "explanation": "Nema podataka za klizišta. Točka nije unutar poligona studije.",
            "source": {
                "title": "Podložnost klizištima",
                "publisher": "Ministarstvo prostornoga uređenja, graditeljstva i državne imovine",
                "year": 2021,
                "resolution": "poligoni studije",
                "note": None,
            },
        },
    ],
    "summary": "Najznačajniji utvrđeni rizik na lokaciji: likvefakcija tla (razina: visoko).",
    "all_no_data": False,
    "recommended_actions": [
        {
            "hazard": "geohazards",
            "title": "Naručite geotehnički i inženjerskogeološki pregled terena",
            "description": "Za konkretnu česticu preporučuje se terenski uvid geomehaničara.",
            "institution": "Informacijski sustav prostornog uređenja (ISPU)",
            "url": "https://ispu.mgipu.hr/",
        }
    ],
    "disclaimer": "Informativni prikaz iz javnih podataka.",
}


def test_fallback_parser_matches_all_22_benchmark_queries():
    for item in TESTSET["queries"]:
        parsed = fallback_parse_nl_query(item["text"])
        assert parsed.model_dump(mode="json") == item["expected"], f"Mismatch on {item['id']}"


def test_sanitize_report_strips_coordinates():
    clean = sanitize_report_for_llm(SAMPLE_REPORT)
    assert "location" not in clean
    assert "45.4375" not in json.dumps(clean)
    assert len(clean["hazards"]) == 3


def test_fallback_explain_and_ask_grounded_in_report():
    exp = fallback_explain_report(SAMPLE_REPORT)
    assert "likvefakcija" in exp.lower()
    assert "nema podataka" in exp.lower()

    ans_liq = fallback_answer_report_question("Kakva je podložnost likvefakciji na ovoj lokaciji?", SAMPLE_REPORT)
    assert "visoko" in ans_liq.lower()
    assert "mpgi" in ans_liq.lower() or "ministarstvo" in ans_liq.lower()

    ans_price = fallback_answer_report_question("Kolika je cijena kvadrata ovdje?", SAMPLE_REPORT)
    assert "ne sadrži podatke o cijenama nekretnina" in ans_price

    ans_nodata = fallback_answer_report_question("Zašto nema podataka za klizišta?", SAMPLE_REPORT)
    assert "nema podataka" in ans_nodata.lower()


def test_parse_and_validate_pipeline_for_split_and_petrinja():
    parsed_split = fallback_parse_nl_query("Pronađi područja u Splitu bez poplava i bez klizišta.")
    val_split = validate_against_catalogue(parsed_split, CATALOGUE)
    assert val_split["in_banovina"] is False
    assert val_split["supported_filters"] == [{"hazard": "flood", "max_level": "nema_prema_karti"}]
    assert any("Banovine" in w for w in val_split["warnings"])
    assert val_split["center"] is not None

    parsed_petrinja = fallback_parse_nl_query("Pronađi područja u Petrinji bez poplava i s cijenom kvadrata ispod 1500 eura.")
    val_petrinja = validate_against_catalogue(parsed_petrinja, CATALOGUE)
    assert val_petrinja["in_banovina"] is True
    assert val_petrinja["supported_filters"] == [{"hazard": "flood", "max_level": "nema_prema_karti"}]
    assert any("cijene nekretnina" in w for w in val_petrinja["warnings"])


class _StubEFAS:
    def available(self) -> bool:
        return True

    def depths(self, lat: float, lon: float) -> dict[int, float | None]:
        # Simulate flood hazard on the northern half of Petrinja (lat >= 45.4375)
        if lat >= 45.4375:
            return {10: None, 100: 0.8, 500: 1.4}
        return {10: None, 100: None, 500: None}


def test_evaluate_region_grid_hex_geometry_and_filtering():
    parsed_petrinja = fallback_parse_nl_query("Pronađi područja u Petrinji bez poplava.")
    val_petrinja = validate_against_catalogue(parsed_petrinja, CATALOGUE)

    grid = evaluate_region_grid(val_petrinja, efas=_StubEFAS())
    assert grid is not None
    assert grid["type"] == "FeatureCollection"
    summary = grid["summary"]
    assert summary["region"] == "petrinja"
    assert summary["h3_resolution"] == 9
    assert summary["resolutions"] == {"coarse": 7, "medium": 8, "base": 9, "fine": 10}
    assert summary["cell_area_km2"] == 0.11
    base_feats = [f for f in grid["features"] if f["properties"]["tier"] == "base"]
    assert summary["total_cells"] == len(base_feats)
    assert summary["total_cells"] == summary["matched_cells"] + summary["excluded_cells"]
    assert summary["matched_cells"] > 0
    assert summary["excluded_cells"] > 0
    assert "ODbL 1.0" in summary["odbl_notice"]

    tiers = {f["properties"]["tier"] for f in grid["features"]}
    assert tiers == {"coarse", "medium", "base", "fine"}

    first_feat = base_feats[0]
    assert h3.is_valid_cell(first_feat["properties"]["h3_index"])
    assert h3.get_resolution(first_feat["properties"]["h3_index"]) == 9
    assert first_feat["geometry"]["type"] == "Polygon"
    ring = first_feat["geometry"]["coordinates"][0]
    assert len(ring) == 7  # 6 vertices + closing vertex
    assert ring[0] == ring[-1]

    # Non-find_area intent returns None
    parsed_layer = fallback_parse_nl_query("Prikaži sloj klizišta na Banovini.")
    val_layer = validate_against_catalogue(parsed_layer, CATALOGUE)
    assert evaluate_region_grid(val_layer) is None


def test_ollama_partial_json_and_extract_unsupported():
    raw_ollama_json = json.dumps({
        "intent": "find_area",
        "region": "petrinja",
        "filters": [{"hazard": "flood", "max_level": "nema_prema_karti"}],
    })
    parsed = ParsedQuery.model_validate_json(raw_ollama_json)
    assert parsed.intent.value == "find_area"
    assert parsed.region == "petrinja"
    assert _extract_unsupported("pronađi područja u petrinji bez poplava i cijena kvadrata") == ["cijene nekretnina"]
