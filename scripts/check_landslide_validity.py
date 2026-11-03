"""Check whether invalid landslide polygons change the report's class near validity defects.

Read-only on data/. For every invalid polygon part of a susceptibility layer: repair that part alone with
shapely.make_valid, then compare Geohazards.susceptibility() (the real report code path, original geometry)
with the class from a repaired geometry set at points around each defect (CRS EPSG:4326, shapely order lon,lat).

  PY scripts/check_landslide_validity.py [--data data] [--layer landslide] [--radius-m 200] [--n 20] [--csv out.csv]
"""
from __future__ import annotations

import argparse
import csv
import math
import multiprocessing as mp
import re
import resource
import sys
import time
from collections import Counter
from pathlib import Path

import shapely
from shapely import STRtree
from shapely.geometry import MultiPolygon, Point, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.geohazards import Geohazards  # noqa: E402

ORDER = {"niska": 1, "srednja": 2, "visoka": 3}  # same rule as Geohazards.susceptibility()
_LOC_RE = re.compile(r"\[(-?[\d.eE+-]+) (-?[\d.eE+-]+)\]")
REPAIR_TIMEOUT_S = 120


def parse_defect(reason: str) -> tuple[float, float] | None:
    """Reason strings print 'x y' = lon lat, e.g. 'Self-intersection[16.40256 45.22683]'. Returns (lon, lat)."""
    m = _LOC_RE.search(reason)
    return (float(m.group(1)), float(m.group(2))) if m else None


def split_parts(geom) -> list[Polygon]:
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


def polygonal(geom):
    """Keep only Polygon/MultiPolygon components of a make_valid result."""
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = [g for g in getattr(geom, "geoms", []) if g.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(parts) if parts else None


def _repair_worker(part, q):
    q.put(shapely.to_wkb(polygonal(shapely.make_valid(part))))


def repair_part(part, timeout_s: float = REPAIR_TIMEOUT_S):
    """make_valid on one part in a forked process; None on timeout (caller reports 'nije popravljeno')."""
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    p = ctx.Process(target=_repair_worker, args=(part, q))
    p.start()
    try:
        data = q.get(timeout=timeout_s)
    except Exception:
        p.terminate()
        p.join()
        return None
    p.join()
    return shapely.from_wkb(data) if data is not None else None


def grid_offsets(radius_m: float, n: int) -> list[tuple[float, float]]:
    """(dx, dy) metre offsets: regular square grid inside the radius, n points nearest to the centre."""
    k = max(1, math.ceil(math.sqrt(n * 4 / math.pi)))
    step = 2 * radius_m / k
    cells = [(-radius_m + step * (i + 0.5), -radius_m + step * (j + 0.5)) for i in range(k) for j in range(k)]
    cells = [c for c in cells if math.hypot(*c) <= radius_m]
    return sorted(cells, key=lambda c: math.hypot(*c))[:n]


def offset_point(lon: float, lat: float, dx_m: float, dy_m: float) -> tuple[float, float]:
    """Metres -> degrees at the defect latitude. Returns (lon, lat)."""
    return lon + dx_m / (111_320.0 * math.cos(math.radians(lat))), lat + dy_m / 111_132.0


def best_class(values):
    values = [v for v in values if v]
    return max(values, key=lambda v: ORDER.get(v.lower(), 0)) if values else None


def defect_nodes(part) -> list[tuple[float, float]]:
    """All self-intersection nodes (lon, lat) of a part's rings. is_valid_reason reports only the first one.

    A noded ring has degree-2 vertices only (start vertex counted twice); a node reached by >= 3 line ends is a
    self-intersection/touch of the ring.
    """
    out = []
    for ring in [part.exterior, *part.interiors]:
        if ring.is_simple:
            continue
        ends = Counter()
        for ln in shapely.node(shapely.LineString(ring.coords)).geoms:
            ends[ln.coords[0]] += 1
            ends[ln.coords[-1]] += 1
        out += [k for k, v in ends.items() if v >= 3]
    return out


def find_invalid(geoms) -> list[dict]:
    """Invalid parts across features: feature index, part index, reason, defect (lon, lat)."""
    found = []
    for fi, g in enumerate(geoms):
        for pi, part in enumerate(split_parts(g)):
            if not shapely.is_valid(part):
                reason = shapely.is_valid_reason(part)
                nodes = defect_nodes(part)
                first = parse_defect(reason)
                if first and first not in nodes:
                    nodes.insert(0, first)
                found.append({"feature": fi, "part": pi, "reason": reason, "defect": first, "nodes": nodes,
                              "npts": shapely.get_num_coordinates(part)})
    return found


def build_repaired_set(geoms, props, invalid, timeout_s=REPAIR_TIMEOUT_S):
    """Flat list of (geometry, podloznost): valid parts unchanged, invalid parts repaired. Marks failures."""
    bad = {(d["feature"], d["part"]): d for d in invalid}
    out_g, out_p = [], []
    for fi, g in enumerate(geoms):
        for pi, part in enumerate(split_parts(g)):
            d = bad.get((fi, pi))
            if d is None:
                out_g.append(part)
            else:
                t0 = time.time()
                fixed = repair_part(part, timeout_s)
                d["repair_s"] = time.time() - t0
                d["repaired"] = fixed is not None
                if fixed is None:
                    continue  # excluded from the repaired set: points there are flagged, not silently valid
            if d is not None:
                out_g.append(fixed)
            out_p.append(props[fi].get("podloznost"))
    return out_g, out_p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--layer", default="landslide")
    ap.add_argument("--radius-m", type=float, default=200)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--csv")
    a = ap.parse_args(argv)
    t0 = time.time()

    gh = Geohazards(Path(a.data) / "geohazards")
    layer = gh.layers[a.layer]
    geoms, props = layer.geoms, layer.props
    invalid = find_invalid(geoms)
    n_parts = sum(len(split_parts(g)) for g in geoms)
    print(f"layer={a.layer} features={len(geoms)} parts={n_parts} invalid_parts={len(invalid)}")

    rep_g, rep_p = build_repaired_set(geoms, props, invalid)
    for d in invalid:
        print(f"  invalid f{d['feature']}p{d['part']} npts={d['npts']} repaired={d.get('repaired')} "
              f"({d.get('repair_s', 0):.1f}s) defect_nodes={len(d['nodes'])} reason={d['reason']}")
    tree = STRtree(rep_g)

    rows = []
    n_nodes = 0
    for d in invalid:
        for k, (lon0, lat0) in enumerate(d["nodes"]):
            n_nodes += 1
            offs = [(0.0, 0.0)] + grid_offsets(a.radius_m, a.n)
            for dx, dy in offs:
                lon, lat = offset_point(lon0, lat0, dx, dy)
                rc = gh.susceptibility(a.layer, lat, lon)  # real report path, original geometry
                idx = tree.query(Point(lon, lat), predicate="covered_by")
                fixed = best_class(rep_p[i] for i in idx)
                rows.append({"defect": f"f{d['feature']}p{d['part']}#{k}", "lon": lon0, "lat": lat0,
                             "dx_m": round(dx), "dy_m": round(dy), "report_class": rc, "repaired_class": fixed,
                             "match": rc == fixed, "repaired_part": bool(d.get("repaired"))})

    mism = [r for r in rows if not r["match"]]
    types = Counter(f"{r['report_class']}->{r['repaired_class']}" for r in mism)
    known = [r for r in rows if abs(r["lon"] - 16.40256) < 1e-4 and abs(r["lat"] - 45.22683) < 1e-4]
    print(f"known defect 16.40256 45.22683 listed: {sorted({r['defect'] for r in known})}")
    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 2 if sys.platform == "darwin" else 1024)
    unrepaired = [d for d in invalid if not d.get("repaired")]
    print(f"\nSUMMARY invalid_parts={len(invalid)} defect_nodes={n_nodes} parts_repaired={len(invalid) - len(unrepaired)} "
          f"not_repaired={len(unrepaired)} points_checked={len(rows)} mismatches={len(mism)} "
          f"({100 * len(mism) / max(1, len(rows)):.1f}%) types={dict(types)} "
          f"runtime_s={time.time() - t0:.0f} peak_rss_MB={rss:.0f}")
    for r in mism:
        print("MISMATCH", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
