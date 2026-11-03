import json
from pathlib import Path

from app.main import CATALOGUE, serialise
from app.risk_rules import Level, seismic_level
from app.seismic import SeismicReader


def test_seismic_reader_nearest_grid_point(tmp_path):
    grid_path = tmp_path / "eshm20_pga475.json"
    grid_path.write_text(json.dumps({
        "model_id": 81,
        "points": [
            {"lat": 45.4, "lon": 16.28213, "ag_g": 0.11446},
            {"lat": 45.55, "lon": 18.69, "ag_g": 0.06882},
            {"lat": 45.2, "lon": 13.6, "ag_g": 0.038},
        ],
    }), encoding="utf-8")

    reader = SeismicReader(grid_path)
    assert reader.available()

    # Petrinja -> nearest grid point (45.4, 16.28213) -> above low seismicity
    ag_pet, dist_pet = reader.pga_g(45.4375, 16.2739)
    assert ag_pet == 0.11446
    assert dist_pet < 10
    assert seismic_level(ag_pet, dist_pet).level is Level.SEISMIC_ABOVE_LOW

    # Osijek -> low seismicity (0.04 < ag <= 0.08)
    ag_os, _ = reader.pga_g(45.555, 18.695)
    assert ag_os == 0.06882
    assert seismic_level(ag_os).level is Level.SEISMIC_LOW

    # West Istria -> very low seismicity (ag <= 0.04)
    ag_is, _ = reader.pga_g(45.21, 13.61)
    assert ag_is == 0.038
    assert seismic_level(ag_is).level is Level.SEISMIC_VERY_LOW

    # Far from any grid point (> max_deg) -> None -> NO_DATA
    assert reader.pga_g(42.6, 18.1) is None
    assert seismic_level(None).level is Level.NO_DATA


def test_seismic_reader_missing_file(tmp_path):
    reader = SeismicReader(tmp_path / "missing.json")
    assert not reader.available()
    assert reader.pga_g(45.4375, 16.2739) is None


SEISMIC_NOTE = "Okvirna vrijednost iz europskog modela ESHM20 (najbliža točka mreže ~10 km, stijena Vs30 = 760 m/s)."


def _petrinja_grid(tmp_path):
    path = tmp_path / "g.json"
    path.write_text(json.dumps({"points": [{"lat": 45.4, "lon": 16.28213, "ag_g": 0.11446}]}), encoding="utf-8")
    return SeismicReader(path)


def test_seismic_result_has_note_and_distance(tmp_path):
    ag, dist = _petrinja_grid(tmp_path).pga_g(45.4375, 16.2739)
    res = seismic_level(ag, dist)
    assert res.level is Level.SEISMIC_ABOVE_LOW
    assert res.notes == [SEISMIC_NOTE]
    assert res.detail["ag_g"] == 0.114
    assert res.detail["udaljenost_km"] == round(dist, 1)
    assert 3 < res.detail["udaljenost_km"] < 5  # ~0.0375 deg lat = ~4.2 km


def test_seismic_no_data_has_note(tmp_path):
    reader = SeismicReader(tmp_path / "missing.json")
    res = seismic_level(reader.pga_g(45.4375, 16.2739))
    assert res.level is Level.NO_DATA
    assert res.notes == ["Podatak o potresnoj opasnosti nije dostupan za ovu lokaciju."]


def test_seismic_source_note_in_serialised_result_and_catalogue(tmp_path):
    ag, dist = _petrinja_grid(tmp_path).pga_g(45.4375, 16.2739)
    note = CATALOGUE["layers"]["seismic"]["note"]
    assert serialise(seismic_level(ag, dist))["source"]["note"] == note
    assert "data.gov.hr" in note and "760" in note
