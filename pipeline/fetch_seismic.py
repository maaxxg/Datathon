"""Download ESHM20 PGA (475-year return period, arithmetic mean) grid for Croatia from EFEHR API.

Usage:
    python pipeline/fetch_seismic.py [--out data/seismic/eshm20_pga475.json]

Source:
    EFEHR Seismic Hazard Services (ETH Zürich), model_id=81 (ESHM20),
    IMT=PGA (g, rock Vs30=760 m/s), POE=0.002103 in 1 year (475-year return period = 10% in 50 years),
    aggregation_type=arithmetic (mean hazard).
    Licence: CC BY 4.0 (DOI: 10.12686/a15).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

API_URL = "https://efehr-services.ethz.ch/hazard/api/v1/maps/area"
CROATIA_BBOX = (13.2, 42.3, 19.65, 46.6)  # lon_min, lat_min, lon_max, lat_max
MODEL_ID = 81                             # European Seismic Hazard Model 2020 (ESHM20)
POE_475YR = 0.002103                      # 1 - (1 - 0.1)**(1/50), 1-year investigation timespan


def fetch_croatia_grid() -> dict:
    w, s, e, n = CROATIA_BBOX
    with httpx.Client(timeout=120) as client:
        r = client.get(API_URL, params={
            "lon_min": w, "lat_min": s, "lon_max": e, "lat_max": n,
            "modelid": MODEL_ID, "imt": "PGA", "poe": POE_475YR, "timespan": 1,
            "aggregationtype": "arithmetic",
        })
        r.raise_for_status()
        body = r.json()
    points = [
        {"lat": round(float(p["lat"]), 5), "lon": round(float(p["lon"]), 5), "ag_g": round(float(p["value"]), 5)}
        for p in body.get("points", [])
        if p.get("aggregation_type") == "arithmetic" and p.get("value") is not None
    ]
    return {
        "model_id": MODEL_ID,
        "model_name": "European Seismic Hazard Model 2020 (ESHM20)",
        "doi": "https://doi.org/10.12686/a15",
        "licence": "CC BY 4.0",
        "imt": "PGA",
        "unit": "g",
        "return_period_years": 475,
        "poe_1yr": POE_475YR,
        "aggregation_type": "arithmetic",
        "bbox": list(CROATIA_BBOX),
        "count": len(points),
        "points": points,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/seismic/eshm20_pga475.json"))
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    data = fetch_croatia_grid()
    args.out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"ESHM20 PGA475: {data['count']} grid points in {time.perf_counter() - t0:.1f}s -> {args.out}")


if __name__ == "__main__":
    main()
