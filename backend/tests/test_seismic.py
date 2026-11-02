import json
from pathlib import Path

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
    ag_pet = reader.pga_g(45.4375, 16.2739)
    assert ag_pet == 0.11446
    assert seismic_level(ag_pet).level is Level.SEISMIC_ABOVE_LOW

    # Osijek -> low seismicity (0.04 < ag <= 0.08)
    ag_os = reader.pga_g(45.555, 18.695)
    assert ag_os == 0.06882
    assert seismic_level(ag_os).level is Level.SEISMIC_LOW

    # West Istria -> very low seismicity (ag <= 0.04)
    ag_is = reader.pga_g(45.21, 13.61)
    assert ag_is == 0.038
    assert seismic_level(ag_is).level is Level.SEISMIC_VERY_LOW

    # Far from any grid point (> max_deg) -> None -> NO_DATA
    assert reader.pga_g(42.6, 18.1) is None
    assert seismic_level(reader.pga_g(42.6, 18.1)).level is Level.NO_DATA


def test_seismic_reader_missing_file(tmp_path):
    reader = SeismicReader(tmp_path / "missing.json")
    assert not reader.available()
    assert reader.pga_g(45.4375, 16.2739) is None
