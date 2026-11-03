import json

from app.geohazards import Geohazards, in_banovina


def square(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def test_lookup(tmp_path):
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"podloznost": "niska", "mjera": None}, "geometry": square(16.0, 45.0, 16.5, 45.5)},
        {"type": "Feature", "properties": {"podloznost": "visoka", "mjera": None}, "geometry": square(16.25, 45.4, 16.3, 45.45)},
    ]}
    (tmp_path / "landslide.geojson").write_text(json.dumps(fc), encoding="utf-8")
    (tmp_path / "unfavourable.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": square(16.27, 45.43, 16.28, 45.44)}]}), encoding="utf-8")
    (tmp_path / "groundwater.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"dubina_do": 1.2, "datum_mjerenja": "4.02.2021."},
         "geometry": {"type": "Point", "coordinates": [16.2750, 45.4380]}},
        {"type": "Feature", "properties": {"dubina_do": 4.5, "datum_mjerenja": "4.02.2021."},
         "geometry": {"type": "Point", "coordinates": [16.2800, 45.4420]}},
    ]}), encoding="utf-8")
    geo = Geohazards(tmp_path)
    # Petrinja test point lies in both polygons -> the higher class wins
    assert geo.susceptibility("landslide", 45.4375, 16.2739) == "visoka"
    assert geo.susceptibility("landslide", 45.1, 16.1) == "niska"
    assert geo.susceptibility("landslide", 44.0, 16.1) is None
    assert geo.susceptibility("sinkhole", 45.4375, 16.2739) is None   # layer not loaded
    assert geo.inside("unfavourable", 45.4375, 16.2739)
    assert not geo.inside("unfavourable", 45.1, 16.1)

    gw = geo.nearest_groundwater(45.4375, 16.2739, max_dist_m=1000.0)
    assert gw is not None
    assert gw["dubina_do"] == 1.2
    assert gw["datum_mjerenja"] == "4.02.2021."
    assert gw["udaljenost_m"] < 200
    assert geo.nearest_groundwater(45.1, 16.1, max_dist_m=1000.0) is None


def test_banovina_bbox():
    assert in_banovina(45.4375, 16.2739)      # Petrinja
    assert not in_banovina(43.5081, 16.4402)  # Split


def test_placeholder_points_dropped(tmp_path):
    pt = lambda lon, lat, d: {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                              "properties": {"dubina_do": d, "datum_mjerenja": "4.02.2021."}}
    fc = {"type": "FeatureCollection", "features": [pt(16.2739, 45.4375, 2.0), pt(16.5, -90, 0)]}
    (tmp_path / "groundwater.geojson").write_text(json.dumps(fc), encoding="utf-8")
    geo = Geohazards(tmp_path)
    assert len(geo.layers["groundwater"].geoms) == 1
    assert geo.nearest_groundwater(45.4375, 16.2739)["dubina_do"] == 2.0


def test_well_without_date_is_not_used(tmp_path):
    def pt(lon, lat, d, date):
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"dubina_do": d, "datum_mjerenja": date}}
    fc = {"type": "FeatureCollection", "features": [pt(16.2739, 45.4375, 0, ""), pt(16.2740, 45.4376, 4.4, None)]}
    (tmp_path / "groundwater.geojson").write_text(json.dumps(fc), encoding="utf-8")
    geo = Geohazards(tmp_path)
    assert geo.nearest_groundwater(45.4375, 16.2739) is None
    fc["features"].append(pt(16.2745, 45.4380, 2.0, "4.02.2021."))
    (tmp_path / "groundwater.geojson").write_text(json.dumps(fc), encoding="utf-8")
    assert Geohazards(tmp_path).nearest_groundwater(45.4375, 16.2739)["dubina_do"] == 2.0
