import pytest

from app.risk_rules import (
    Level, combine_flood, flood_efas_level, flood_hv_level, groundwater_level,
    most_significant, seismic_level, susceptibility_level, unfavourable_level,
)


@pytest.mark.parametrize("classes, expected", [
    ({"velika": "d_lt_0_5", "srednja": "d_0_5_1_5", "mala": "d_1_5_2_5"}, Level.HIGH),
    ({"velika": "outside", "srednja": "d_1_5_2_5", "mala": "d_gt_2_5"}, Level.HIGH),
    ({"velika": "outside", "srednja": "d_0_5_1_5", "mala": "d_1_5_2_5"}, Level.MEDIUM),
    ({"velika": "outside", "srednja": "outside", "mala": "d_1_5_2_5"}, Level.LOW),
    ({"velika": "outside", "srednja": "outside", "mala": "outside"}, Level.NONE),
    ({"velika": None, "srednja": "outside", "mala": "outside"}, Level.NO_DATA),
    ({"velika": "permanent_water", "srednja": "permanent_water", "mala": "permanent_water"}, Level.HIGH),
])
def test_flood_hv(classes, expected):
    assert flood_hv_level(classes).level is expected


def test_flood_hv_karlovac_observed():
    # Observed on 30.10.2026: Karlovac test point, mala vjerojatnost 1.5-2.5 m, srednja outside.
    r = flood_hv_level({"velika": "outside", "srednja": "outside", "mala": "d_1_5_2_5"})
    assert r.level is Level.LOW


@pytest.mark.parametrize("depths, expected", [
    ({10: 0.4, 100: 1.0, 500: 2.0}, Level.HIGH),
    ({10: 0.0, 100: 0.3, 500: 1.0}, Level.MEDIUM),
    ({10: 0.0, 100: 0.0, 500: 0.2}, Level.LOW),
    ({10: 0.0, 100: 0.0, 500: 0.0}, Level.NONE),
    # None = not covered -> NO_DATA, never NONE
    ({10: None, 100: None, 500: 0.2}, Level.NO_DATA),
    ({10: None, 100: 0.0, 500: None}, Level.NO_DATA),
    ({10: None, 100: None, 500: None}, Level.NO_DATA),
    ({10: 1.0}, Level.NO_DATA),
])
def test_flood_efas(depths, expected):
    assert flood_efas_level(depths).level is expected


def test_hv_has_priority_over_efas():
    hv = flood_hv_level({"velika": "outside", "srednja": "outside", "mala": "outside"})
    efas = flood_efas_level({10: 1.0, 100: 1.0, 500: 1.0})
    assert combine_flood(hv, efas).source == "flood_hv"
    hv_missing = flood_hv_level({"velika": None, "srednja": None, "mala": None})
    assert combine_flood(hv_missing, efas).source == "flood_efas"


EFAS_NO_DATA_NOTE = "Europski model EFAS prikazuje samo poplave uz veće rijeke; za ovu točku nema podatka."


def test_efas_no_data_note_text():
    assert flood_efas_level({10: None, 100: None, 500: None}).notes == [EFAS_NO_DATA_NOTE]


def test_both_flood_sources_no_data_keeps_both_notes():
    hv = flood_hv_level({"velika": None, "srednja": None, "mala": None})
    efas = flood_efas_level({10: None, 100: None, 500: None})
    r = combine_flood(hv, efas)
    assert r.level is Level.NO_DATA
    assert r.source == "flood_hv"
    assert all(n in r.notes for n in hv.notes)
    assert EFAS_NO_DATA_NOTE in r.notes


@pytest.mark.parametrize("ag, expected", [
    (0.03, Level.SEISMIC_VERY_LOW), (0.04, Level.SEISMIC_VERY_LOW),
    (0.06, Level.SEISMIC_LOW), (0.08, Level.SEISMIC_LOW),
    (0.081, Level.SEISMIC_ABOVE_LOW), (0.3, Level.SEISMIC_ABOVE_LOW), (None, Level.NO_DATA),
])
def test_seismic_eurocode_thresholds(ag, expected):
    assert seismic_level(ag).level is expected


def test_susceptibility():
    assert susceptibility_level("landslide", "visoka", True).level is Level.HIGH
    assert susceptibility_level("landslide", "Niska ", True).level is Level.LOW
    assert susceptibility_level("landslide", None, True).level is Level.NO_DATA
    assert susceptibility_level("landslide", "visoka", False).level is Level.NO_DATA
    assert susceptibility_level("landslide", "???", True).level is Level.NO_DATA


def test_unfavourable():
    assert unfavourable_level(True, True).level is Level.HIGH
    assert unfavourable_level(False, True).level is Level.NONE
    assert unfavourable_level(True, False).level is Level.NO_DATA


def test_groundwater():
    assert groundwater_level({"dubina_do": 0.8, "udaljenost_m": 85}, True).level is Level.HIGH
    assert groundwater_level({"dubina_do": 1.5, "udaljenost_m": 120}, True).level is Level.MEDIUM
    assert groundwater_level({"dubina_do": 3.0, "udaljenost_m": 120}, True).level is Level.MEDIUM
    assert groundwater_level({"dubina_do": 3.5, "udaljenost_m": 200}, True).level is Level.LOW
    assert groundwater_level(None, True).level is Level.NO_DATA
    assert groundwater_level({"dubina_do": 0.5, "udaljenost_m": 50}, False).level is Level.NO_DATA


def test_most_significant_tie_break_prefers_flood():
    results = [
        susceptibility_level("landslide", "visoka", True),
        flood_hv_level({"velika": "d_lt_0_5", "srednja": "outside", "mala": "outside"}),
    ]
    assert most_significant(results).hazard == "flood"


def test_most_significant_none_when_nothing_found():
    results = [
        flood_hv_level({"velika": "outside", "srednja": "outside", "mala": "outside"}),
        susceptibility_level("landslide", None, False),
    ]
    assert most_significant(results) is None


def test_groundwater_note_date_and_distance():
    r = groundwater_level({"dubina_do": 0.8, "datum_mjerenja": "4.02.2021.", "udaljenost_m": 85}, True)
    assert r.level is Level.HIGH
    assert "4. 2. 2021." in r.notes[0] and "85 m" in r.notes[0]
    r = groundwater_level({"dubina_do": 2.0, "datum_mjerenja": "25.2.2021.", "udaljenost_m": 10}, True)
    assert "25. 2. 2021." in r.notes[0]


def test_groundwater_negative_depth_note():
    r = groundwater_level({"dubina_do": -0.28, "datum_mjerenja": "18.02.2021", "udaljenost_m": 40}, True)
    assert r.level is Level.HIGH
    assert any("iznad razine terena" in n for n in r.notes)
    assert "18. 2. 2021." in r.notes[0]


def test_groundwater_date_fallback():
    for raw in (None, "", "veljača", "2021-02-04"):
        r = groundwater_level({"dubina_do": 2.0, "datum_mjerenja": raw, "udaljenost_m": 5}, True)
        assert "2021. (datum mjerenja nije naveden; bušotina udaljena 5 m)" in r.notes[0]
        assert "veljač" not in r.notes[0]


def test_groundwater_layer_not_loaded():
    r = groundwater_level(None, True, layer_loaded=False)
    assert r.level is Level.NO_DATA
    assert any("nije učitan" in n for n in r.notes)


@pytest.mark.parametrize("inside", [False, True])
def test_unfavourable_layer_not_loaded_is_no_data(inside):
    r = unfavourable_level(inside, True, layer_loaded=False)
    assert r.level is Level.NO_DATA
    assert "nije učitan" in r.notes[0]


def test_susceptibility_layer_not_loaded_is_no_data():
    r = susceptibility_level("landslide", None, True, layer_loaded=False)
    assert r.level is Level.NO_DATA
    assert "nije učitan" in r.notes[0]


def test_out_of_coverage_checked_before_layer_loaded():
    assert "Izvan obuhvata" in unfavourable_level(False, False, layer_loaded=False).notes[0]
    assert "Izvan obuhvata" in susceptibility_level("sinkhole", None, False, layer_loaded=False).notes[0]


def test_layer_loaded_default_keeps_behaviour():
    assert unfavourable_level(False, True).level is Level.NONE
    assert susceptibility_level("landslide", "visoka", True).level is Level.HIGH


# --- D22: HV outage, EFAS fallback with explicit note ------------------------

EFAS_HIGH = {10: 0.17, 100: 1.03, 500: 1.42}
ALL_FAILED_NOTE = ("Servis Hrvatskih voda trenutačno ne odgovara (privremeni prekid); karta opasnosti od "
                   "poplava za ovu točku nije mogla biti provjerena.")
PARTIAL_NOTE = ("Servis Hrvatskih voda trenutačno ne odgovara za: mala vjerojatnost (privremeni prekid). "
                "Odgovor za ostale scenarije: velika vjerojatnost – izvan poplavne zone; "
                "srednja vjerojatnost – izvan poplavne zone.")


def test_combine_hv_all_fail_efas_data():
    r = combine_flood(flood_hv_level({"velika": None, "srednja": None, "mala": None}), flood_efas_level(EFAS_HIGH))
    assert r.level is Level.HIGH and r.source == "flood_efas"
    assert r.notes[0] == ALL_FAILED_NOTE
    assert r.detail["hv_status"] == "unavailable"
    assert r.detail["hv_unavailable_scenarios"] == ["velika", "srednja", "mala"]


def test_combine_hv_partial_fail_efas_data():
    hv = flood_hv_level({"velika": "outside", "srednja": "outside", "mala": None})
    assert hv.level is Level.NO_DATA  # Q1: no partial level
    r = combine_flood(hv, flood_efas_level(EFAS_HIGH))
    assert r.level is Level.HIGH and r.source == "flood_efas"
    assert r.notes[0] == PARTIAL_NOTE
    assert r.detail["hv_unavailable_scenarios"] == ["mala"]


def test_partial_note_uses_depth_label():
    hv = flood_hv_level({"velika": "d_1_5_2_5", "srednja": None, "mala": None})
    assert hv.notes[0].endswith("Odgovor za ostale scenarije: velika vjerojatnost – 1,5 – 2,5 m.")


@pytest.mark.parametrize("efas", [flood_efas_level({10: None, 100: None, 500: None}), None])
def test_combine_hv_partial_fail_no_efas(efas):
    r = combine_flood(flood_hv_level({"velika": "outside", "srednja": "outside", "mala": None}), efas)
    assert r.level is Level.NO_DATA and r.source == "flood_hv"
    assert r.notes[0] == PARTIAL_NOTE
    assert r.detail["hv_status"] == "unavailable"
    assert r.detail["hv_unavailable_scenarios"] == ["mala"]


def test_combine_hv_ok():
    r = combine_flood(flood_hv_level({"velika": "outside", "srednja": "outside", "mala": "d_1_5_2_5"}),
                      flood_efas_level(EFAS_HIGH))
    assert r.level is Level.LOW and r.source == "flood_hv"
    assert r.detail["hv_status"] == "ok" and r.detail["hv_unavailable_scenarios"] == []
    assert not any("ne odgovara" in n for n in r.notes)


def test_efas_note_has_no_hv_clause():
    assert flood_efas_level(EFAS_HIGH).notes == ["Europski model (90 m), okvirna procjena."]
