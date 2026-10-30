import json

from app.geohazards import Geohazards, in_banovina


def square(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def test_lookup(tmp_path):
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"podloznost": "niska", "mjera": None}, "geometry": square(16.0, 45.0, 16.5, 45.5)},
        {"type": "Feature", "properties": {"podloznost": "visoka", "mjera": None}, "geometry": square(16.25, 45.4, 16.3, 45.45)},
    ]}
    (tmp_path / "landslide.geojson").write_text(json.dumps(fc))
    (tmp_path / "unfavourable.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": square(16.27, 45.43, 16.28, 45.44)}]}))
    geo = Geohazards(tmp_path)
    # Petrinja test point lies in both polygons -> the higher class wins
    assert geo.susceptibility("landslide", 45.4375, 16.2739) == "visoka"
    assert geo.susceptibility("landslide", 45.1, 16.1) == "niska"
    assert geo.susceptibility("landslide", 44.0, 16.1) is None
    assert geo.susceptibility("sinkhole", 45.4375, 16.2739) is None   # layer not loaded
    assert geo.inside("unfavourable", 45.4375, 16.2739)
    assert not geo.inside("unfavourable", 45.1, 16.1)


def test_banovina_bbox():
    assert in_banovina(45.4375, 16.2739)      # Petrinja
    assert not in_banovina(43.5081, 16.4402)  # Split
