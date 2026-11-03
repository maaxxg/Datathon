from app.risk_rules import (
    HazardResult, Level, flood_efas_level, flood_hv_level, most_significant,
    seismic_level, susceptibility_level, unfavourable_level,
)
from app.templates import build_summary, explain_hazard, recommended_actions


def test_explain_hv_flood_scenarios():
    high = flood_hv_level({"velika": "d_0_5_1_5", "srednja": "d_1_5_2_5", "mala": "d_gt_2_5"})
    assert "velike vjerojatnosti" in explain_hazard(high)
    assert "0,5 – 1,5 m" in explain_hazard(high)

    none = flood_hv_level({"velika": "outside", "srednja": "outside", "mala": "outside"})
    assert "izvan poplavnih zona" in explain_hazard(none)


def test_explain_efas_and_seismic():
    efas = flood_efas_level({10: 0.0, 100: 0.45, 500: 1.1})
    assert "EFAS" in explain_hazard(efas)
    assert "RP100: 0,45 m" in explain_hazard(efas)

    seis = seismic_level(0.185)
    assert "0,185 g" in explain_hazard(seis)
    assert "Eurokodu 8" in explain_hazard(seis)


def test_explain_geohazards():
    ls = susceptibility_level("landslide", "visoka", True)
    assert "klizištima" in explain_hazard(ls)
    assert "visoka" in explain_hazard(ls)

    unfav = unfavourable_level(True, True)
    assert "nepovoljno za gradnju" in explain_hazard(unfav)

    gw = HazardResult("groundwater", Level.MEDIUM, "groundwater",
                      {"dubina_do": 1.96, "udaljenost_m": 70, "datum_mjerenja": "16.02.2021."})
    assert "1,96 m" in explain_hazard(gw)
    assert "70 m" in explain_hazard(gw)


def test_summary_and_recommended_actions():
    results = [
        flood_hv_level({"velika": "outside", "srednja": "d_0_5_1_5", "mala": "d_1_5_2_5"}),
        susceptibility_level("liquefaction", "visoka", True),
        seismic_level(0.16),
    ]
    top = most_significant(results)
    summary = build_summary(results, top, in_banovina_coverage=True)
    assert "Najznačajniji utvrđeni rizik" in summary
    assert "likvefakcija" in summary

    actions = recommended_actions(results)
    hazards = [a["hazard"] for a in actions]
    assert "flood" in hazards
    assert "seismic" in hazards
    assert "geohazards" in hazards
    assert "general" in hazards
    assert all(a["url"].startswith("https://") for a in actions)


# --- brief 001 (update 3. 11.): honest texts for every rule outcome ----------

import re

import pytest

from app.risk_rules import combine_flood, groundwater_level
from app.templates import FALLBACK_TEXT

HV = flood_hv_level
GW_HIT = {"dubina_do": 2.0, "datum_mjerenja": "16.02.2021.", "udaljenost_m": 70}


def _gw(depth, date="16.02.2021.", covered=True, loaded=True, hit=True):
    h = {"dubina_do": depth, "datum_mjerenja": date, "udaljenost_m": 70} if hit else None
    return groundwater_level(h, covered, loaded)


CASES = {
    "hv_permanent": HV({"velika": "permanent_water", "srednja": "outside", "mala": "outside"}),
    "hv_velika": HV({"velika": "d_lt_0_5", "srednja": "d_0_5_1_5", "mala": "d_gt_2_5"}),
    "hv_srednja_deep": HV({"velika": "outside", "srednja": "d_1_5_2_5", "mala": "d_gt_2_5"}),
    "hv_srednja_shallow": HV({"velika": "outside", "srednja": "d_0_5_1_5", "mala": "d_1_5_2_5"}),
    "hv_mala": HV({"velika": "outside", "srednja": "outside", "mala": "d_lt_0_5"}),
    "hv_none": HV({"velika": "outside", "srednja": "outside", "mala": "outside"}),
    "hv_one_none": HV({"velika": "outside", "srednja": None, "mala": "outside"}),
    "efas_rp10": flood_efas_level({10: 0.3, 100: 0.5, 500: 1.0}),
    "efas_rp100": flood_efas_level({10: 0.0, 100: 0.45, 500: 1.0}),
    "efas_rp500": flood_efas_level({10: 0.0, 100: 0.0, 500: 1.2}),
    "efas_dry": flood_efas_level({10: 0.0, 100: 0.0, 500: 0.0}),
    "combined_no_data": combine_flood(HV({"velika": None, "srednja": None, "mala": None}),
                                      flood_efas_level({10: None, 100: None, 500: None})),
    "seis_003": seismic_level(0.03, 9.8),
    "seis_0061": seismic_level(0.061, 4.0),
    "seis_0114": seismic_level(0.114, 3.2),
    "seis_none": seismic_level(None),
    "unfav_inside": unfavourable_level(True, True),
    "unfav_outside": unfavourable_level(False, True),
    "unfav_no_cov": unfavourable_level(False, False),
    "unfav_not_loaded": unfavourable_level(False, True, False),
    "gw_04": _gw(0.4), "gw_20": _gw(2.0), "gw_50": _gw(5.0), "gw_neg": _gw(-0.28),
    "gw_no_well": _gw(0, hit=False), "gw_not_loaded": _gw(2.0, loaded=False),
    "gw_no_date": _gw(2.0, date=None), "gw_no_cov": _gw(2.0, covered=False),
}
for _h in ("landslide", "liquefaction", "sinkhole"):
    for _v in ("niska", "srednja", "visoka"):
        CASES[f"{_h}_{_v}"] = susceptibility_level(_h, _v, True)
    CASES[f"{_h}_no_cov"] = susceptibility_level(_h, None, False)
    CASES[f"{_h}_not_loaded"] = susceptibility_level(_h, None, True, False)
    CASES[f"{_h}_outside_poly"] = susceptibility_level(_h, None, True)
    CASES[f"{_h}_unknown"] = susceptibility_level(_h, "nepoznato", True)

FORBIDDEN = ("obvezan", "1964", "25 godina", "100-godišnj", "nema_podataka", "visoka seizmičnost")


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_rule_outcome_has_specific_clean_text(name):
    text = explain_hazard(CASES[name])
    assert text and text != FALLBACK_TEXT
    assert not re.search(r"\d\.\d", text)
    assert "_" not in text
    assert not any(f in text for f in FORBIDDEN)


@pytest.mark.parametrize("name", [n for n, r in CASES.items() if r.level is Level.NO_DATA])
def test_no_data_text_contains_rule_notes(name):
    r = CASES[name]
    text = explain_hazard(r)
    assert text.startswith("Nema podataka za ")
    for note in r.notes:
        assert note in text
    assert "nije utvrđena" not in text


def test_specific_no_data_notes_reach_user():
    assert "Sloj nije učitan." in explain_hazard(CASES["landslide_not_loaded"])
    assert "Točka nije unutar poligona studije." in explain_hazard(CASES["sinkhole_outside_poly"])
    assert "Izvan obuhvata studije (Banovina)." in explain_hazard(CASES["unfav_no_cov"])


def test_groundwater_texts():
    text = explain_hazard(CASES["gw_20"])
    assert "16. 2. 2021." in text and "udaljena 70 m" in text and "Jedno mjerenje" in text
    assert "datum mjerenja nije naveden" in explain_hazard(CASES["gw_no_date"])
    neg = explain_hazard(CASES["gw_neg"])
    assert "iznad razine terena (0,28 m)" in neg and "-" not in neg.replace("–", "")


def test_seismic_texts():
    hi = explain_hazard(CASES["seis_0114"])
    for part in ("iznad praga niske seizmičnosti", "0,114 g", "ESHM20", "okvirno", "475 god.",
                 "prema Eurokodu 8", "udaljena je 3,2 km"):
        assert part in hi
    low = explain_hazard(CASES["seis_0061"])
    assert "niska seizmičnost" in low and "vrlo niska" not in low
    assert "vrlo niska seizmičnost" in explain_hazard(CASES["seis_003"])


def test_efas_texts():
    text = explain_hazard(CASES["efas_rp100"])
    for part in ("europski model EFAS", "90 m", "okvirno", "RP100: 0,45 m",
                 "karta Hrvatskih voda ovdje nema podataka"):
        assert part in text
    assert "RP10:" not in text
    assert "10, 100 i 500 god." in explain_hazard(CASES["efas_dry"])


def test_susceptibility_wording():
    assert "zoni visoke podložnosti klizištima" in explain_hazard(CASES["landslide_visoka"])
    assert "zoni niske podložnosti nastanku vrtača" in explain_hazard(CASES["sinkhole_niska"])


def test_summary_all_no_data():
    results = [CASES["combined_no_data"], CASES["seis_none"], CASES["landslide_no_cov"]]
    s = build_summary(results, most_significant(results), False)
    assert s.startswith("Za ovu lokaciju trenutno nema dostupnih podataka")
    assert "nije utvrđena" not in s


def test_summary_none_plus_no_data_lists_both_groups():
    results = [CASES["hv_none"], CASES["seis_none"], CASES["landslide_no_cov"]]
    s = build_summary(results, most_significant(results), False)
    assert "nije utvrđena povišena opasnost za: poplave." in s
    assert "Nema podataka za: potresna opasnost, klizišta." in s


def test_summary_top_plus_no_data_and_scope():
    results = [CASES["hv_velika"], CASES["seis_none"], CASES["landslide_no_cov"]]
    s = build_summary(results, most_significant(results), False)
    assert "razina: visoko" in s
    assert "Nema podataka za: potresna opasnost, klizišta." in s
    assert "nacionalni slojevi" not in s and "Sisačko" not in s
    assert "samo za područje Banovine" in s
    assert not re.search(r"\d\.\d", s) and "_" not in s


def test_summary_level_labels_have_diacritics():
    results = [CASES["seis_0114"]]
    s = build_summary(results, most_significant(results), False)
    assert "razina: iznad praga niske seizmičnosti" in s


def test_actions_text_has_no_unsourced_claims():
    results = [CASES["hv_velika"], CASES["seis_0114"], CASES["landslide_visoka"]]
    for a in recommended_actions(results):
        assert "1964" not in a["description"]
