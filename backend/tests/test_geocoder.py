import importlib.util
import sqlite3
from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest
from fastapi.testclient import TestClient

from app import main
from app.geocoder import AddressGeocoder, _number_token, format_label, fts_query

# The pipeline script is not a package; load it by path.
_spec = importlib.util.spec_from_file_location(
    "build_address_index", Path(__file__).resolve().parents[2] / "pipeline" / "build_address_index.py"
)
pipe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pipe)

NS = ('xmlns:ad="http://inspire.ec.europa.eu/schemas/ad/4.0" xmlns:gml="http://www.opengis.net/gml/3.2" '
      'xmlns:xlink="http://www.w3.org/1999/xlink"')


def _designator(value: str, kind: str) -> str:
    return (f'<ad:designator><ad:LocatorDesignator><ad:designator>{value}</ad:designator>'
            f'<ad:type xlink:href="http://inspire.ec.europa.eu/codelist/LocatorDesignatorTypeValue/{kind}"/>'
            f'</ad:LocatorDesignator></ad:designator>')


def _address_xml(designators: list[tuple[str, str]], pos: str = "2561799.19 4781765.61") -> str:
    return (f'<ad:Address {NS} gml:id="Address.1"><ad:position><ad:GeographicPosition><ad:geometry>'
            f'<gml:Point gml:id="g1"><gml:pos>{pos}</gml:pos></gml:Point></ad:geometry>'
            f'</ad:GeographicPosition></ad:position><ad:locator><ad:AddressLocator>'
            + "".join(_designator(v, k) for v, k in designators) +
            '</ad:AddressLocator></ad:locator><ad:component xlink:href="#T.1"/></ad:Address>')


NAMES = {"T.1": ("ThoroughfareName", "Ulica Test")}


def test_parse_address_concatenates_number_and_extension():
    row = pipe.parse_address(fromstring(_address_xml([("45", "addressNumber"), ("A", "addressNumberExtension")])), NAMES)
    assert row[0] == "Ulica Test" and row[1] == "45A"
    row = pipe.parse_address(fromstring(_address_xml([("12", "addressNumber"), ("/1", "addressNumberExtension")])), NAMES)
    assert row[1] == "12/1"
    row = pipe.parse_address(fromstring(_address_xml([("7", "addressNumber")])), NAMES)
    assert row[1] == "7"


def test_parse_address_axis_order_known_point():
    # Known address Matije Gupca 12, Petrinja: LAEA pos is (northing, easting).
    from pyproj import Transformer
    e, n = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True).transform(16.271776, 45.441024)
    row = pipe.parse_address(fromstring(_address_xml([("12", "addressNumber")], pos=f"{n} {e}")), NAMES)
    assert row[5] == pytest.approx(45.441024, abs=1e-5)
    assert row[6] == pytest.approx(16.271776, abs=1e-5)
    assert pipe.in_croatia(row[5], row[6])
    # swapped axes land outside Croatia and must be skipped, not "fixed"
    swapped = pipe.parse_address(fromstring(_address_xml([("12", "addressNumber")], pos=f"{e} {n}")), NAMES)
    assert not pipe.in_croatia(swapped[5], swapped[6])


def test_search_text_adds_d_and_dj_forms():
    text = pipe.search_text("Ulica Đure Đakovića", "1", "Đakovo", "Đakovo", "31400")
    assert "dakovo" in text.split() and "djakovo" in text.split()
    assert "Đakovo" in text  # original kept
    assert pipe.search_text("Rimska ulica", "19", "Sisak", "Sisak", "44000") == "Rimska ulica 19 Sisak 44000"


def _seed_db(path: Path, rows: list[tuple]) -> None:
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE address(id INTEGER PRIMARY KEY, street TEXT, number TEXT, settlement TEXT,
                             municipality TEXT, postcode TEXT, lat REAL, lon REAL);
        CREATE VIRTUAL TABLE address_fts USING fts5(label, content='', tokenize='unicode61 remove_diacritics 2');
    """)
    for row in rows:
        cur = db.execute(
            "INSERT INTO address(street,number,settlement,municipality,postcode,lat,lon) VALUES (?,?,?,?,?,?,?)", row)
        db.execute("INSERT INTO address_fts(rowid,label) VALUES (?,?)", (cur.lastrowid, pipe.search_text(*row[:5])))
    db.commit()
    db.close()


ROWS = [
    ("Ulica Matije Gupca", "12", "Petrinja", "Petrinja", "44250", 45.4375, 16.2739),
    ("Ulica Matije Gupca", "12/1", "Petrinja", "Petrinja", "44250", 45.4376, 16.2740),
    ("Radićeva ulica", "5", "Petrinja", "Petrinja", "44250", 45.4401, 16.2782),
    ("Rimska ulica", "19", "Sisak", "Sisak", "44000", 45.4840, 16.3740),
    ("Ulica kralja Tomislava", "3", "Glina", "Glina", "44400", 45.3381, 16.0886),
    ("Ulica Bartolovci", "450", "Bartolovci", "Bartolovci", "42000", 46.3, 16.4),
    ("Ulica Bartolovci", "45A", "Bartolovci", "Bartolovci", "42000", 46.3, 16.41),
    ("Ulica Bartolovci", "45", "Bartolovci", "Bartolovci", "42000", 46.3, 16.42),
    ("Ulica Bartolovci", "45B", "Bartolovci", "Bartolovci", "42000", 46.3, 16.43),
    ("Trg Ante Starčevića", "1", "Đakovo", "Đakovo", "31400", 45.31, 18.4),
    ("Ulica podjela", "2", "Podjela", "Podjela", "10000", 45.8, 16.0),
]


@pytest.fixture()
def geo(tmp_path):
    _seed_db(tmp_path / "addresses.sqlite", ROWS)
    g = AddressGeocoder(tmp_path / "addresses.sqlite")
    yield g
    g.close()


def test_fts_query_sanitises_and_adds_prefix():
    assert fts_query("Radićeva 5, Petrinja!") == '"Radićeva"* "5"* "Petrinja"*'
    assert fts_query("   ") == ""
    assert fts_query("Đakovo") == '"Dakovo"*'
    assert fts_query("podjela odjel") == '"podjela"* "odjel"*'


def test_number_token():
    assert _number_token("Ulica 45A Bartolovci") == "45a"
    assert _number_token("Gupca 12/1 Petrinja") == "12/1"
    assert _number_token("Gupca 12 44250 Petrinja") == "12"
    assert _number_token("Petrinja") == ""


def test_format_label():
    assert format_label("Rimska ulica", "19", "Sisak", "Sisak", "44000") == "Rimska ulica 19, 44000 Sisak"
    assert format_label("Glavna", "1", "Mošćenica", "Petrinja", "44250") == "Glavna 1, 44250 Mošćenica (Petrinja)"


def test_diacritic_insensitive_search(geo):
    hits = geo.search("radiceva petrinja")
    assert [h["street"] for h in hits] == ["Radićeva ulica"]
    assert hits[0]["lat"] == 45.4401
    assert geo.search("") == []


def test_suffix_search_and_ranking(geo):
    assert geo.search("bartolovci 45a")[0]["number"] == "45A"
    assert geo.search("gupca 12/1 petrinja")[0]["number"] == "12/1"
    numbers = [h["number"] for h in geo.search("bartolovci 45")]
    assert numbers[0] == "45"
    assert numbers.index("45A") < numbers.index("450")
    assert numbers.index("45B") < numbers.index("450")
    labels = [h["label"] for h in geo.search("bartolovci")]
    assert len(labels) == len(set(labels))


def test_dj_folding(geo):
    for q in ("dakovo", "djakovo", "Đakovo", "ĐAKOVO"):
        assert any(h["settlement"] == "Đakovo" for h in geo.search(q)), q
    assert geo.search("Đakovo")[0]["label"].count("Đakovo") >= 1  # label keeps the original letter
    assert [h["settlement"] for h in geo.search("podjela")] == ["Podjela"]


@pytest.mark.parametrize("q", ['"', "*", ":", "^", "-", "(", "AND", "NEAR", 'a" OR "b', "NEAR(a b)", "col:x", "a -b", "%", "_", "--"])
def test_fts_injection_strings(geo, q):
    geo.search(q)  # must not raise


@pytest.fixture()
def client(tmp_path):
    _seed_db(tmp_path / "addresses.sqlite", ROWS)
    g = AddressGeocoder(tmp_path / "addresses.sqlite")
    old = main.state.get("geocoder")
    main.state["geocoder"] = g
    yield TestClient(main.app)  # no `with`: lifespan (HV client, data dir) is not started
    g.close()
    if old is None:
        main.state.pop("geocoder", None)
    else:
        main.state["geocoder"] = old


@pytest.mark.parametrize("q", ['"', "*", ":", "^", "-", "(", "AND", "NEAR", 'x" OR "y'])
def test_api_injection_strings_return_200(client, q):
    r = client.get("/api/addresses", params={"q": q + q})
    assert r.status_code == 200
    assert r.json()["available"] is True


def test_api_validation(client):
    assert client.get("/api/addresses", params={"q": "a" * 121}).status_code == 422
    assert client.get("/api/addresses", params={"q": "a" * 120}).status_code == 200
    r = client.get("/api/addresses", params={"q": "P"})
    assert r.status_code == 200 and r.json() == {"available": True, "results": []}


def test_api_contract_with_index(client):
    r = client.get("/api/addresses", params={"q": "radiceva petrinja"})
    body = r.json()
    assert r.status_code == 200 and body["available"] is True
    assert set(body["results"][0]) == {"id", "label", "street", "number", "settlement", "municipality",
                                       "postcode", "lat", "lon"}
    assert body["results"][0]["label"] == "Radićeva ulica 5, 44250 Petrinja"


def test_api_contract_without_index(tmp_path):
    g = AddressGeocoder(tmp_path / "nonexistent.sqlite")
    old = main.state.get("geocoder")
    main.state["geocoder"] = g
    try:
        r = TestClient(main.app).get("/api/addresses", params={"q": "Petrinja"})
    finally:
        if old is None:
            main.state.pop("geocoder", None)
        else:
            main.state["geocoder"] = old
    assert r.status_code == 200
    assert r.json() == {"available": False, "results": []}
