import sqlite3
from pathlib import Path

from app.geocoder import AddressGeocoder, format_label, fts_query


def _seed_db(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE address(id INTEGER PRIMARY KEY, street TEXT, number TEXT, settlement TEXT,
                             municipality TEXT, postcode TEXT, lat REAL, lon REAL);
        CREATE VIRTUAL TABLE address_fts USING fts5(label, content='address', content_rowid='id',
                                                    tokenize='unicode61 remove_diacritics 2');
    """)
    rows = [
        ("Ulica Matije Gupca", "12", "Petrinja", "Petrinja", "44250", 45.4375, 16.2739),
        ("Radićeva ulica", "5", "Petrinja", "Petrinja", "44250", 45.4401, 16.2782),
        ("Rimska ulica", "19", "Sisak", "Sisak", "44000", 45.4840, 16.3740),
        ("Ulica kralja Tomislava", "3", "Glina", "Glina", "44400", 45.3381, 16.0886),
    ]
    for row in rows:
        cur = db.execute(
            "INSERT INTO address(street,number,settlement,municipality,postcode,lat,lon) VALUES (?,?,?,?,?,?,?)",
            row,
        )
        label = " ".join(p for p in row[:5] if p)
        db.execute("INSERT INTO address_fts(rowid,label) VALUES (?,?)", (cur.lastrowid, label))
    db.commit()
    db.close()


def test_fts_query_sanitises_and_adds_prefix():
    assert fts_query("Radićeva 5, Petrinja!") == '"Radićeva"* "5"* "Petrinja"*'
    assert fts_query("   ") == ""


def test_format_label():
    assert format_label("Rimska ulica", "19", "Sisak", "Sisak", "44000") == "Rimska ulica 19, 44000 Sisak"
    assert format_label("Glavna", "1", "Mošćenica", "Petrinja", "44250") == "Glavna 1, 44250 Mošćenica (Petrinja)"


def test_geocoder_search_diacritic_insensitive(tmp_path):
    db_path = tmp_path / "addresses.sqlite"
    _seed_db(db_path)
    geo = AddressGeocoder(db_path)
    assert geo.available()

    # Search without diacritics ('radiceva' matches 'Radićeva')
    hits = geo.search("radiceva petrinja")
    assert len(hits) == 1
    assert hits[0]["street"] == "Radićeva ulica"
    assert hits[0]["number"] == "5"
    assert hits[0]["settlement"] == "Petrinja"
    assert hits[0]["lat"] == 45.4401

    # Partial prefix search
    hits_pet = geo.search("petrinj", limit=2)
    assert len(hits_pet) == 2

    assert geo.search("") == []
    geo.close()


def test_geocoder_missing_file(tmp_path):
    geo = AddressGeocoder(tmp_path / "nonexistent.sqlite")
    assert not geo.available()
    assert geo.search("Petrinja") == []
