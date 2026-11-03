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
import re
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


CROATIA_BBOX = (13.4, 42.3, 19.5, 46.6)  # lon_min, lat_min, lon_max, lat_max


def parse_address(el, names: dict[str, tuple[str, str]], stats: Counter | None = None):
    """Parse one <ad:Address> element into a row tuple, or None when it has no position.

    The house number is assembled by LocatorDesignator type, not by file order:
    addressNumber + addressNumberExtension + "/" + addressNumber2ndExtension
    (117 + 1 -> "117/1", 105 + A + 1 -> "105A/1", 12 + A -> "12A"). Per-type counts go to stats.
    """
    pos = next((p.text for p in el.iter(f"{GML}pos") if p.text), None)
    if not pos:
        return None
    parts: dict[str, str] = {}
    for ld in el.iter():
        if local(ld.tag) != "LocatorDesignator":
            continue
        value = next((d.text.strip() for d in ld if local(d.tag) == "designator" and d.text and d.text.strip()), "")
        kind = next((t.get(XLINK, "").rsplit("/", 1)[-1] for t in ld if local(t.tag) == "type"), "")
        if stats is not None:
            stats[f"designator:{kind or 'unknown'}"] += 1
        if value and kind and kind not in parts:
            parts[kind] = value
    second = parts.get("addressNumber2ndExtension", "")
    if second and not second.startswith("/"):
        second = "/" + second
    number = parts.get("addressNumber", "") + parts.get("addressNumberExtension", "") + second
    street = settlement = municipality = postcode = ""
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
                    postcode, municipality = val.split("|", 1)
    # EPSG:3035 GML pos is (northing, easting); with always_xy the transformer wants (easting, northing).
    northing, easting = (float(v) for v in pos.split()[:2])
    lon, lat = laea_to_wgs84.transform(easting, northing)
    return (street, number, settlement, municipality or settlement, postcode, lat, lon)


def in_croatia(lat: float, lon: float) -> bool:
    w, s, e, n = CROATIA_BBOX
    return w <= lon <= e and s <= lat <= n


def iter_addresses(zip_path: Path, names: dict[str, tuple[str, str]], stats: Counter | None = None):
    """Yield address rows; points outside the Croatia bbox are skipped and counted in stats['skipped']."""
    stats = stats if stats is not None else Counter()
    with zipfile.ZipFile(zip_path) as z:
        addr_files = [n for n in z.namelist() if n.lower().startswith("address.") and n.lower().endswith((".gml", ".xml"))]
        if not addr_files:
            addr_files = [n for n in z.namelist() if n.lower().endswith((".gml", ".xml"))]
        for name in addr_files:
            with z.open(name) as fh:
                for _, el in iterparse(fh, events=("end",)):
                    if local(el.tag) != "Address":
                        continue
                    row = parse_address(el, names, stats)
                    el.clear()
                    if row is None:
                        continue
                    if not in_croatia(row[5], row[6]):
                        stats["skipped"] += 1
                        continue
                    if "/" in row[1]:
                        stats["number_with_slash"] += 1
                    yield row


def number_tokens(number: str) -> str:
    """Base numbers of a house number, so exact number tokens match suffixed numbers:
    "45A" -> "45", "105A/1" -> "105 1" (the tokenizer already yields "105a" and "1")."""
    bases = []
    for part in number.split("/"):
        digits = re.match(r"\d+", part)
        if digits and digits.group(0) != part:
            bases.append(digits.group(0))
    return " ".join(bases)


def search_text(street: str, number: str, settlement: str, municipality: str, postcode: str) -> str:
    """Text indexed by FTS5, lower-cased tokens are split by unicode61.
    - Words with Croatian D-stroke get both a 'd' and a 'dj' form (unicode61 does not fold it).
    - The house number also yields its base number(s), because the query matches number tokens exactly."""
    label = " ".join(p for p in (
        street, number, settlement, municipality if municipality != settlement else "", postcode,
    ) if p)
    extra = []
    for word in label.split():
        low = word.lower()
        if "đ" in low:
            extra.append(low.replace("đ", "d"))
            extra.append(low.replace("đ", "dj"))
    extra.append(number_tokens(number))
    return " ".join(p for p in [label, *extra] if p)


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
        CREATE VIRTUAL TABLE address_fts USING fts5(label, content='',
                                                    tokenize='unicode61 remove_diacritics 2');
    """)
    batch: list[tuple] = []
    n = 0
    stats: Counter[str] = Counter()
    for row in iter_addresses(zip_path, names, stats):
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
    rows = db.execute("SELECT id, street, number, settlement, municipality, postcode FROM address ORDER BY id").fetchall()
    db.executemany(
        "INSERT INTO address_fts(rowid, label) VALUES (?, ?)",
        ((r[0], search_text(*r[1:])) for r in rows),
    )
    db.commit()
    db.execute("PRAGMA journal_mode = DELETE;")
    db.close()
    for key in sorted(stats):
        if key != "skipped":
            print(f"{key}: {stats[key]}")
    print(f"done: {n} addresses indexed, {stats['skipped']} skipped (outside Croatia bbox) -> {out}")


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
