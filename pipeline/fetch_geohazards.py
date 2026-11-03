"""Download MPGI geohazard layers (Banovina) as GeoJSON in WGS84.

Usage: python pipeline/fetch_geohazards.py [--out data/geohazards]

The service runs on several mirror hosts; gis1 returned HTTP 502 on 30.10.2026,
so hosts are tried in order until one answers.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

HOSTS = [f"https://gis{i}.mgipu.hr/srv1/RGN_MGIPU_Public/wfs" for i in (2, 3, 4, 1)]
LAYERS = {
    "landslide": "RGN_kliziste_podloznost",
    "liquefaction": "RGN_likvefakcija_podloznost",
    "sinkhole": "RGN_vrtaca_podloznost",
    "unfavourable": "RGN_nepovoljno_za_gradnju",
    "groundwater": "RGN_podzemna_voda_dubina",
    "landslide_inventory": "RGN_kliziste_inventar",
    "liquefaction_inventory": "RGN_likvefakcija_inventar",
    "sinkhole_inventory": "RGN_vrtaca_inventar",
}


def fetch_layer(client: httpx.Client, type_name: str) -> dict:
    last_error: Exception | None = None
    for host in HOSTS:
        try:
            r = client.get(host, params={
                "service": "WFS", "version": "2.0.0", "request": "GetFeature",
                "typeNames": f"RGN_MGIPU_Public:{type_name}",
                "outputFormat": "application/json", "srsName": "EPSG:4326",
            })
            r.raise_for_status()
            fc = r.json()
            fc["_source_host"] = host
            return fc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            last_error = exc
            print(f"  {host}: {exc}", file=sys.stderr)
    raise RuntimeError(f"all hosts failed for {type_name}: {last_error}")


def drop_placeholder_points(fc: dict) -> dict:
    """The groundwater layer has 5 placeholder Points at lat -90; drop invalid lon/lat."""
    def ok(f: dict) -> bool:
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            return True
        lon, lat = g["coordinates"][:2]
        return -180 <= lon <= 180 and -90 < lat < 90
    fc["features"] = [f for f in fc["features"] if ok(f)]
    if fc.get("features") and any("datum_mjerenja" in (f.get("properties") or {}) for f in fc["features"]):
        # groundwater: wells without a parseable measurement date count as "no measurement"
        fc["features"] = [f for f in fc["features"]
                          if re.search(r"\d{1,2}\.\d{1,2}\.\d{4}", str((f.get("properties") or {}).get("datum_mjerenja") or ""))]
    return fc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/geohazards")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # Large polygons can take ~25 s per request.
    with httpx.Client(timeout=180, follow_redirects=True) as client:
        for key, type_name in LAYERS.items():
            t0 = time.perf_counter()
            fc = drop_placeholder_points(fetch_layer(client, type_name))
            path = out / f"{key}.geojson"
            part = path.with_name(path.name + ".part")  # atomic: never leave a truncated file
            part.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
            part.replace(path)
            attrs = sorted({k for f in fc["features"] for k in (f.get("properties") or {})})
            print(f"{key}: {len(fc['features'])} features, attrs={attrs}, "
                  f"{time.perf_counter() - t0:.1f}s -> {path}")


if __name__ == "__main__":
    main()
