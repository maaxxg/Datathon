"""JSON schema and catalogue validation for natural-language queries (SPEC SHOULD #10, D7, D8, D9, D18).

The LLM translates Croatian user text into a JSON object conforming strictly to
`QUERY_JSON_SCHEMA` (passed to Ollama's `format` parameter). The deterministic
validator then checks requested layers against `layers.yaml` coverage (Banovina vs.
whole Croatia) and separates supported filters from unsupported criteria.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Intent(str, Enum):
    FIND_AREA = "find_area"
    COMPARE_LOCATIONS = "compare_locations"
    SHOW_LAYER = "show_layer"


HazardKey = Literal[
    "flood", "seismic", "landslide", "liquefaction", "sinkhole", "unfavourable", "groundwater"
]

AllowedMaxLevel = Literal[
    "nema_prema_karti",
    "vrlo_niska_seizmicnost",
    "nisko",
    "niska_seizmicnost",
    "srednje",
    "iznad_praga_niske_seizmicnosti",
]

BANOVINA_REGIONS = {
    "banovina",
    "sisacko-moslavacka",
    "sisačko-moslavačka",
    "petrinja",
    "sisak",
    "glina",
    "hrvatska kostajnica",
    "topusko",
    "dvori",
    "dvor",
    "lekenik",
    "sunja",
    "martinska ves",
    "donji kukuruzari",
    "majur",
    "gvozd",
}

REGION_COORDS: dict[str, dict[str, float]] = {
    "banovina": {"lat": 45.3500, "lon": 16.3200, "zoom": 10},
    "sisačko-moslavačka": {"lat": 45.3500, "lon": 16.3200, "zoom": 10},
    "sisacko-moslavacka": {"lat": 45.3500, "lon": 16.3200, "zoom": 10},
    "petrinja": {"lat": 45.4375, "lon": 16.2739, "zoom": 13},
    "sisak": {"lat": 45.4896, "lon": 16.3713, "zoom": 13},
    "glina": {"lat": 45.3381, "lon": 16.0881, "zoom": 13},
    "hrvatska kostajnica": {"lat": 45.2289, "lon": 16.5392, "zoom": 13},
    "topusko": {"lat": 45.2975, "lon": 15.9756, "zoom": 13},
    "dvor": {"lat": 45.0731, "lon": 16.3708, "zoom": 13},
    "dvori": {"lat": 45.0731, "lon": 16.3708, "zoom": 13},
    "lekenik": {"lat": 45.5861, "lon": 16.2114, "zoom": 13},
    "sunja": {"lat": 45.3675, "lon": 16.5672, "zoom": 13},
    "zagreb": {"lat": 45.7930, "lon": 15.9600, "zoom": 12},
    "split": {"lat": 43.5081, "lon": 16.4402, "zoom": 12},
    "osijek": {"lat": 45.5550, "lon": 18.6955, "zoom": 12},
    "karlovac": {"lat": 45.4870, "lon": 15.5480, "zoom": 12},
    "gunja": {"lat": 44.8810, "lon": 18.8450, "zoom": 13},
    "rijeka": {"lat": 45.3271, "lon": 14.4422, "zoom": 12},
    "zadar": {"lat": 44.1194, "lon": 15.2314, "zoom": 12},
}


class HazardFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hazard: HazardKey = Field(description="Canonical hazard identifier from the layer catalogue.")
    max_level: AllowedMaxLevel = Field(
        description="Maximum acceptable risk level for this hazard (e.g. 'nema_prema_karti' for no hazard, 'nisko' for at most low)."
    )


class ParsedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent = Field(description="User intent: find_area, compare_locations, or show_layer.")
    region: str | None = Field(
        default=None,
        description="Target settlement, municipality, or region in Croatia (lowercase nominative, e.g. 'petrinja', 'sisak', 'banovina', 'zagreb').",
    )
    filters: list[HazardFilter] = Field(
        default_factory=list,
        description="Deterministic hazard filters requested by the user.",
    )
    locations: list[str] = Field(
        default_factory=list,
        description="Addresses or place names when intent is 'compare_locations' (up to 2 locations).",
    )
    layer: str | None = Field(
        default=None,
        description="Layer key when intent is 'show_layer' (e.g. 'flood_hv', 'liquefaction', 'seismic', 'landslide', 'sinkhole', 'unfavourable', 'flood_efas').",
    )
    unsupported: list[str] = Field(
        default_factory=list,
        description="Short Croatian labels for parts of the user query that are outside the data catalogue (e.g. 'požari', 'cijene nekretnina', 'buka', 'kvaliteta zraka', 'nagib terena').",
    )


QUERY_JSON_SCHEMA: dict = ParsedQuery.model_json_schema()


def is_banovina_region(region: str | None) -> bool:
    if not region:
        return True  # default search area is Banovina
    norm = region.strip().lower()
    return norm in BANOVINA_REGIONS


def resolve_region_center(region: str | None) -> dict[str, float] | None:
    if not region:
        return REGION_COORDS["banovina"]
    norm = region.strip().lower()
    return REGION_COORDS.get(norm)


def validate_against_catalogue(query: ParsedQuery, catalogue: dict) -> dict:
    """Split filters into executable filters and explicit Croatian explanations of what is not possible."""
    layers_cfg = catalogue.get("layers", {})
    in_banovina = is_banovina_region(query.region)

    supported_filters: list[dict] = []
    warnings: list[str] = []

    for item in query.unsupported:
        warnings.append(f"Kriterij „{item}” nije podržan u dostupnim otvorenim podacima (izvan opsega sustava).")

    for f in query.filters:
        # Map canonical 'flood' to HV/EFAS (available nationally) and others to their layer key
        layer_key = "flood_hv" if f.hazard == "flood" else f.hazard
        layer_meta = layers_cfg.get(layer_key, {})
        coverage = layer_meta.get("coverage", "banovina")

        if coverage == "banovina" and not in_banovina:
            title = layer_meta.get("title", f.hazard)
            warnings.append(
                f"Sloj „{title}” dostupan je samo za područje Banovine (Sisačko-moslavačka županija), "
                f"pa se ne može primijeniti na regiju „{query.region}”."
            )
            continue

        supported_filters.append({"hazard": f.hazard, "max_level": f.max_level})

    return {
        "intent": query.intent.value,
        "region": query.region or "banovina",
        "in_banovina": in_banovina,
        "center": resolve_region_center(query.region),
        "supported_filters": supported_filters,
        "locations": query.locations,
        "layer": query.layer,
        "warnings": warnings,
    }
