"""Validate all MUST layers on 10 known reference points across Croatia (PLAN 2. 11. - D).

Usage:
    python scripts/validate_known_points.py                 # local mode (rule functions + local data)
    python scripts/validate_known_points.py --api https://localhost --insecure   # API mode (/api/report)

--insecure skips TLS verification (Caddy internal CA); off by default.

Queries:
- Hrvatske vode WMS (2019 flood hazard maps: velika, srednja, mala)
- Clipped JRC EFAS v3.1.1 rasters (data/efas/rp{10,100,500}.tif)
- ESHM20 Croatia PGA 475-yr grid (data/seismic/eshm20_pga475.json)
- MPGI Banovina geohazards (data/geohazards/*.geojson)
- DGU Adrese INSPIRE index (data/addresses.sqlite)
"""
from __future__ import annotations

import asyncio
import json
import math
import sqlite3
import sys
from pathlib import Path

import rasterio
from shapely import STRtree
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.geohazards import SUSCEPTIBILITY_LAYERS, Geohazards, in_banovina  # noqa: E402
from app.hv_flood import HVFloodClient  # noqa: E402
from app.risk_rules import (  # noqa: E402
    combine_flood, flood_efas_level, flood_hv_level, most_significant,
    seismic_level, susceptibility_level, unfavourable_level,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

KNOWN_POINTS = [
    {"id": "p01_petrinja_centar", "name": "Petrinja — središte", "query": "Matije Gupca 12 Petrinja", "lat": 45.4375, "lon": 16.2739},
    {"id": "p02_petrinja_gupca_12", "name": "Petrinja — Matije Gupca 12", "query": "Matije Gupca 12 Petrinja", "lat": 45.441024, "lon": 16.271776},
    {"id": "p03_sisak_rimska_19", "name": "Sisak — Rimska ulica 19", "query": "Rimska ulica 19 Sisak", "lat": 45.489569, "lon": 16.371289},
    {"id": "p04_glina_centar", "name": "Glina — središte", "query": "Kralja Tomislava Glina", "lat": 45.3381, "lon": 16.0886},
    {"id": "p05_hrvatska_kostajnica", "name": "Hrvatska Kostajnica (uz Unu)", "query": "Hrvatska Kostajnica", "lat": 45.2292, "lon": 16.5392},
    {"id": "p06_karlovac_kupa", "name": "Karlovac (uz Kupu)", "query": "Karlovac", "lat": 45.4870, "lon": 15.5480},
    {"id": "p07_gunja_sava", "name": "Gunja (županjska Posavina)", "query": "Gunja", "lat": 44.8810, "lon": 18.8450},
    {"id": "p08_zagreb_sava", "name": "Zagreb — priobalje Save", "query": "Savska cesta Zagreb", "lat": 45.7930, "lon": 15.9600},
    {"id": "p09_split_centar", "name": "Split — središte", "query": "Split", "lat": 43.5081, "lon": 16.4402},
    {"id": "p10_osijek_centar", "name": "Osijek — središte", "query": "Osijek", "lat": 45.5550, "lon": 18.6955},
]


def sample_efas(lat: float, lon: float) -> dict[int, float]:
    out = {}
    for rp in (10, 100, 500):
        p = DATA_DIR / "efas" / f"rp{rp}.tif"
        if not p.is_file():
            out[rp] = 0.0
            continue
        with rasterio.open(p) as ds:
            r, c = ds.index(lon, lat)
            val = float(ds.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
            out[rp] = round(val, 2) if not math.isnan(val) and val > 0 else 0.0
    return out


def load_eshm20():
    p = DATA_DIR / "seismic" / "eshm20_pga475.json"
    if not p.is_file():
        return [], None
    pts = [(float(x["lat"]), float(x["lon"]), float(x["ag_g"])) for x in json.loads(p.read_text(encoding="utf-8"))["points"]]
    tree = STRtree([Point(lon, lat) for lat, lon, _ in pts])
    return pts, tree


def sample_eshm20(pts, tree, lat: float, lon: float) -> float | None:
    if not pts or tree is None:
        return None
    cands = tree.query(Point(lon, lat).buffer(0.25))
    best, best_d = None, 1e9
    for idx in cands:
        plat, plon, val = pts[int(idx)]
        d = math.hypot(lat - plat, (lon - plon) * math.cos(math.radians(lat)))
        if d < best_d:
            best, best_d = val, d
    return round(best, 4) if best is not None else None


async def run_all():
    sys.stdout.reconfigure(encoding="utf-8")
    hv = HVFloodClient()
    geo = Geohazards(DATA_DIR / "geohazards")
    eshm_pts, eshm_tree = load_eshm20()

    results_out = []
    for pt in KNOWN_POINTS:
        lat, lon = pt["lat"], pt["lon"]
        hv_classes = await hv.classify(lat, lon)
        efas_depths = sample_efas(lat, lon)
        ag_g = sample_eshm20(eshm_pts, eshm_tree, lat, lon)
        ban = in_banovina(lat, lon) and geo.available()

        hv_res = flood_hv_level(hv_classes)
        efas_res = flood_efas_level(efas_depths)
        flood_res = combine_flood(hv_res, efas_res)
        seis_res = seismic_level(ag_g)

        susc = {lyr: (geo.susceptibility(lyr, lat, lon) if ban else None) for lyr in SUSCEPTIBILITY_LAYERS}
        unfav = geo.inside("unfavourable", lat, lon) if ban else False

        hazards = [
            flood_res,
            seis_res,
            *(susceptibility_level(lyr, susc[lyr], ban) for lyr in SUSCEPTIBILITY_LAYERS),
            unfavourable_level(unfav, ban),
        ]
        top = most_significant(hazards)
        results_out.append({
            "id": pt["id"],
            "name": pt["name"],
            "lat": lat,
            "lon": lon,
            "in_banovina": ban,
            "hv_classes": hv_classes,
            "efas_depths_m": efas_depths,
            "flood_level": flood_res.level.value,
            "flood_source": flood_res.source,
            "eshm20_ag_g": ag_g,
            "seismic_level": seis_res.level.value,
            "geohazards": {**susc, "unfavourable": unfav if ban else None},
            "most_significant": {"hazard": top.hazard, "level": top.level.value} if top else None,
        })

    await hv.aclose()
    print(json.dumps(results_out, ensure_ascii=False, indent=2))


def run_api(base: str, insecure: bool) -> None:
    """Call GET {base}/api/report for every known point and print a compact JSON list."""
    import httpx

    sys.stdout.reconfigure(encoding="utf-8")
    if insecure:
        print("WARNING: --insecure, TLS verification is disabled.", file=sys.stderr)
    out = []
    with httpx.Client(verify=not insecure, timeout=30.0) as client:
        for pt in KNOWN_POINTS:
            entry = {"id": pt["id"], "name": pt["name"], "lat": pt["lat"], "lon": pt["lon"]}
            try:
                r = client.get(f"{base.rstrip('/')}/api/report", params={"lat": pt["lat"], "lon": pt["lon"]})
                if r.status_code != 200:
                    entry["error"] = f"HTTP {r.status_code}"
                else:
                    d = r.json()
                    ms = d.get("most_significant")
                    entry["hazards"] = [
                        {
                            "hazard": h["hazard"],
                            "level": h["level"],
                            "source": (h.get("source") or {}).get("title"),
                            "detail": h.get("detail"),
                            "notes": h.get("notes"),
                        }
                        for h in d.get("hazards", [])
                    ]
                    entry["most_significant"] = {"hazard": ms["hazard"], "level": ms["level"]} if ms else None
                    entry["all_no_data"] = d.get("all_no_data")
            except Exception as e:  # noqa: BLE001 - record and continue
                entry = {k: entry[k] for k in ("id", "name", "lat", "lon")}
                entry["error"] = type(e).__name__
            out.append(entry)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if any("error" in e for e in out):
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--api", metavar="BASE_URL", help="query a running API instead of local rule functions")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (API mode only)")
    args = ap.parse_args()
    if args.api:
        run_api(args.api, args.insecure)
    else:
        asyncio.run(run_all())
