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
