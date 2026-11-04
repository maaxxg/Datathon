"""API-level test of /api/report with HV mocked and no local data (no network)."""
from fastapi.testclient import TestClient

from app import main
from app.hv_flood import HVFloodClient

PETRINJA = {"lat": 45.4375, "lon": 16.2739}  # public test point, not a user address


def _client(monkeypatch, tmp_path, classes):
    async def fake_classify(self, lat, lon):
        return dict(classes)

    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(HVFloodClient, "classify", fake_classify)
    return TestClient(main.app)


def test_all_no_data(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path, {"velika": None, "srednja": None, "mala": None}) as c:
        body = c.get("/api/report", params=PETRINJA).json()
    assert body["all_no_data"] is True
    assert body["most_significant"] is None
    assert "nema dostupnih podataka" in body["summary"]
    assert "nije utvrđena" not in body["summary"]
    assert all(h["explanation"] for h in body["hazards"])
    assert [a["hazard"] for a in body["recommended_actions"]] == ["general"]


def test_not_all_no_data_when_hv_answers(monkeypatch, tmp_path):
    classes = {"velika": "d_lt_0_5", "srednja": "d_lt_0_5", "mala": "d_lt_0_5"}
    with _client(monkeypatch, tmp_path, classes) as c:
        body = c.get("/api/report", params=PETRINJA).json()
    assert body["all_no_data"] is False
    assert body["most_significant"]["hazard"] == "flood"
    assert "Nema podataka za:" in body["summary"]


def test_health_map_layers_flag(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path, {}) as c:
        assert c.get("/api/health").json()["map_layers_loaded"] is False
    (tmp_path / "map").mkdir()
    for f in main.MAP_FILES:
        (tmp_path / "map" / f).write_bytes(b"x")
    with _client(monkeypatch, tmp_path, {}) as c:
        assert c.get("/api/health").json()["map_layers_loaded"] is True


def test_map_data_serves_file_and_404(tmp_path):
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    (tmp_path / "map").mkdir()
    (tmp_path / "map" / "efas_bounds.json").write_text("[[1,2]]")
    # same mount call as main.py, on a tmp dir (main.DATA_DIR is fixed at import time)
    app = FastAPI()
    app.mount("/api/map-data", StaticFiles(directory=tmp_path / "map", check_dir=False))
    c = TestClient(app)
    ok = c.get("/api/map-data/efas_bounds.json")
    assert ok.status_code == 200 and ok.json() == [[1, 2]]
    assert c.get("/api/map-data/missing.png").status_code == 404


def test_map_data_geojson_served_as_json(tmp_path):
    import app.main  # noqa: F401  (registers the .geojson MIME type)
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    (tmp_path / "geohazard_x.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    app_ = FastAPI()
    app_.mount("/api/map-data", StaticFiles(directory=tmp_path, check_dir=False))
    r = TestClient(app_).get("/api/map-data/geohazard_x.geojson")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_report_hv_partial_outage_with_efas(monkeypatch, tmp_path):
    class FakeEFAS:
        def available(self):
            return True

        def depths(self, lat, lon):
            return {10: 0.17, 100: 1.03, 500: 1.42}

        def close(self):
            pass

    with _client(monkeypatch, tmp_path, {"velika": "outside", "srednja": "outside", "mala": None}) as c:
        main.state["efas"] = FakeEFAS()
        body = c.get("/api/report", params=PETRINJA).json()
    flood = next(h for h in body["hazards"] if h["hazard"] == "flood")
    assert flood["level"] == "visoko"
    assert flood["detail"]["hv_status"] == "unavailable"
    assert flood["detail"]["hv_unavailable_scenarios"] == ["mala"]
    assert "mala vjerojatnost (privremeni prekid)" in flood["notes"][0]
    assert "trenutačno ne odgovara" in body["summary"]
