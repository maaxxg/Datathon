"""Deterministic risk rules (SPEC section 6, decisions D4, D13 and D16).

Every function maps raw source values to a level. No weighting, no AI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum


class Level(str, Enum):
    HIGH = "visoko"
    MEDIUM = "srednje"
    LOW = "nisko"
    NONE = "nema_prema_karti"      # source covers the point and shows no hazard
    NO_DATA = "nema_podataka"      # source does not cover the point or is unavailable
    # seismic classes (Eurocode 8, EN 1998-1 3.2.1)
    SEISMIC_VERY_LOW = "vrlo_niska_seizmicnost"
    SEISMIC_LOW = "niska_seizmicnost"
    SEISMIC_ABOVE_LOW = "iznad_praga_niske_seizmicnosti"


# Severity is used only to pick the "most significant" hazard, never shown as a score.
SEVERITY = {
    Level.HIGH: 3, Level.SEISMIC_ABOVE_LOW: 2, Level.MEDIUM: 2,
    Level.LOW: 1, Level.SEISMIC_LOW: 1, Level.SEISMIC_VERY_LOW: 0,
    Level.NONE: 0, Level.NO_DATA: -1,
}
# Tie-break order from SPEC section 6.
HAZARD_ORDER = ["flood", "seismic", "landslide", "liquefaction", "sinkhole", "unfavourable", "groundwater"]


@dataclass
class HazardResult:
    hazard: str
    level: Level
    source: str                      # key in layers.yaml
    detail: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# --- floods -----------------------------------------------------------------

FLOODED = {"d_lt_0_5", "d_0_5_1_5", "d_1_5_2_5", "d_gt_2_5"}
DEEP = {"d_1_5_2_5", "d_gt_2_5"}


def flood_hv_level(classes: dict[str, str | None]) -> HazardResult:
    """classes: scenario ('velika'|'srednja'|'mala') -> depth class, 'outside', or None if unavailable."""
    detail = dict(classes)
    if any(v is None for v in classes.values()):
        return HazardResult("flood", Level.NO_DATA, "flood_hv", detail,
                            ["Servis Hrvatskih voda nije odgovorio za sve scenarije."])
    if any(v == "permanent_water" for v in classes.values()):
        return HazardResult("flood", Level.HIGH, "flood_hv", detail,
                            ["Točka je na stalnoj vodenoj površini prema karti."])
    if classes.get("velika") in FLOODED:
        return HazardResult("flood", Level.HIGH, "flood_hv", detail)
    srednja = classes.get("srednja")
    if srednja in DEEP:
        return HazardResult("flood", Level.HIGH, "flood_hv", detail)
    if srednja in FLOODED:
        return HazardResult("flood", Level.MEDIUM, "flood_hv", detail)
    if classes.get("mala") in FLOODED:
        return HazardResult("flood", Level.LOW, "flood_hv", detail)
    return HazardResult("flood", Level.NONE, "flood_hv", detail)


def flood_efas_level(depths_m: dict[int, float | None]) -> HazardResult:
    """depths_m: return period (years) -> depth in m; None = not covered / not loaded; 0 = dry.

    Used only where HV has no data. If any of RP10/100/500 is missing or None the point is
    not covered by EFAS -> NO_DATA (never NONE).
    """
    detail = {f"rp{k}": v for k, v in sorted(depths_m.items())}
    if any(depths_m.get(rp) is None for rp in (10, 100, 500)):
        return HazardResult("flood", Level.NO_DATA, "flood_efas", detail,
                            ["Europski model EFAS prikazuje samo poplave uz veće rijeke; za ovu točku nema podatka."])
    notes = ["Europski model (90 m), okvirna procjena; podatak s karte Hrvatskih voda ovdje nije dostupan."]

    if depths_m[10] > 0:
        level = Level.HIGH
    elif depths_m[100] > 0:
        level = Level.MEDIUM
    elif depths_m[500] > 0:
        level = Level.LOW
    else:
        level = Level.NONE
    return HazardResult("flood", level, "flood_efas", detail, notes)


def combine_flood(hv: HazardResult, efas: HazardResult | None) -> HazardResult:
    """HV is authoritative; EFAS replaces it only if HV is NO_DATA and EFAS has data.

    If both are NO_DATA, return HV with the EFAS notes appended (both reasons visible).
    """
    if hv.level is not Level.NO_DATA or efas is None:
        return hv
    if efas.level is Level.NO_DATA:
        return replace(hv, notes=[*hv.notes, *efas.notes])
    return efas


# --- earthquake -------------------------------------------------------------

def seismic_level(ag_g: float | None, distance_km: float | None = None, source: str = "seismic") -> HazardResult:
    """ag_g: PGA for reference rock (Vs30 = 760 m/s), 475-year return period, in g.

    distance_km: distance to the nearest ESHM20 grid point (no interpolation).
    """
    if ag_g is None:
        return HazardResult("seismic", Level.NO_DATA, source,
                            notes=["Podatak o potresnoj opasnosti nije dostupan za ovu lokaciju."])
    if ag_g <= 0.04:
        level = Level.SEISMIC_VERY_LOW
    elif ag_g <= 0.08:
        level = Level.SEISMIC_LOW
    else:
        level = Level.SEISMIC_ABOVE_LOW
    detail = {"ag_g": round(ag_g, 3)}
    if distance_km is not None:
        detail["udaljenost_km"] = round(distance_km, 1)
    notes = ["Okvirna vrijednost iz europskog modela ESHM20 (najbliža točka mreže ~10 km, stijena Vs30 = 760 m/s)."]
    return HazardResult("seismic", level, source, detail, notes)


# --- geohazards (Banovina) --------------------------------------------------

SUSCEPTIBILITY = {"niska": Level.LOW, "srednja": Level.MEDIUM, "visoka": Level.HIGH}


def susceptibility_level(hazard: str, value: str | None, in_coverage: bool) -> HazardResult:
    if not in_coverage:
        return HazardResult(hazard, Level.NO_DATA, hazard, notes=["Izvan obuhvata studije (Banovina)."])
    if value is None:
        return HazardResult(hazard, Level.NO_DATA, hazard, notes=["Točka nije unutar poligona studije."])
    level = SUSCEPTIBILITY.get(value.strip().lower())
    if level is None:
        return HazardResult(hazard, Level.NO_DATA, hazard, {"raw": value}, ["Nepoznat razred u podacima."])
    return HazardResult(hazard, level, hazard, {"podloznost": value})


def unfavourable_level(inside: bool, in_coverage: bool) -> HazardResult:
    if not in_coverage:
        return HazardResult("unfavourable", Level.NO_DATA, "unfavourable",
                            notes=["Izvan obuhvata studije (Banovina)."])
    return HazardResult("unfavourable", Level.HIGH if inside else Level.NONE, "unfavourable")


_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _format_measurement_date(raw: str | None) -> str:
    """Normalise inconsistent strings ('4.02.2021.') to '4. 2. 2021.'; fallback '2021. (datum mjerenja nije naveden)'."""
    m = _DATE_RE.search(raw or "")
    if not m:
        return "2021. (datum mjerenja nije naveden)"
    d, mo, y = m.groups()
    return f"{int(d)}. {int(mo)}. {y}."


def groundwater_level(hit: dict | None, in_coverage: bool, layer_loaded: bool = True) -> HazardResult:
    """hit: {'dubina_do': float, 'datum_mjerenja': str | None, 'udaljenost_m': int} from nearest well <= 1 km."""
    if not in_coverage:
        return HazardResult("groundwater", Level.NO_DATA, "groundwater",
                            notes=["Izvan obuhvata studije (Banovina)."])
    if not layer_loaded:
        return HazardResult("groundwater", Level.NO_DATA, "groundwater",
                            notes=["Sloj podzemne vode nije učitan."])
    if hit is None or hit.get("dubina_do") is None:
        return HazardResult("groundwater", Level.NO_DATA, "groundwater",
                            notes=["Nema točke mjerenja podzemne vode unutar 1 km."])
    depth = float(hit["dubina_do"])
    if depth < 1.5:
        level = Level.HIGH
    elif depth <= 3.0:
        level = Level.MEDIUM
    else:
        level = Level.LOW
    when = _format_measurement_date(hit.get("datum_mjerenja"))
    dist = hit.get("udaljenost_m")
    if when.startswith("2021. ("):
        first = f"Jedno mjerenje iz 2021. (datum mjerenja nije naveden; bušotina udaljena {dist} m). "
    else:
        first = f"Jedno mjerenje od {when} (bušotina udaljena {dist} m). "
    notes = [first + "Razina podzemne vode mijenja se tijekom godine."]
    if depth < 0:
        notes.append("Mjerenje pokazuje vodu iznad razine terena.")
    return HazardResult("groundwater", level, "groundwater", dict(hit), notes)


# --- summary ----------------------------------------------------------------

def most_significant(results: list[HazardResult]) -> HazardResult | None:
    candidates = [r for r in results if SEVERITY[r.level] > 0]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (SEVERITY[r.level], -HAZARD_ORDER.index(r.hazard)))
