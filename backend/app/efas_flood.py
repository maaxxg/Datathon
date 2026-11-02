"""Read EFAS river flood depth (m) for return periods 10, 100, 500 years from clipped Croatia GeoTIFFs."""
from __future__ import annotations

import math
from pathlib import Path

import rasterio

RETURN_PERIODS = (10, 100, 500)


class EFASFloodReader:
    def __init__(self, directory: Path):
        self.directory = directory
        self._datasets: dict[int, rasterio.DatasetReader] = {}
        for rp in RETURN_PERIODS:
            p = directory / f"rp{rp}.tif"
            if p.is_file():
                self._datasets[rp] = rasterio.open(p)

    def available(self) -> bool:
        return len(self._datasets) == len(RETURN_PERIODS)

    def depths(self, lat: float, lon: float) -> dict[int, float | None] | None:
        """Return {10: depth_m, 100: depth_m, 500: depth_m} at (lat, lon), or None if EFAS rasters are not loaded."""
        if not self._datasets:
            return None
        out: dict[int, float | None] = {}
        for rp in RETURN_PERIODS:
            ds = self._datasets.get(rp)
            if ds is None:
                out[rp] = None
                continue
            left, bottom, right, top = ds.bounds
            if not (left <= lon <= right and bottom <= lat <= top):
                out[rp] = None
                continue
            row, col = ds.index(lon, lat)
            if not (0 <= row < ds.height and 0 <= col < ds.width):
                out[rp] = None
                continue
            val = float(ds.read(1, window=((row, row + 1), (col, col + 1)))[0, 0])
            nodata = ds.nodata
            if math.isnan(val) or (nodata is not None and math.isclose(val, float(nodata))) or val <= 0.0:
                out[rp] = 0.0
            else:
                out[rp] = round(val, 2)
        return out

    def close(self) -> None:
        for ds in self._datasets.values():
            ds.close()
        self._datasets.clear()
