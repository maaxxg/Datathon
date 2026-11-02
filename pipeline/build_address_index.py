"""Build a SQLite FTS5 address index from DGU 'Adrese INSPIRE' (GML 3.2.1, ETRS89/LAEA).

Usage:
    # download once (~86 MB): https://geoportal.dgu.hr/services/atom/INSPIRE_Addresses_(AD).zip
    python pipeline/build_address_index.py data/raw/INSPIRE_Addresses_(AD).zip --out data/addresses.sqlite

DGU's INSPIRE AD zip contains four GML files:
- ThoroughfareName.gml: street names (<gn:text>)
- AdminUnitName.gml: settlements (4thOrder / localId NA.*, <gn:text>) and 1stOrder country
- PostalDescriptor.gml: postCode (<ad:postCode>) and post office name (<gn:text>)
- Address.gml: Address features referencing the above via <ad:component xlink:href="#..."/>
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
XLINK_TITLE = "{http://www.w3.org/1999/xlink}title"
NAME_FEATURES = {"ThoroughfareName", "AdminUnitName", "AddressAreaName", "PostalDescriptor"}

laea_to_wgs84 = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def gml_members(zip_path: Path, exclude_address: bool = False):
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.lower().endswith((".gml", ".xml")):
                continue
            if exclude_address and name.lower().startswith("address."):
                continue
            with z.open(name) as fh:
                yield name, fh


def collect_names(zip_path: Path) -> dict[str, tuple[str, str]]:
    """gml:id -> (kind, value) for street/settlement/postal features."""
    names: dict[str, tuple[str, str]] = {}
    for _, fh in gml_members(zip_path, exclude_address=True):
        for _, el in iterparse(fh, events=("end",)):
            kind = local(el.tag)
            if kind not in NAME_FEATURES:
                continue
            gid = el.get(f"{GML}id")
            if not gid:
                el.clear()
                continue
            if kind == "PostalDescriptor":
                post_text = next((t.text.strip() for t in el.iter() if local(t.tag) == "text" and t.text), "")
                post_code = next((t.text.strip() for t in el.iter() if local(t.tag) == "postCode" and t.text), "")
                names[gid] = ("PostalDescriptor", f"{post_code}|{post_text}")
            elif kind == "AdminUnitName":
                level = next((t.get(XLINK_TITLE, "") for t in el.iter() if local(t.tag) == "level"), "")
                text = next((t.text.strip() for t in el.iter() if local(t.tag) == "text" and t.text), "")
                if text and level != "1stOrder":
                    names[gid] = ("Settlement", text)
            else:
                text = next((t.text.strip() for t in el.iter() if local(t.tag) == "text" and t.text), "")
                if text:
                    names[gid] = (kind, text)
            el.clear()
    return names


def iter_addresses(zip_path: Path, names: dict[str, tuple[str, str]]):
    with zipfile.ZipFile(zip_path) as z:
        addr_files = [n for n in z.namelist() if n.lower().startswith("address.") and n.lower().endswith((".gml", ".xml"))]
        if not addr_files:
            addr_files = [n for n in z.namelist() if n.lower().endswith((".gml", ".xml"))]
        for name in addr_files:
            with z.open(name) as fh:
                for _, el in iterparse(fh, events=("end",)):
                    if local(el.tag) != "Address":
                        continue
                    pos = next((p.text for p in el.iter(f"{GML}pos") if p.text), None)
                    number = next(
                        (d.text for d in el.iter() if local(d.tag) == "designator" and d.text and not len(d)),
                        "",
                    )
                    street = ""
                    settlement = ""
                    municipality = ""
                    postcode = ""
                    for comp in el.iter():
                        if local(comp.tag) == "component" and comp.get(XLINK):
                            ref = comp.get(XLINK).lstrip("#")
                            if ref in names:
                                kind, val = names[ref]
                                if kind == "ThoroughfareName" and not street:
                                    street = val
                                elif kind in ("Settlement", "AddressAreaName") and not settlement:
                                    settlement = val
                                elif kind == "PostalDescriptor":
                                    pc, po = val.split("|", 1)
                                    postcode = pc
                                    municipality = po
                    el.clear()
                    if not pos:
                        continue
                    a, b = (float(v) for v in pos.split()[:2])
                    # EPSG:3035 axis order in GML is northing, easting; fall back if the file uses x,y
                    lon, lat = laea_to_wgs84.transform(b, a)
                    if not (42.0 < lat < 47.0 and 13.0 < lon < 20.0):
                        lon, lat = laea_to_wgs84.transform(a, b)
                    yield (
                        street, number.strip(), settlement, municipality or settlement, postcode, lat, lon,
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
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript("""
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = MEMORY;
        CREATE TABLE address(id INTEGER PRIMARY KEY, street TEXT, number TEXT, settlement TEXT,
                             municipality TEXT, postcode TEXT, lat REAL, lon REAL);
        CREATE VIRTUAL TABLE address_fts USING fts5(label, content='address', content_rowid='id',
                                                    tokenize='unicode61 remove_diacritics 2');
    """)
    batch: list[tuple] = []
    n = 0
    for row in iter_addresses(zip_path, names):
        batch.append(row)
        n += 1
        if len(batch) >= 100_000:
            db.executemany(
                "INSERT INTO address(street,number,settlement,municipality,postcode,lat,lon) VALUES (?,?,?,?,?,?,?)",
                batch,
            )
            db.commit()
            batch.clear()
            print(f"{n} addresses", file=sys.stderr)
    if batch:
        db.executemany(
            "INSERT INTO address(street,number,settlement,municipality,postcode,lat,lon) VALUES (?,?,?,?,?,?,?)",
            batch,
        )
        db.commit()
        batch.clear()
    print("building FTS5 index...", file=sys.stderr)
    db.execute("""
        INSERT INTO address_fts(rowid, label)
        SELECT id,
               trim(street || ' ' || number || ' ' || settlement || ' ' ||
                    CASE WHEN municipality != settlement THEN municipality ELSE '' END || ' ' || postcode)
        FROM address;
    """)
    db.commit()
    db.execute("PRAGMA journal_mode = DELETE;")
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
