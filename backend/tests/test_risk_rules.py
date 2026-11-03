import pytest

from app.risk_rules import (
    Level, combine_flood, flood_efas_level, flood_hv_level, most_significant,
    seismic_level, susceptibility_level, unfavourable_level,
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


def test_both_flood_sources_no_data_keeps_both_notes():
    hv = flood_hv_level({"velika": None, "srednja": None, "mala": None})
    efas = flood_efas_level({10: None, 100: None, 500: None})
    r = combine_flood(hv, efas)
    assert r.level is Level.NO_DATA
    assert r.source == "flood_hv"
    assert all(n in r.notes for n in hv.notes)
    assert "Europski model EFAS ne pokriva ovu točku." in r.notes


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
