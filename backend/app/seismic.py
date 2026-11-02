"""ESHM20 peak ground acceleration (PGA, 475-yr return period, in g) lookup for Croatia."""
from __future__ import annotations

import json
import math
from pathlib import Path

from shapely import STRtree
from shapely.geometry import Point


def _dist_deg_scaled(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = lat2 - lat1
    dx = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) * 0.5))
    return math.hypot(dx, dy)


class SeismicReader:
    """Nearest-grid-point lookup on the pre-fetched ESHM20 Croatia grid (~0.1 deg spacing)."""

    def __init__(self, path: Path, max_deg: float = 0.25):
        self.path = path
        self.max_deg = max_deg
        self.points: list[tuple[float, float, float]] = []
        self._tree: STRtree | None = None
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            pts = raw.get("points", [])
            self.points = [(float(p["lat"]), float(p["lon"]), float(p["ag_g"])) for p in pts]
            if self.points:
                self._tree = STRtree([Point(lon, lat) for lat, lon, _ in self.points])

    def available(self) -> bool:
        return bool(self.points)

    def pga_g(self, lat: float, lon: float) -> float | None:
        """Return reference PGA (g, 475-yr) at the nearest ESHM20 grid point within max_deg."""
        if not self.points or self._tree is None:
            return None
        candidates = self._tree.query(Point(lon, lat).buffer(self.max_deg))
        best_val: float | None = None
        best_dist = float("inf")
        for idx in candidates:
            plat, plon, val = self.points[int(idx)]
            d = _dist_deg_scaled(lat, lon, plat, plon)
            if d <= self.max_deg and d < best_dist:
                best_dist = d
                best_val = val
        return best_val
