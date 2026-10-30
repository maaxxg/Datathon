"""Download MPGI geohazard layers (Banovina) as GeoJSON in WGS84.

Usage: python pipeline/fetch_geohazards.py [--out data/geohazards]

The service runs on several mirror hosts; gis1 returned HTTP 502 on 30.10.2026,
so hosts are tried in order until one answers.
"""
from __future__ import annotations

import argparse
import json
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
            fc = fetch_layer(client, type_name)
            path = out / f"{key}.geojson"
            path.write_text(json.dumps(fc, ensure_ascii=False))
            attrs = sorted({k for f in fc["features"] for k in (f.get("properties") or {})})
            print(f"{key}: {len(fc['features'])} features, attrs={attrs}, "
                  f"{time.perf_counter() - t0:.1f}s -> {path}")


if __name__ == "__main__":
    main()
