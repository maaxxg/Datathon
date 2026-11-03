"""Flood depth class at a point from Hrvatske vode WMS (2019 hazard maps).

The hazard layers are rasters that GeoServer marks as not queryable
(GetFeatureInfo -> LayerNotQueryable), and vector data is available only on
request. We therefore render a small fixed tile with GetMap and read the pixel
under the point. The layer uses an exact 5-value colour map (GetLegendGraphic,
checked 30.10.2026), so the colour decodes deterministically to a depth class.

Privacy: tiles are snapped to a fixed 0.01 deg grid and cached per tile, so the
cache never stores the user's exact coordinates.
"""
from __future__ import annotations

import asyncio
import io
import math
from collections import OrderedDict

import httpx
from PIL import Image

WMS_URL = "https://servisi.voda.hr/wms"
LAYERS = {
    s: f"poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-{s}-vjerojatnost_2019"
    for s in ("velika", "srednja", "mala")
}
LEGEND = {
    (0xBE, 0xE8, 0xFF): "d_lt_0_5",
    (0x73, 0xDF, 0xFF): "d_0_5_1_5",
    (0x73, 0xB2, 0xFF): "d_1_5_2_5",
    (0x7A, 0x8E, 0xF5): "d_gt_2_5",
    (0x00, 0x4D, 0xA8): "permanent_water",
}
TILE_DEG = 0.02        # ~2.2 km; WMS layer only renders within ~1:15k..1:100k scale range
TILE_PX = 256          # ~8.5 m per pixel (scale ~1:31,000 in OGC WMS 1.3.0)
MAX_COLOUR_DIST = 24   # tolerance for resampling at tile edges


def tile_origin(lat: float, lon: float) -> tuple[float, float]:
    return (math.floor(lat / TILE_DEG) * TILE_DEG, math.floor(lon / TILE_DEG) * TILE_DEG)


def pixel_in_tile(lat: float, lon: float, south: float, west: float) -> tuple[int, int]:
    x = int((lon - west) / TILE_DEG * TILE_PX)
    y = int((south + TILE_DEG - lat) / TILE_DEG * TILE_PX)
    return min(max(x, 0), TILE_PX - 1), min(max(y, 0), TILE_PX - 1)


def decode_rgba(rgba: tuple[int, int, int, int]) -> str:
    r, g, b, a = rgba
    if a < 200:
        return "outside"
    best, dist = None, 1e9
    for (lr, lg, lb), cls in LEGEND.items():
        d = math.dist((r, g, b), (lr, lg, lb))
        if d < dist:
            best, dist = cls, d
    return best if dist <= MAX_COLOUR_DIST else "outside"


class HVFloodClient:
    def __init__(self, client: httpx.AsyncClient | None = None, cache_size: int = 512):
        self._client = client or httpx.AsyncClient(timeout=20)
        self._cache: OrderedDict[tuple, Image.Image] = OrderedDict()
        self._cache_size = cache_size

    async def _tile(self, scenario: str, south: float, west: float) -> Image.Image:
        key = (scenario, round(south, 4), round(west, 4))
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        r = await self._client.get(WMS_URL, params={
            "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
            "LAYERS": LAYERS[scenario], "STYLES": "", "CRS": "EPSG:4326",
            # WMS 1.3.0 + EPSG:4326 uses lat,lon axis order
            "BBOX": f"{south},{west},{south + TILE_DEG},{west + TILE_DEG}",
            "WIDTH": TILE_PX, "HEIGHT": TILE_PX, "FORMAT": "image/png", "TRANSPARENT": "true",
        })
        r.raise_for_status()
        if not r.headers.get("content-type", "").startswith("image/"):
            raise RuntimeError(f"WMS returned {r.headers.get('content-type')}: {r.text[:200]}")
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        self._cache[key] = img
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return img

    async def classify(self, lat: float, lon: float) -> dict[str, str | None]:
        """scenario -> depth class / 'outside'; None if the service failed for that scenario."""
        south, west = tile_origin(lat, lon)
        x, y = pixel_in_tile(lat, lon, south, west)

        async def one(scenario: str) -> str | None:
            try:
                img = await self._tile(scenario, south, west)
            except (httpx.HTTPError, RuntimeError, OSError):
                return None
            return decode_rgba(img.getpixel((x, y)))

        results = await asyncio.gather(*(one(s) for s in LAYERS))
        return dict(zip(LAYERS, results))

    async def aclose(self) -> None:
        await self._client.aclose()
