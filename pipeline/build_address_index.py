"""Build a SQLite FTS5 address index from DGU 'Adrese INSPIRE' (GML 3.2.1, ETRS89/LAEA).

Usage:
    # download once (~84 MB): https://geoportal.dgu.hr/services/atom/INSPIRE_Addresses_(AD).zip
    python pipeline/build_address_index.py data/raw/INSPIRE_Addresses_(AD).zip --out data/addresses.sqlite

INSPIRE AD keeps street, settlement and postal names in separate features that
addresses reference via xlink:href, so the file is parsed in two streaming passes.
NOTE: written against the INSPIRE AD 4.0 schema; not yet run on the real DGU file.
Run with --inspect first to print the element names actually present.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree.ElementTree import iterparse

from pyproj import Transformer

GML = "{http://www.opengis.net/gml/3.2}"
XLINK = "{http://www.w3.org/1999/xlink}href"
NAME_FEATURES = {"ThoroughfareName", "AdminUnitName", "AddressAreaName", "PostalDescriptor"}

laea_to_wgs84 = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def gml_members(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.lower().endswith((".gml", ".xml")):
                with z.open(name) as fh:
                    yield name, fh


def collect_names(zip_path: Path) -> dict[str, tuple[str, str]]:
    """gml:id -> (kind, text) for street/settlement/postal features."""
    names: dict[str, tuple[str, str]] = {}
    for _, fh in gml_members(zip_path):
        for _, el in iterparse(fh, events=("end",)):
            kind = local(el.tag)
            if kind in NAME_FEATURES:
                gid = el.get(f"{GML}id")
                text = next((t.text for t in el.iter() if local(t.tag) in ("text", "postCode") and t.text), None)
                if gid and text:
                    names[gid] = (kind, text.strip())
                el.clear()
    return names


def iter_addresses(zip_path: Path, names: dict[str, tuple[str, str]]):
    for _, fh in gml_members(zip_path):
        for _, el in iterparse(fh, events=("end",)):
            if local(el.tag) != "Address":
                continue
            pos = next((p.text for p in el.iter(f"{GML}pos") if p.text), None)
            number = next((d.text for d in el.iter() if local(d.tag) == "designator" and d.text and not len(d)), "")
            parts: dict[str, str] = {}
            for comp in el.iter():
                if local(comp.tag) == "component" and comp.get(XLINK):
                    ref = comp.get(XLINK).lstrip("#")
                    if ref in names:
                        kind, text = names[ref]
                        parts.setdefault(kind, text)
            el.clear()
            if not pos:
                continue
            a, b = (float(v) for v in pos.split()[:2])
            # EPSG:3035 axis order in GML is northing, easting; fall back if the file uses x,y
            lon, lat = laea_to_wgs84.transform(b, a)
            if not (42.0 < lat < 47.0 and 13.0 < lon < 20.0):
                lon, lat = laea_to_wgs84.transform(a, b)
            yield (
                parts.get("ThoroughfareName", ""), number.strip(),
                parts.get("AddressAreaName", ""), parts.get("AdminUnitName", ""),
                parts.get("PostalDescriptor", ""), lat, lon,
            )


def inspect(zip_path: Path, limit: int = 300_000) -> None:
    counts: Counter[str] = Counter()
    for name, fh in gml_members(zip_path):
        print("file:", name)
        for i, (_, el) in enumerate(iterparse(fh, events=("end",))):
            counts[local(el.tag)] += 1
            el.clear()
            if i > limit:
                break
    for tag, n in counts.most_common(40):
        print(f"{n:>8}  {tag}")


def build(zip_path: Path, out: Path) -> None:
    names = collect_names(zip_path)
    print(f"name features: {len(names)}", file=sys.stderr)
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript("""
        CREATE TABLE address(id INTEGER PRIMARY KEY, street TEXT, number TEXT, settlement TEXT,
                             municipality TEXT, postcode TEXT, lat REAL, lon REAL);
        CREATE VIRTUAL TABLE address_fts USING fts5(label, content='address', content_rowid='id',
                                                    tokenize='unicode61 remove_diacritics 2');
    """)
    n = 0
    for row in iter_addresses(zip_path, names):
        cur = db.execute("INSERT INTO address(street,number,settlement,municipality,postcode,lat,lon) "
                         "VALUES (?,?,?,?,?,?,?)", row)
        label = " ".join(p for p in (row[0], row[1], row[2], row[3], row[4]) if p)
        db.execute("INSERT INTO address_fts(rowid,label) VALUES (?,?)", (cur.lastrowid, label))
        n += 1
        if n % 100_000 == 0:
            db.commit()
            print(f"{n} addresses", file=sys.stderr)
    db.commit()
    db.close()
    print(f"done: {n} addresses -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip", type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/addresses.sqlite"))
    ap.add_argument("--inspect", action="store_true", help="print element counts and exit")
    args = ap.parse_args()
    if args.inspect:
        inspect(args.zip)
    else:
        build(args.zip, args.out)


if __name__ == "__main__":
    main()
