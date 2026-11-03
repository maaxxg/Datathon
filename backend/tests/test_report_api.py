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


def test_health_map_layers_flag_and_static(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path, {}) as c:
        assert c.get("/api/health").json()["map_layers_loaded"] is False
    (tmp_path / "map").mkdir()
    for f in main.MAP_FILES:
        (tmp_path / "map" / f).write_bytes(b"x")
    with _client(monkeypatch, tmp_path, {}) as c:
        assert c.get("/api/health").json()["map_layers_loaded"] is True
