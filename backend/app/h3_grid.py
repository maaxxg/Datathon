"""Multi-resolution Uber H3 hexagonal grid engine for regional queries (SPEC SHOULD #10, D7, D8, D14).

Uses the official Uber `h3` v4 library (`latlng_to_cell`, `grid_disk`, `cell_to_boundary`,
`cell_to_latlng`, `cell_to_parent`, `cell_to_children`, `cell_area`) to generate real H3
cells anchored to official DGU INSPIRE land addresses from `addresses.sqlite` (so coastal
cities like Split never place cells in the sea, with a `grid_disk` fallback for unit tests).

Evaluates hazard filters deterministically across a 4-level H3 resolution hierarchy
(`coarse` res 7 -> `medium` res 8 -> `base` res 9 -> `fine` res 10) so the MapLibre map
dynamically subdivides and merges hexagons as the user zooms in and out.
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import h3

from .geohazards import in_banovina
from .query_schema import REGION_COORDS, resolve_region_center
from .risk_rules import Level, groundwater_level, seismic_level, susceptibility_level, unfavourable_level

if TYPE_CHECKING:
    from .efas_flood import EFASFloodReader
    from .geocoder import AddressGeocoder
    from .geohazards import Geohazards
    from .seismic import SeismicReader

# Default H3 resolution for settlements (res 9 ~ 0.105 km^2 per cell, per DECISIONS.md D8).
SETTLEMENT_BASE_RES = 9
# Whole-region overview ("banovina") uses res 7 (~5.16 km^2) as base so the entire region fits cleanly.
REGION_OVERVIEW_BASE_RES = 7

LEVEL_RANK = {
    "nema_prema_karti": 0,
    "nisko": 1,
    "srednje": 2,
    "visoko": 3,
}

SEISMIC_RANK = {
    "vrlo_niska_seizmicnost": 0,
    "niska_seizmicnost": 1,
    "iznad_praga_niske_seizmicnosti": 2,
}

# Cache of settlement base H3 cells: (region_key, base_res) -> list[str]
_CELL_CACHE: dict[tuple[str, int], list[str]] = {}


def _h3_ring_coordinates(h3_cell: str) -> list[list[float]]:
    """Convert an H3 cell boundary ((lat, lng), ...) to a closed GeoJSON Polygon ring [[lon, lat], ...]."""
    boundary = h3.cell_to_boundary(h3_cell)
    ring = [[round(lng, 5), round(lat, 5)] for lat, lng in boundary]
    if ring:
        ring.append(ring[0])
    return ring


def _query_settlement_points(region: str, geocoder: AddressGeocoder | None) -> list[tuple[float, float]]:
    if geocoder is None or not geocoder.available() or geocoder._conn is None:
        return []
    norm = region.strip().lower()
    if norm in ("banovina", "sisačko-moslavačka", "sisacko-moslavacka"):
        return []

    tokens = [t for t in norm.replace("-", " ").split() if len(t) >= 2]
    if not tokens:
        return []
    fts_expr = " AND ".join(f'"{t}"*' for t in tokens)
    like_pat = f"%{norm}%"
    sql = """
        SELECT a.lat, a.lon
        FROM address_fts f
        JOIN address a ON a.id = f.rowid
        WHERE address_fts MATCH ?
          AND (lower(a.settlement) LIKE ? OR lower(a.municipality) LIKE ?)
        LIMIT 6000
    """
    try:
        rows = geocoder._conn.execute(sql, (fts_expr, like_pat, like_pat)).fetchall()
        return [(float(r["lat"]), float(r["lon"])) for r in rows]
    except Exception:
        return []


def settlement_h3_cells(
    region: str,
    geocoder: AddressGeocoder | None = None,
) -> tuple[int, list[str]]:
    """Return `(base_res, list_of_h3_indices)` for a region or settlement."""
    norm = (region or "banovina").strip().lower()
    center_info = resolve_region_center(norm) or REGION_COORDS["banovina"]
    lat0, lon0 = float(center_info["lat"]), float(center_info["lon"])

    if norm in ("banovina", "sisačko-moslavačka", "sisacko-moslavacka"):
        base_res = REGION_OVERVIEW_BASE_RES
        cache_key = (norm, base_res)
        if cache_key in _CELL_CACHE:
            return base_res, _CELL_CACHE[cache_key]
        center_cell = h3.latlng_to_cell(lat0, lon0, base_res)
        cells = sorted(h3.grid_disk(center_cell, 5))
        _CELL_CACHE[cache_key] = cells
        return base_res, cells

    base_res = SETTLEMENT_BASE_RES
    cache_key = (norm, base_res)
    if cache_key in _CELL_CACHE:
        return base_res, _CELL_CACHE[cache_key]

    pts = _query_settlement_points(norm, geocoder)
    if pts:
        seed_cells: set[str] = {h3.latlng_to_cell(lat, lon, base_res) for lat, lon in pts}
        # If a smaller town has sparse address cells, expand by 1 H3 ring to create a continuous mesh.
        if len(seed_cells) < 110:
            expanded: set[str] = set()
            for c in seed_cells:
                expanded.update(h3.grid_disk(c, 1))
            seed_cells = expanded

        cells = sorted(seed_cells)
        if len(cells) > 220:
            # Keep the 220 cells closest to the settlement center so multi-res children stay fast.
            cells.sort(
                key=lambda c: (h3.cell_to_latlng(c)[0] - lat0) ** 2 + (h3.cell_to_latlng(c)[1] - lon0) ** 2
            )
            cells = sorted(cells[:220])
        _CELL_CACHE[cache_key] = cells
        return base_res, cells

    # Fallback when addresses.sqlite is not loaded (e.g. unit tests)
    center_cell = h3.latlng_to_cell(lat0, lon0, base_res)
    fallback_cells = sorted(h3.grid_disk(center_cell, 7))
    return base_res, fallback_cells


def _eval_cell_flood_efas(lat: float, lon: float, efas: EFASFloodReader | None) -> str:
    """Evaluate regional flood level from local EFAS rasters (RP10, RP100, RP500)."""
    if efas is None or not efas.available():
        return Level.NONE.value
    depths = efas.depths(lat, lon)
    if not depths:
        return Level.NONE.value
    if (depths.get(10) or 0.0) > 0.0:
        return Level.HIGH.value
    if (depths.get(100) or 0.0) > 0.0:
        return Level.MEDIUM.value
    if (depths.get(500) or 0.0) > 0.0:
        return Level.LOW.value
    return Level.NONE.value


def _eval_cell_hazard(
    hazard: str,
    lat: float,
    lon: float,
    efas: EFASFloodReader | None,
    geo: Geohazards | None,
    seismic: SeismicReader | None,
) -> str:
    if hazard == "flood":
        return _eval_cell_flood_efas(lat, lon, efas)

    if hazard == "seismic":
        if seismic is None or not seismic.available():
            return Level.SEISMIC_LOW.value
        hit = seismic.pga_g(lat, lon)
        return seismic_level(*hit).level.value if hit else Level.SEISMIC_LOW.value

    covered = in_banovina(lat, lon)
    if not covered or geo is None or not geo.available():
        return Level.NO_DATA.value

    if hazard in ("landslide", "liquefaction", "sinkhole"):
        raw = geo.susceptibility(hazard, lat, lon)
        if raw is None:
            return Level.NONE.value
        return susceptibility_level(hazard, raw, True, True).level.value

    if hazard == "unfavourable":
        inside = geo.inside("unfavourable", lat, lon)
        return unfavourable_level(inside, True, True).level.value

    if hazard == "groundwater":
        gw = geo.nearest_groundwater(lat, lon)
        if gw is None:
            return Level.LOW.value
        return groundwater_level(gw, True, True).level.value

    return Level.NONE.value


def _passes_filter(cell_level: str, max_level: str, hazard: str) -> bool:
    if hazard == "seismic":
        c_rank = SEISMIC_RANK.get(cell_level, 1)
        m_rank = SEISMIC_RANK.get(max_level, 1)
        return c_rank <= m_rank
    c_rank = LEVEL_RANK.get(cell_level, 0)
    m_rank = LEVEL_RANK.get(max_level, 0)
    return c_rank <= m_rank


def _evaluate_single_h3_cell(
    h3_cell: str,
    requested_hazards: list[str],
    supported_filters: list[dict],
    efas: EFASFloodReader | None,
    geo: Geohazards | None,
    seismic: SeismicReader | None,
) -> tuple[float, float, dict[str, str], list[str], bool]:
    clat, clon = h3.cell_to_latlng(h3_cell)
    cell_hazards: dict[str, str] = {}
    for h in requested_hazards:
        cell_hazards[h] = _eval_cell_hazard(h, clat, clon, efas, geo, seismic)

    failed_filters: list[str] = []
    for f in supported_filters:
        h = f["hazard"]
        max_lvl = f["max_level"]
        actual_lvl = cell_hazards.get(h) or _eval_cell_hazard(h, clat, clon, efas, geo, seismic)
        cell_hazards[h] = actual_lvl
        if not _passes_filter(actual_lvl, max_lvl, h):
            failed_filters.append(h)

    matched = len(failed_filters) == 0
    return clat, clon, cell_hazards, failed_filters, matched


def _build_parent_tier_features(
    base_records: list[dict],
    parent_res: int,
    tier_name: str,
) -> list[dict]:
    """Aggregate evaluated base H3 cells into coarser parent H3 cells (`cell_to_parent`)."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for rec in base_records:
        parent_id = h3.cell_to_parent(rec["h3_index"], parent_res)
        grouped[parent_id].append(rec)

    parent_features: list[dict] = []
    for parent_id, children in grouped.items():
        total_ch = len(children)
        matched_ch = sum(1 for c in children if c["matched"])
        match_ratio = round(matched_ch / total_ch, 2) if total_ch else 0.0
        # Parent cell is marked matched if at least half of its constituent cells pass
        matched = matched_ch * 2 >= total_ch
        clat, clon = h3.cell_to_latlng(parent_id)
        ring = _h3_ring_coordinates(parent_id)

        # Collect union of failed filters from children if parent did not pass
        failed_union = sorted({ff for c in children for ff in c["failed_filters"]}) if not matched else []
        parent_features.append({
            "type": "Feature",
            "properties": {
                "cell_id": parent_id,
                "h3_index": parent_id,
                "h3_res": parent_res,
                "tier": tier_name,
                "matched": matched,
                "match_ratio": match_ratio,
                "children_matched": matched_ch,
                "children_total": total_ch,
                "center_lat": round(clat, 5),
                "center_lon": round(clon, 5),
                "hazards": children[0]["hazards"] if children else {},
                "failed_filters": failed_union,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [ring],
            },
        })
    return parent_features


def evaluate_region_grid(
    validated: dict,
    efas: EFASFloodReader | None = None,
    geo: Geohazards | None = None,
    seismic: SeismicReader | None = None,
    geocoder: AddressGeocoder | None = None,
) -> dict | None:
    """Evaluate multi-resolution Uber H3 cells for a `find_area` query and return a GeoJSON FeatureCollection."""
    if validated.get("intent") != "find_area":
        return None

    region = validated.get("region") or "banovina"
    supported_filters: list[dict] = validated.get("supported_filters") or []
    base_res, base_cells = settlement_h3_cells(region, geocoder)

    requested_hazards = list(dict.fromkeys([f["hazard"] for f in supported_filters] or ["flood"]))

    base_features: list[dict] = []
    base_records: list[dict] = []
    matched_count = 0
    total_area_km2 = 0.0
    matched_area_km2 = 0.0
    min_lon, min_lat = 180.0, 90.0
    max_lon, max_lat = -180.0, -90.0

    for h3_cell in base_cells:
        clat, clon, cell_hazards, failed_filters, matched = _evaluate_single_h3_cell(
            h3_cell, requested_hazards, supported_filters, efas, geo, seismic
        )
        ring = _h3_ring_coordinates(h3_cell)
        cell_area = h3.cell_area(h3_cell, unit="km^2")
        total_area_km2 += cell_area

        for lon_pt, lat_pt in ring:
            if lon_pt < min_lon:
                min_lon = lon_pt
            if lon_pt > max_lon:
                max_lon = lon_pt
            if lat_pt < min_lat:
                min_lat = lat_pt
            if lat_pt > max_lat:
                max_lat = lat_pt

        if matched:
            matched_count += 1
            matched_area_km2 += cell_area

        rec = {
            "h3_index": h3_cell,
            "matched": matched,
            "hazards": cell_hazards,
            "failed_filters": failed_filters,
        }
        base_records.append(rec)

        base_features.append({
            "type": "Feature",
            "properties": {
                "cell_id": h3_cell,
                "h3_index": h3_cell,
                "h3_res": base_res,
                "tier": "base",
                "matched": matched,
                "match_ratio": 1.0 if matched else 0.0,
                "center_lat": round(clat, 5),
                "center_lon": round(clon, 5),
                "hazards": cell_hazards,
                "failed_filters": failed_filters,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [ring],
            },
        })

    # Build coarser parent H3 tiers (res - 2 = "coarse", res - 1 = "medium") using h3.cell_to_parent
    coarse_res = max(4, base_res - 2)
    medium_res = max(5, base_res - 1)
    coarse_features = _build_parent_tier_features(base_records, coarse_res, "coarse")
    medium_features = _build_parent_tier_features(base_records, medium_res, "medium")

    # Build finer child H3 tier (res + 1 = "fine", e.g. res 10 ~ 0.015 km^2) using h3.cell_to_children
    fine_res = min(10, base_res + 1)
    fine_features: list[dict] = []
    if fine_res > base_res:
        for rec in base_records:
            parent_cell = rec["h3_index"]
            for child_cell in sorted(h3.cell_to_children(parent_cell, fine_res)):
                clat, clon, ch_hazards, ch_failed, ch_matched = _evaluate_single_h3_cell(
                    child_cell, requested_hazards, supported_filters, efas, geo, seismic
                )
                ring = _h3_ring_coordinates(child_cell)
                fine_features.append({
                    "type": "Feature",
                    "properties": {
                        "cell_id": child_cell,
                        "h3_index": child_cell,
                        "h3_res": fine_res,
                        "tier": "fine",
                        "matched": ch_matched,
                        "match_ratio": 1.0 if ch_matched else 0.0,
                        "center_lat": round(clat, 5),
                        "center_lon": round(clon, 5),
                        "hazards": ch_hazards,
                        "failed_filters": ch_failed,
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [ring],
                    },
                })

    total_cells = len(base_features)
    excluded_count = total_cells - matched_count
    avg_cell_area = round(total_area_km2 / total_cells, 2) if total_cells else 0.11
    bbox = [round(min_lon, 5), round(min_lat, 5), round(max_lon, 5), round(max_lat, 5)] if base_features else None

    all_features = coarse_features + medium_features + base_features + fine_features

    return {
        "type": "FeatureCollection",
        "summary": {
            "region": region,
            "in_banovina": bool(validated.get("in_banovina", True)),
            "h3_resolution": base_res,
            "resolutions": {
                "coarse": coarse_res,
                "medium": medium_res,
                "base": base_res,
                "fine": fine_res,
            },
            "total_cells": total_cells,
            "matched_cells": matched_count,
            "excluded_cells": excluded_count,
            "cell_area_km2": avg_cell_area,
            "matched_area_km2": round(matched_area_km2, 1),
            "bbox": bbox,
            "odbl_notice": (
                "Izvedena višerezolucijska Uber H3 mreža (rezolucije "
                f"{coarse_res}–{fine_res}) sadrži procjene poplava iz europskog modela "
                "Copernicus EFAS v3.1.1 (ODbL 1.0) te geohazarde MPGI-ja (2021., samo Banovina). "
                "Približite ili udaljite kartu za automatsku promjenu H3 rezolucije."
            ),
        },
        "features": all_features,
    }
