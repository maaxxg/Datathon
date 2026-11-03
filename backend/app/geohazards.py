"""Point lookups in MPGI geohazard polygons and point measurements (Banovina), loaded once from GeoJSON."""
from __future__ import annotations

import json
import re
import math
from pathlib import Path

from shapely import STRtree
from shapely.geometry import Point, shape

BANOVINA_BBOX = (15.7298, 44.9575, 16.9236, 45.6799)  # WFS WGS84BoundingBox, 30.10.2026.
SUSCEPTIBILITY_LAYERS = ("landslide", "liquefaction", "sinkhole")


def in_banovina(lat: float, lon: float) -> bool:
    w, s, e, n = BANOVINA_BBOX
    return w <= lon <= e and s <= lat <= n


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat2 - lat1) * 111_132.0
    dx = (lon2 - lon1) * 111_320.0 * math.cos(math.radians((lat1 + lat2) * 0.5))
    return math.hypot(dx, dy)


def valid_point_feature(f: dict) -> bool:
    """Drop placeholder points (source has 5 at [16.5, -90]); other geometries pass through."""
    g = f.get("geometry")
    if not g or g.get("type") != "Point":
        return True
    lon, lat = g["coordinates"][:2]
    return -180 <= lon <= 180 and -90 < lat < 90


_DATE_RE = re.compile(r"\d{1,2}\.\d{1,2}\.\d{4}")


def has_measurement_date(f: dict) -> bool:
    """Groundwater wells without a parseable datum_mjerenja are treated as 'no measurement'."""
    return bool(_DATE_RE.search(str((f.get("properties") or {}).get("datum_mjerenja") or "")))


class Layer:
    def __init__(self, features: list[dict]):
        self.geoms = [shape(f["geometry"]) for f in features if f.get("geometry")]
        self.props = [f.get("properties") or {} for f in features if f.get("geometry")]
        self.tree = STRtree(self.geoms)

    def hits(self, lat: float, lon: float) -> list[dict]:
        p = Point(lon, lat)
        return [self.props[i] for i in self.tree.query(p, predicate="intersects")]

    def nearest_within(self, lat: float, lon: float, max_dist_m: float) -> tuple[dict, float] | None:
        if not self.geoms:
            return None
        # Pre-filter with a generous degree buffer (~70 km per degree of longitude at 45 deg N)
        deg_buf = max_dist_m / 70_000.0
        candidates = self.tree.query(Point(lon, lat).buffer(deg_buf))
        best_prop: dict | None = None
        best_dist = float("inf")
        for idx in candidates:
            geom = self.geoms[idx]
            pt = geom if geom.geom_type == "Point" else geom.centroid
            d = _distance_m(lat, lon, pt.y, pt.x)
            if d <= max_dist_m and d < best_dist:
                best_dist = d
                best_prop = self.props[idx]
        if best_prop is None:
            return None
        return best_prop, best_dist


class Geohazards:
    def __init__(self, directory: Path):
        self.layers: dict[str, Layer] = {}
        for path in sorted(directory.glob("*.geojson")):
            fc = json.loads(path.read_text(encoding="utf-8"))
            self.layers[path.stem] = Layer([f for f in fc.get("features", [])
                                       if valid_point_feature(f)
                                       and (path.stem != "groundwater" or has_measurement_date(f))])

    def available(self) -> bool:
        return bool(self.layers)

    def susceptibility(self, layer: str, lat: float, lon: float) -> str | None:
        """Highest susceptibility class among polygons containing the point (polygons should not overlap)."""
        if layer not in self.layers:
            return None
        order = {"niska": 1, "srednja": 2, "visoka": 3}
        values = [h.get("podloznost") for h in self.layers[layer].hits(lat, lon) if h.get("podloznost")]
        return max(values, key=lambda v: order.get(v.lower(), 0)) if values else None

    def inside(self, layer: str, lat: float, lon: float) -> bool:
        return layer in self.layers and bool(self.layers[layer].hits(lat, lon))

    def nearest_groundwater(self, lat: float, lon: float, max_dist_m: float = 1000.0) -> dict | None:
        """Nearest groundwater measurement point within max_dist_m meters."""
        if "groundwater" not in self.layers:
            return None
        res = self.layers["groundwater"].nearest_within(lat, lon, max_dist_m)
        if res is None:
            return None
        props, dist_m = res
        if props.get("dubina_do") is None:
            return None
        return {
            "dubina_do": float(props["dubina_do"]),
            "datum_mjerenja": props.get("datum_mjerenja"),
            "udaljenost_m": round(dist_m),
        }
