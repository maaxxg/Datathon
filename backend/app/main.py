"""Geo-rizik API (vertical prototype: HV floods + Banovina geohazards + ESHM20 seismic)."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query

from .geohazards import SUSCEPTIBILITY_LAYERS, Geohazards, in_banovina
from .hv_flood import HVFloodClient
from .risk_rules import (
    HazardResult, flood_hv_level, most_significant, seismic_level,
    susceptibility_level, unfavourable_level,
)
from .seismic import SeismicReader

DATA_DIR = Path(os.environ.get("GEORIZIK_DATA", Path(__file__).resolve().parents[2] / "data"))
CATALOGUE = yaml.safe_load((Path(__file__).parent / "layers.yaml").read_text(encoding="utf-8"))
CROATIA = CATALOGUE["coverages"]["croatia"]
DISCLAIMER = ("Informativni prikaz iz javnih podataka. Nije stručno mišljenje ni službena potvrda; "
              "za odluke se obratite nadležnim institucijama i ovlaštenim stručnjacima.")

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["hv"] = HVFloodClient()
    state["geo"] = Geohazards(DATA_DIR / "geohazards")
    state["seismic"] = SeismicReader(DATA_DIR / "seismic" / "eshm20_pga475.json")
    yield
    await state["hv"].aclose()


app = FastAPI(title="Geo-rizik API", version="0.1.0", lifespan=lifespan)


def serialise(r: HazardResult) -> dict:
    d = asdict(r)
    d["level"] = r.level.value
    layer = CATALOGUE["layers"].get(r.source, {})
    d["source"] = {k: layer.get(k) for k in ("title", "publisher", "licence", "url", "year", "resolution")}
    return d


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "geohazards_loaded": state["geo"].available(),
        "seismic_loaded": state["seismic"].available(),
    }


@app.get("/api/sources")
async def sources() -> dict:
    return CATALOGUE


@app.get("/api/report")
async def report(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)) -> dict:
    w, s, e, n = CROATIA
    if not (w <= lon <= e and s <= lat <= n):
        raise HTTPException(422, "Lokacija je izvan Hrvatske.")

    results: list[HazardResult] = [flood_hv_level(await state["hv"].classify(lat, lon))]

    geo: Geohazards = state["geo"]
    covered = in_banovina(lat, lon) and geo.available()
    for layer in SUSCEPTIBILITY_LAYERS:
        value = geo.susceptibility(layer, lat, lon) if covered else None
        results.append(susceptibility_level(layer, value, covered))
    results.append(unfavourable_level(geo.inside("unfavourable", lat, lon), covered))

    seismic: SeismicReader = state["seismic"]
    results.append(seismic_level(seismic.pga_g(lat, lon)))

    top = most_significant(results)
    return {
        "location": {"lat": lat, "lon": lon},
        "most_significant": serialise(top) if top else None,
        "hazards": [serialise(r) for r in results],
        "disclaimer": DISCLAIMER,
    }
