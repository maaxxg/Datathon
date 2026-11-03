"""Clip JRC EFAS v3.1.1 river flood hazard maps (RP10, RP100, RP500) to Croatia as COGs.

Usage:
    python pipeline/fetch_efas.py [--out data/efas]

Uses GDAL /vsicurl/ via rasterio to fetch only the Croatia bounding box window
([13.2, 42.3, 19.65, 46.6] in EPSG:4326) over HTTP range requests instead of
downloading the full ~300 MB continental GeoTIFFs.
"""
from __future__ import annotations

import argparse
import datetime
import time
from pathlib import Path

import rasterio
from rasterio.windows import from_bounds

BASE_URL = "https://jeodpp.jrc.ec.europa.eu/ftp/public/JRC-OpenData/CEMS-EFAS/flood_hazard"
RETURN_PERIODS = (10, 100, 500)
CROATIA_BBOX = (13.2, 42.3, 19.65, 46.6)  # west, south, east, north (WGS84)


def clip_rp(rp: int, out_dir: Path) -> Path:
    url = f"/vsicurl/{BASE_URL}/Europe_RP{rp}_filled_depth.tif"
    out_path = out_dir / f"rp{rp}.tif"
    w, s, e, n = CROATIA_BBOX
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        with rasterio.open(url) as src:
            win = from_bounds(w, s, e, n, src.transform).round_offsets().round_lengths()
            data = src.read(1, window=win)
            transform = src.window_transform(win)
            profile = src.profile.copy()
            profile.update(
                driver="GTiff",
                height=int(win.height),
                width=int(win.width),
                transform=transform,
                compress="deflate",
                predictor=2,
                tiled=True,
                blockxsize=256,
                blockysize=256,
            )
            part = out_path.with_name(out_path.name + ".part")  # atomic: never leave a truncated file
            with rasterio.open(part, "w", **profile) as dst:
                dst.write(data, 1)
            part.replace(out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/efas"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"EFAS v3.1.1, clipped on {datetime.date.today().isoformat()}")
    for rp in RETURN_PERIODS:
        t0 = time.perf_counter()
        path = clip_rp(rp, args.out)
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"RP{rp}: {size_mb:.2f} MB in {time.perf_counter() - t0:.1f}s -> {path}")


if __name__ == "__main__":
    main()
