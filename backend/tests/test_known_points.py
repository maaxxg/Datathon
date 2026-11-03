"""Deterministic regression tests on the 10 known Croatia locations observed on 2. 11. 2026."""
import pytest

from app.risk_rules import (
    Level, combine_flood, flood_efas_level, flood_hv_level, most_significant,
    seismic_level, susceptibility_level, unfavourable_level,
)

# Ground-truth observations recorded by scripts/validate_known_points.py on 2. 11. 2026.
# EFAS values re-read 3. 11. 2026 on clipped v3.1.1 files; -9999 (nodata) -> None (D20).
OBSERVED_POINTS = [
    (
        "p01_petrinja_centar",
        True,
        {"velika": "outside", "srednja": "outside", "mala": "d_1_5_2_5"},
        {10: None, 100: None, 500: None},
        0.1145,
        {"landslide": None, "liquefaction": "visoka", "sinkhole": None, "unfavourable": False},
        ("liquefaction", Level.HIGH),
    ),
    (
        "p02_petrinja_gupca_12",
        True,
        {"velika": "outside", "srednja": "outside", "mala": "outside"},
        {10: None, 100: None, 500: None},
        0.1145,
        {"landslide": None, "liquefaction": "visoka", "sinkhole": None, "unfavourable": False},
        ("liquefaction", Level.HIGH),
    ),
    (
        "p03_sisak_rimska_19",
        True,
        {"velika": "outside", "srednja": "outside", "mala": "outside"},
        {10: None, 100: None, 500: None},
        0.1086,
        {"landslide": None, "liquefaction": "visoka", "sinkhole": None, "unfavourable": False},
        ("liquefaction", Level.HIGH),
    ),
    (
        "p04_glina_centar",
        True,
        {"velika": "outside", "srednja": "outside", "mala": "d_lt_0_5"},
        {10: None, 100: None, 500: None},
        0.1159,
        {"landslide": None, "liquefaction": "visoka", "sinkhole": None, "unfavourable": False},
        ("liquefaction", Level.HIGH),
    ),
    (
        "p05_hrvatska_kostajnica",
        True,
        {"velika": "outside", "srednja": "outside", "mala": "outside"},
        {10: None, 100: None, 500: None},
        0.1052,
        {"landslide": "visoka", "liquefaction": None, "sinkhole": None, "unfavourable": False},
        ("landslide", Level.HIGH),
    ),
    (
        "p06_karlovac_kupa",
        False,
        {"velika": "outside", "srednja": "outside", "mala": "d_1_5_2_5"},
        {10: None, 100: None, 500: None},
        0.1759,
        {"landslide": None, "liquefaction": None, "sinkhole": None, "unfavourable": False},
        ("seismic", Level.SEISMIC_ABOVE_LOW),
    ),
    (
        "p07_gunja_sava",
        False,
        {"velika": "outside", "srednja": "outside", "mala": "d_1_5_2_5"},
        {10: 0.17, 100: 1.03, 500: 1.42},
        0.1036,
        {"landslide": None, "liquefaction": None, "sinkhole": None, "unfavourable": False},
        ("seismic", Level.SEISMIC_ABOVE_LOW),
    ),
    (
        "p08_zagreb_sava",
        False,
        {"velika": "outside", "srednja": "outside", "mala": "d_0_5_1_5"},
        {10: None, 100: None, 500: None},
        0.2452,
        {"landslide": None, "liquefaction": None, "sinkhole": None, "unfavourable": False},
        ("seismic", Level.SEISMIC_ABOVE_LOW),
    ),
    (
        "p09_split_centar",
        False,
        {"velika": "outside", "srednja": "outside", "mala": "d_0_5_1_5"},
        {10: None, 100: None, 500: None},
        0.1694,
        {"landslide": None, "liquefaction": None, "sinkhole": None, "unfavourable": False},
        ("seismic", Level.SEISMIC_ABOVE_LOW),
    ),
    (
        "p10_osijek_centar",
        False,
        {"velika": "outside", "srednja": "outside", "mala": "outside"},
        {10: None, 100: None, 500: None},
        0.0688,
        {"landslide": None, "liquefaction": None, "sinkhole": None, "unfavourable": False},
        ("seismic", Level.SEISMIC_LOW),
    ),
]


@pytest.mark.parametrize("pid, in_ban, hv_cls, efas_d, ag, geo, expected_top", OBSERVED_POINTS)
def test_ten_known_points_rules(pid, in_ban, hv_cls, efas_d, ag, geo, expected_top):
    flood_res = combine_flood(flood_hv_level(hv_cls), flood_efas_level(efas_d))
    seis_res = seismic_level(ag)
    results = [
        flood_res,
        seis_res,
        susceptibility_level("landslide", geo["landslide"], in_ban),
        susceptibility_level("liquefaction", geo["liquefaction"], in_ban),
        susceptibility_level("sinkhole", geo["sinkhole"], in_ban),
        unfavourable_level(bool(geo["unfavourable"]), in_ban),
    ]
    top = most_significant(results)
    assert top is not None, f"{pid} returned no top hazard"
    assert (top.hazard, top.level) == expected_top


def test_petrinja_efas_nodata_with_hv_no_data_is_no_data_not_none():
    # p01: EFAS raw -9999 on all return periods; with HV unavailable the flood result must be NO_DATA.
    hv = flood_hv_level({"velika": None, "srednja": None, "mala": None})
    r = combine_flood(hv, flood_efas_level({10: None, 100: None, 500: None}))
    assert r.level is Level.NO_DATA
