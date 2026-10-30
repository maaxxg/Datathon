"""Phase 1 data feasibility checks for Geo-rizik.

Usage:  pip install requests pillow
        python scripts/check_sources.py

Re-runs the checks summarised in docs/DATA_INVENTORY.md and prints JSON.
Nothing here is cached or invented: every value comes from a live request.
"""
from __future__ import annotations

import io
import json
import time
import xml.etree.ElementTree as ET

import requests
from PIL import Image

CKAN = "https://data.gov.hr/ckan/api/3/action/package_show?id="
SLUGS = [
    "geohazardi", "karte-opasnosti-od-poplava", "karte-rizika-od-poplava",
    "adrese-inspire", "visine-inspire", "katastarske-cestice-i-katastarske-opcine-inspire",
    "zgrade-iz-digitalnog-katastarskog-plana-inspire", "ekolo-ka-mre-a-natura-2000",
]
GEOHAZARD_HOSTS = [f"https://gis{i}.mgipu.hr/srv1/RGN_MGIPU_Public/wfs" for i in (1, 2, 3, 4)]
GEOHAZARD_LAYERS = [
    "RGN_kliziste_podloznost", "RGN_likvefakcija_podloznost", "RGN_vrtaca_podloznost",
    "RGN_podzemna_voda_dubina", "RGN_nepovoljno_za_gradnju",
]
VODA_WMS = "https://servisi.voda.hr/wms"
FLOOD_LAYERS = {
    s: f"poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-{s}-vjerojatnost_2019"
    for s in ("velika", "srednja", "mala")
}
# Exact legend colours (GetLegendGraphic, 30.10.2026.)
FLOOD_COLOURS = {
    (0xBE, 0xE8, 0xFF): "dubina < 0,5 m",
    (0x73, 0xDF, 0xFF): "dubina 0,5-1,5 m",
    (0x73, 0xB2, 0xFF): "dubina 1,5-2,5 m",
    (0x7A, 0x8E, 0xF5): "dubina > 2,5 m",
    (0x00, 0x4D, 0xA8): "stalna vodena povrsina",
}
POINTS = {  # lat, lon (WGS84)
    "Petrinja": (45.4375, 16.2739),
    "Sisak": (45.4840, 16.3740),
    "Karlovac": (45.4870, 15.5480),
    "Gunja": (44.8810, 18.8450),
    "ZagrebSava": (45.7930, 15.9600),
    "Split": (43.5081, 16.4402),
}

session = requests.Session()


def timed_get(url: str, **params):
    t0 = time.perf_counter()
    r = session.get(url, params=params or None, timeout=60)
    return r, round((time.perf_counter() - t0) * 1000)


def check_ckan() -> dict:
    out = {}
    for slug in SLUGS:
        r, ms = timed_get(CKAN + slug)
        body = r.json()
        if not body.get("success"):
            out[slug] = {"found": False, "ms": ms}
            continue
        p = body["result"]
        out[slug] = {
            "found": True,
            "publisher": (p.get("organization") or {}).get("title"),
            "license": p.get("license_title"),
            "modified": p.get("metadata_modified"),
            "spatial": p.get("spatial_text") or p.get("spatial_uri"),
            "resources": [f'{x["format"]} {x["url"]}' for x in p["resources"]],
        }
    return out


def flood_class(lat: float, lon: float, layer: str, half: float = 0.01, n: int = 201) -> str:
    """Read the centre pixel of a small GetMap render; layer is not GetFeatureInfo-queryable."""
    r, _ = timed_get(
        VODA_WMS, SERVICE="WMS", VERSION="1.3.0", REQUEST="GetMap", LAYERS=layer, STYLES="",
        CRS="EPSG:4326", BBOX=f"{lat-half},{lon-half},{lat+half},{lon+half}",
        WIDTH=n, HEIGHT=n, FORMAT="image/png", TRANSPARENT="true",
    )
    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    red, green, blue, alpha = img.getpixel((n // 2, n // 2))
    if alpha < 200:
        return "izvan zone"
    return FLOOD_COLOURS.get((red, green, blue), f"nepoznata boja #{red:02X}{green:02X}{blue:02X}")


def check_floods() -> dict:
    return {
        name: {scen: flood_class(lat, lon, lyr) for scen, lyr in FLOOD_LAYERS.items()}
        for name, (lat, lon) in POINTS.items()
    }


def check_geohazards() -> dict:
    out = {"hosts": {}, "layers": {}}
    working = None
    for host in GEOHAZARD_HOSTS:
        try:
            r, ms = timed_get(host, service="WFS", request="GetCapabilities")
            ok = r.ok and b"FeatureType" in r.content
        except requests.RequestException as exc:
            out["hosts"][host] = f"ERR {exc}"
            continue
        out["hosts"][host] = {"status": r.status_code, "ms": ms, "ok": ok}
        if ok and working is None:
            working = host
            root = ET.fromstring(r.content)
            ns = {"wfs": "http://www.opengis.net/wfs/2.0", "ows": "http://www.opengis.net/ows/1.1"}
            out["bbox"] = {
                ft.findtext("wfs:Name", namespaces=ns): (
                    ft.findtext("ows:WGS84BoundingBox/ows:LowerCorner", namespaces=ns),
                    ft.findtext("ows:WGS84BoundingBox/ows:UpperCorner", namespaces=ns),
                )
                for ft in root.iter("{http://www.opengis.net/wfs/2.0}FeatureType")
            }
    if working is None:
        return out
    for layer in GEOHAZARD_LAYERS:
        r, ms = timed_get(
            working, service="WFS", version="2.0.0", request="GetFeature",
            typeNames=f"RGN_MGIPU_Public:{layer}", outputFormat="application/json",
            srsName="EPSG:4326",
        )
        fc = r.json()
        out["layers"][layer] = {
            "download_ms": ms,
            "features": len(fc["features"]),
            "attributes": sorted({k for f in fc["features"] for k in (f["properties"] or {})}),
            "geom_types": sorted({(f.get("geometry") or {}).get("type") for f in fc["features"]} - {None}),
        }
    return out


if __name__ == "__main__":
    report = {
        "ckan": check_ckan(),
        "floods": check_floods(),
        "geohazards": check_geohazards(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
