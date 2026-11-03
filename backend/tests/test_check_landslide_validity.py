import importlib.util
from pathlib import Path

import shapely
from shapely.geometry import Polygon

_spec = importlib.util.spec_from_file_location(
    "check_landslide_validity", Path(__file__).resolve().parents[2] / "scripts" / "check_landslide_validity.py")
clv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clv)


def test_parse_known_defect_lon_lat_order():
    assert clv.parse_defect("Self-intersection[16.40256 45.22683]") == (16.40256, 45.22683)
    assert clv.parse_defect("Valid Geometry") is None


def test_bowtie_detected_and_repaired_per_part():
    bowtie = Polygon([(16.0, 45.0), (16.01, 45.01), (16.01, 45.0), (16.0, 45.01)])
    found = clv.find_invalid([bowtie])
    assert len(found) == 1 and found[0]["defect"] is not None
    gs, ps = clv.build_repaired_set([bowtie], [{"podloznost": "visoka"}], found)
    assert found[0]["repaired"] and ps == ["visoka"] * len(gs)
    assert all(shapely.is_valid(g) for g in gs)
