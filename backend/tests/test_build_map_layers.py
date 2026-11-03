"""Map-layer build script on tiny synthetic fixtures (no real data, no network)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))
import build_map_layers as b  # noqa: E402


def _fc():
    ring = [[16.0, 45.0], [16.01, 45.0], [16.01, 45.01], [16.005, 45.0100001], [16.0, 45.01], [16.0, 45.0]]
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature", "id": "x.1",
        "properties": {"podloznost": "visoka", "area": 5, "name": "secret"},
        "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]}}]}


def test_keeps_only_podloznost_and_rounds():
    out = b.process_geojson(_fc(), 0.0002, ("podloznost",))
    f = out["features"][0]
    assert f["properties"] == {"podloznost": "visoka"}
    assert "id" not in f
    assert all(len(str(v).split(".")[-1]) <= 5 for ring in f["geometry"]["coordinates"][0] for pt in ring for v in pt)
    assert b.process_geojson(_fc(), 0.0002, ())["features"][0]["properties"] == {}


def test_bbox_assertion():
    fc = b.process_geojson(_fc(), 0.0002, ())
    b.assert_inside(fc, [15.9, 44.9, 16.1, 45.1])
    with pytest.raises(AssertionError):
        b.assert_inside(fc, [17.0, 44.9, 17.5, 45.1])


def test_banovina_bbox_from_yaml():
    w, s, e, n = b.banovina_bbox()
    ring = b.coverage_geojson([w, s, e, n])["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == [w, s] and ring[2] == [e, n]


def test_efas_classification():
    d = np.array([[-9999, 0, 0.3, 1.0, 2.0, 3.0]], dtype=np.float32)
    rgba = b.classify_depth(b.mask_nodata(d))[0]
    assert rgba[0][3] == 0 and rgba[1][3] == 0
    colours = [tuple(rgba[i]) for i in range(2, 6)]
    assert colours == [c for _, c in b.EFAS_COLOURS]
    assert len(set(colours)) == 4


def test_downsample_max_keeps_single_flooded_pixel():
    a = np.zeros((4, 4), dtype=np.float32)
    a[1, 2] = 0.2
    s = b.downsample_max(b.mask_nodata(a + np.where(a == 0, -9999, 0)), 2)
    assert s.shape == (2, 2) and s[0, 1] == pytest.approx(0.2) and s.sum() == pytest.approx(0.2)


def test_downsample_pads_odd_sizes():
    assert b.downsample_max(np.ones((5, 5), dtype=np.float32), 2).shape == (3, 3)
    assert b.efas_factor(7740, 5160) == 2 and b.efas_factor(4096, 100) == 1


def test_build_efas_bounds_lon_lat(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    d = tmp_path / "efas"
    d.mkdir()
    for rp in (10, 100, 500):
        a = np.full((4, 4), -9999, dtype=np.float32)
        a[1, 1] = 1.0
        with rasterio.open(d / f"rp{rp}.tif", "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
                           crs="EPSG:4326", transform=from_origin(18.0, 45.0, 0.1, 0.1), nodata=-9999) as dst:
            dst.write(a, 1)
    out = tmp_path / "map"
    out.mkdir()
    b.build_efas(d, out)
    bounds = json.loads((out / "efas_bounds.json").read_text())
    assert bounds[0] == pytest.approx([18.0, 45.0]) and bounds[2] == pytest.approx([18.4, 44.6])
    assert (out / "efas_rp100.png").exists()


def test_web_mercator_rows_places_known_latitude():
    top, bottom, h = 46.6, 42.3, 1000
    arr = np.repeat(np.arange(h, dtype=np.float32)[:, None], 3, axis=1)  # value = source row
    out = b.to_web_mercator_rows(arr, top, bottom)
    assert out.shape[0] == int(np.ceil(h * 1.1))
    merc = lambda lat: np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    for lat in (45.4375, 44.881, 43.5081):  # Petrinja, Gunja, Split
        frac = (merc(top) - merc(lat)) / (merc(top) - merc(bottom))
        got = out[int(frac * out.shape[0]), 0]
        want = (top - lat) / (top - bottom) * h
        assert abs(got - want) < 3  # source rows (~0.4 km each)
