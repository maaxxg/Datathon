"""Point lookups in MPGI geohazard polygons (Banovina), loaded once from GeoJSON."""
from __future__ import annotations

import json
from pathlib import Path

from shapely import STRtree
from shapely.geometry import Point, shape

BANOVINA_BBOX = (15.7298, 44.9575, 16.9236, 45.6799)  # WFS WGS84BoundingBox, 30.10.2026.
SUSCEPTIBILITY_LAYERS = ("landslide", "liquefaction", "sinkhole")


def in_banovina(lat: float, lon: float) -> bool:
    w, s, e, n = BANOVINA_BBOX
    return w <= lon <= e and s <= lat <= n


class Layer:
    def __init__(self, features: list[dict]):
        self.geoms = [shape(f["geometry"]) for f in features if f.get("geometry")]
        self.props = [f.get("properties") or {} for f in features if f.get("geometry")]
        self.tree = STRtree(self.geoms)

    def hits(self, lat: float, lon: float) -> list[dict]:
        p = Point(lon, lat)
        return [self.props[i] for i in self.tree.query(p, predicate="intersects")]


class Geohazards:
    def __init__(self, directory: Path):
        self.layers: dict[str, Layer] = {}
        for path in sorted(directory.glob("*.geojson")):
            fc = json.loads(path.read_text())
            self.layers[path.stem] = Layer(fc.get("features", []))

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
