"""Build lightweight, display-only map layers for the frontend (brief 012).

Usage: PY pipeline/build_map_layers.py [--data data]

Input : <data>/geohazards/*.geojson (EPSG:4326, lon,lat), <data>/efas/rp{10,100,500}.tif (EPSG:4326, 90 m)
Output: <data>/map/  (git-ignored, served by the API at /api/map-data)
  geohazard_{landslide,liquefaction,sinkhole}.geojson  simplified, only property `podloznost`
  geohazard_unfavourable.geojson                       simplified, no properties
  banovina_coverage.geojson                            bbox from backend/app/layers.yaml
  efas_rp{10,100,500}.png + efas_bounds.json           classified RGBA overlay, ~180 m

The output is for DISPLAY ONLY. Reports keep using the original files. EFAS is
downsampled with MAX (a pixel is flooded if any source pixel is), which is the
conservative choice. Derived from EFAS v3.1.1 (ODbL 1.0, D14). Deterministic:
no timestamps, sorted keys.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from PIL import Image
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parents[1]
LAYERS_YAML = ROOT / "backend" / "app" / "layers.yaml"

SIMPLIFY_TOL = {"landslide": 0.0004, "liquefaction": 0.0002, "sinkhole": 0.0002, "unfavourable": 0.0002}
MAX_GEOJSON_BYTES = 3 * 1024 * 1024
MAX_TEX = 4096
NODATA = -9999.0
BBOX_MARGIN = 0.05
COORD_DECIMALS = 5

# Depth classes (m): 0 < d <= 0.5, <= 1.5, <= 2.5, > 2.5. Purples, distinct from the HV blues.
EFAS_COLOURS = [
    (0.5, (216, 180, 254, 200)),   # #D8B4FE
    (1.5, (168, 85, 247, 200)),    # #A855F7
    (2.5, (126, 34, 206, 200)),    # #7E22CE
    (np.inf, (59, 7, 100, 200)),   # #3B0764
]


def banovina_bbox() -> list[float]:
    return yaml.safe_load(LAYERS_YAML.read_text(encoding="utf-8"))["coverages"]["banovina"]


def _polygons(geom):
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [p for g in getattr(geom, "geoms", []) for p in _polygons(g)]


def _round_ring(coords) -> list:
    return [[round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)] for x, y in coords]


def _poly_coords(p: Polygon) -> list:
    return [_round_ring(p.exterior.coords)] + [_round_ring(r.coords) for r in p.interiors]


def simplify_geometry(geom, tol: float) -> list[Polygon]:
    """Simplify each polygon part first (cheap), repair only the simplified result, drop empties."""
    out: list[Polygon] = []
    for part in _polygons(geom):
        s = part.simplify(tol, preserve_topology=False)
        if s.is_empty:
            continue
        if not s.is_valid:
            s = make_valid(s)
        out.extend(p for p in _polygons(s) if not p.is_empty)
    return out


def _to_geometry(polys: list[Polygon]) -> dict | None:
    # Round BEFORE building coordinates; rounding can only create display artefacts.
    coords = [_poly_coords(p) for p in polys if len(p.exterior.coords) >= 4]
    return {"type": "MultiPolygon", "coordinates": coords} if coords else None


def process_geojson(src: dict, tol: float, keep_props: tuple[str, ...]) -> dict:
    feats = []
    for f in src["features"]:
        geom = _to_geometry(simplify_geometry(shape(f["geometry"]), tol))
        if geom is None:
            continue
        props = {k: f["properties"][k] for k in keep_props if k in (f.get("properties") or {})}
        feats.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": feats}


def assert_inside(fc: dict, bbox: list[float], margin: float = BBOX_MARGIN) -> None:
    w, s, e, n = bbox
    def walk(c):
        if isinstance(c[0], (int, float)):
            lon, lat = c[0], c[1]
            assert w - margin <= lon <= e + margin and s - margin <= lat <= n + margin, \
                f"coordinate outside Banovina bbox: {lon},{lat}"
        else:
            for x in c:
                walk(x)
    for f in fc["features"]:
        walk(f["geometry"]["coordinates"])


def dump(obj, path: Path) -> int:
    path.write_text(json.dumps(obj, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    return path.stat().st_size


def coverage_geojson(bbox: list[float]) -> dict:
    w, s, e, n = bbox
    ring = [[w, s], [e, s], [e, n], [w, n], [w, s]]
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [ring]}}]}


# ---------------------------------------------------------------- EFAS

def downsample_max(arr: np.ndarray, factor: int) -> np.ndarray:
    """Block maximum; edge blocks are padded with 0 (no flooding), which never wins."""
    if factor == 1:
        return arr
    h, w = arr.shape
    ph, pw = -h % factor, -w % factor
    if ph or pw:
        arr = np.pad(arr, ((0, ph), (0, pw)), constant_values=0)
    h2, w2 = arr.shape
    return arr.reshape(h2 // factor, factor, w2 // factor, factor).max(axis=(1, 3))


def mask_nodata(arr: np.ndarray) -> np.ndarray:
    """nodata (-9999), NaN and non-positive values -> 0 BEFORE downsampling."""
    a = np.nan_to_num(arr.astype(np.float32), nan=0.0)
    a[a <= 0] = 0.0
    return a


def classify_depth(depth: np.ndarray) -> np.ndarray:
    """Depth (m) -> RGBA uint8. 0 / nodata fully transparent; four classes above 0."""
    rgba = np.zeros(depth.shape + (4,), dtype=np.uint8)
    lower = 0.0
    for upper, colour in EFAS_COLOURS:
        m = (depth > lower) & (depth <= upper)
        rgba[m] = colour
        lower = upper
    return rgba


def to_web_mercator_rows(arr: np.ndarray, top: float, bottom: float) -> np.ndarray:
    """Resample rows from equal-latitude to equal-Web-Mercator-y spacing (nearest row).

    MapLibre stretches an image source linearly in Web Mercator between the corner
    coordinates, so an EPSG:4326 raster (rows linear in latitude) must be re-spaced or it
    is displaced by km across Croatia. Output height is ceil(1.1 x input) (the real ratio
    is ~1.08 over lat 42.3-46.6), so no source row is skipped.
    """
    h = arr.shape[0]
    new_h = int(np.ceil(h * 1.1))
    merc = lambda lat: np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    y = merc(top) + (np.arange(new_h) + 0.5) / new_h * (merc(bottom) - merc(top))
    lat = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
    rows = np.clip(((top - lat) / (top - bottom) * h).astype(int), 0, h - 1)
    return arr[rows]


def efas_factor(width: int, height: int) -> int:
    return max(1, -(-max(width, height) // MAX_TEX))


def corners(bounds) -> list[list[float]]:
    """MapLibre image-source order (image rows are re-spaced to Web Mercator, see to_web_mercator_rows): TL, TR, BR, BL as [lon, lat]."""
    return [[bounds.left, bounds.top], [bounds.right, bounds.top],
            [bounds.right, bounds.bottom], [bounds.left, bounds.bottom]]


def build_efas(efas_dir: Path, out: Path) -> dict:
    import rasterio
    ref = None
    sizes = {}
    for rp in (10, 100, 500):
        with rasterio.open(efas_dir / f"rp{rp}.tif") as src:
            assert src.crs is not None and src.crs.to_epsg() == 4326, f"rp{rp}: CRS {src.crs}"
            assert src.nodata == NODATA, f"rp{rp}: nodata {src.nodata}"
            c = corners(src.bounds)
            assert ref is None or c == ref, "EFAS rasters have different bounds"
            ref = c
            data = mask_nodata(src.read(1))
            f = efas_factor(src.width, src.height)
            src_top, src_bottom = src.bounds.top, src.bounds.bottom
        small = to_web_mercator_rows(downsample_max(data, f), src_top, src_bottom)
        assert max(small.shape) <= MAX_TEX
        png = out / f"efas_rp{rp}.png"
        Image.fromarray(classify_depth(small), "RGBA").save(png, optimize=False, compress_level=9)
        sizes[png.name] = (png.stat().st_size, small.shape[::-1], f)
    dump(ref, out / "efas_bounds.json")
    return sizes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default="data", help="data directory (default: data)")
    args = ap.parse_args()
    data = Path(args.data)
    if not data.is_absolute():
        data = ROOT / data
    out = data / "map"
    out.mkdir(parents=True, exist_ok=True)
    bbox = banovina_bbox()
    t0 = time.time()

    for name, tol in SIMPLIFY_TOL.items():
        t = time.time()
        src = json.loads((data / "geohazards" / f"{name}.geojson").read_text(encoding="utf-8"))
        keep = () if name == "unfavourable" else ("podloznost",)
        fc = process_geojson(src, tol, keep)
        assert_inside(fc, bbox)
        size = dump(fc, out / f"geohazard_{name}.geojson")
        print(f"geohazard_{name}.geojson: {size/1e6:.2f} MB, tol {tol} deg, {len(fc['features'])} features, {time.time()-t:.0f} s")
        if size > MAX_GEOJSON_BYTES:
            print(f"ERROR: {name} exceeds {MAX_GEOJSON_BYTES} bytes; stop and report to @architect", file=sys.stderr)
            return 1

    dump(coverage_geojson(bbox), out / "banovina_coverage.geojson")
    for name, (size, wh, f) in build_efas(data / "efas", out).items():
        print(f"{name}: {size/1e6:.2f} MB, {wh[0]}x{wh[1]} px, factor {f}")
    total = sum(p.stat().st_size for p in out.iterdir())
    print(f"total data/map: {total/1e6:.2f} MB, runtime {time.time()-t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
