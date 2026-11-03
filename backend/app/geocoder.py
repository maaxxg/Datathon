"""SQLite FTS5 address geocoder backed by DGU Adrese INSPIRE (data/addresses.sqlite)."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

TOKEN_RE = re.compile(r"\w+", re.UNICODE)
# House number: digits, optional letter suffix, optional "/sub" part ("45", "45A", "12/1", "12/1A").
NUMBER_RE = re.compile(r"(?<![\w/])\d+[^\W\d_]{0,2}(?:/\d+[^\W\d_]{0,2})?(?![\w/])", re.UNICODE)


def fold_query(raw: str) -> str:
    """Map Croatian D-stroke to 'd' (the index holds both 'd' and 'dj' forms). 'dj' is never rewritten."""
    return raw.replace("đ", "d").replace("Đ", "D")


def fts_query(raw: str) -> str:
    """Turn user input into a safe FTS5 prefix query: every token is a quoted bound string with a trailing *."""
    tokens = TOKEN_RE.findall(fold_query(raw).strip())
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens[:8])


def _number_token(raw: str) -> str:
    """First house-number-like token ("45", "45a", "12/1"), not a 5-digit postcode."""
    for m in NUMBER_RE.finditer(raw):
        tok = m.group(0)
        if not (len(tok) == 5 and tok.isdigit()):
            return tok.lower()
    return ""


def format_label(street: str, number: str, settlement: str, municipality: str, postcode: str) -> str:
    street_part = " ".join(p for p in (street, number) if p).strip()
    place_part = " ".join(p for p in (postcode, settlement) if p).strip()
    if municipality and municipality.lower() != (settlement or "").lower():
        place_part = f"{place_part} ({municipality})".strip()
    return ", ".join(p for p in (street_part, place_part) if p)


class AddressGeocoder:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        if db_path.is_file():
            # Open read-only; check_same_thread=False allows use across FastAPI worker threads
            uri = f"file:{db_path.as_posix()}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

    def available(self) -> bool:
        return self._conn is not None

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if self._conn is None:
            return []
        match = fts_query(query)
        if not match:
            return []
        num_tok = _number_token(query)
        cur = self._conn.execute(
            """
            SELECT a.id, a.street, a.number, a.settlement, a.municipality, a.postcode, a.lat, a.lon
            FROM address_fts f
            JOIN address a ON a.id = f.rowid
            WHERE address_fts MATCH ?
            ORDER BY CASE WHEN ? = '' THEN 3
                          WHEN lower(a.number) = ? THEN 0
                          -- "45" -> "45A", "45/1" before "450" (a suffix is not another digit)
                          WHEN lower(a.number) LIKE ? || '%'
                               AND substr(a.number, length(?) + 1, 1) NOT GLOB '[0-9]' THEN 1
                          WHEN lower(a.number) LIKE ? || '%' THEN 2
                          ELSE 3 END,
                     bm25(address_fts), a.id
            LIMIT ?
            """,
            (match, num_tok, num_tok, num_tok, num_tok, num_tok, max(1, min(limit, 50))),
        )
        results = []
        for r in cur.fetchall():
            results.append({
                "id": r["id"],
                "label": format_label(
                    r["street"] or "", r["number"] or "",
                    r["settlement"] or "", r["municipality"] or "", r["postcode"] or "",
                ),
                "street": r["street"] or "",
                "number": r["number"] or "",
                "settlement": r["settlement"] or "",
                "municipality": r["municipality"] or "",
                "postcode": r["postcode"] or "",
                "lat": round(float(r["lat"]), 6),
                "lon": round(float(r["lon"]), 6),
            })
        return results

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
