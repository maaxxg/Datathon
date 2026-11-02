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
    assert "RP100: 0.45 m" in explain_hazard(efas)

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
