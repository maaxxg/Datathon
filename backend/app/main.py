"""Geo-rizik API (vertical prototype: HV floods + EFAS fallback + Banovina geohazards + ESHM20 seismic + address geocoder)."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query

from .efas_flood import EFASFloodReader
from .geocoder import AddressGeocoder
from .geohazards import SUSCEPTIBILITY_LAYERS, Geohazards, in_banovina
from .hv_flood import HVFloodClient
from .risk_rules import (
    HazardResult, combine_flood, flood_efas_level, flood_hv_level, groundwater_level,
    most_significant, seismic_level, susceptibility_level, unfavourable_level,
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
    state["efas"] = EFASFloodReader(DATA_DIR / "efas")
    state["geo"] = Geohazards(DATA_DIR / "geohazards")
    state["seismic"] = SeismicReader(DATA_DIR / "seismic" / "eshm20_pga475.json")
    state["geocoder"] = AddressGeocoder(DATA_DIR / "addresses.sqlite")
    yield
    state["efas"].close()
    state["geocoder"].close()
    await state["hv"].aclose()


app = FastAPI(title="Geo-rizik API", version="0.1.0", lifespan=lifespan)


def serialise(r: HazardResult) -> dict:
    d = asdict(r)
    d["level"] = r.level.value
    layer = CATALOGUE["layers"].get(r.source, {})
    d["source"] = {k: layer.get(k) for k in ("title", "publisher", "licence", "url", "year", "resolution", "note")}
    return d


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "geohazards_loaded": state["geo"].available(),
        "addresses_loaded": state["geocoder"].available(),
        "seismic_loaded": state["seismic"].available(),
        "efas_loaded": state["efas"].available(),
    }


@app.get("/api/sources")
async def sources() -> dict:
    return CATALOGUE


@app.get("/api/addresses")
def addresses(q: str = Query("", min_length=0, max_length=120), limit: int = Query(10, ge=1, le=50)) -> dict:
    geocoder: AddressGeocoder = state["geocoder"]
    return {
        "available": geocoder.available(),
        "results": geocoder.search(q, limit=limit) if len(q.strip()) >= 2 else [],
    }


@app.get("/api/report")
async def report(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)) -> dict:
    w, s, e, n = CROATIA
    if not (w <= lon <= e and s <= lat <= n):
        raise HTTPException(422, "Lokacija je izvan Hrvatske.")

    hv_res = flood_hv_level(await state["hv"].classify(lat, lon))
    efas: EFASFloodReader = state["efas"]
    efas_depths = efas.depths(lat, lon) if efas.available() else None
    efas_res = flood_efas_level(efas_depths) if efas_depths is not None else None
    results: list[HazardResult] = [combine_flood(hv_res, efas_res)]

    geo: Geohazards = state["geo"]
    covered = in_banovina(lat, lon) and geo.available()
    for layer in SUSCEPTIBILITY_LAYERS:
        value = geo.susceptibility(layer, lat, lon) if covered else None
        results.append(susceptibility_level(layer, value, covered))
    results.append(unfavourable_level(geo.inside("unfavourable", lat, lon) if covered else False, covered))
    results.append(groundwater_level(geo.nearest_groundwater(lat, lon) if covered else None, covered))

    seismic: SeismicReader = state["seismic"]
    hit = seismic.pga_g(lat, lon)
    results.append(seismic_level(*hit) if hit else seismic_level(None))

    top = most_significant(results)
    return {
        "location": {"lat": lat, "lon": lon},
        "most_significant": serialise(top) if top else None,
        "hazards": [serialise(r) for r in results],
        "disclaimer": DISCLAIMER,
    }
