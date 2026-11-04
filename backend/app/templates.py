"""Deterministic Croatian explanation templates and curated recommended actions (SPEC MUST #6, D5).

Works without an LLM: every text and action is derived strictly from HazardResult values.
"""
from __future__ import annotations

from .risk_rules import DEPTH_LABELS, FLOODED, HAZARD_ORDER, HazardResult, Level


HAZARD_NAMES = {
    "flood": "poplave",
    "seismic": "potresna opasnost",
    "landslide": "klizišta",
    "liquefaction": "likvefakcija tla",
    "sinkhole": "vrtače",
    "unfavourable": "nepovoljni uvjeti za gradnju",
    "groundwater": "podzemna voda",
}

# Accusative forms for "Nema podataka za ..." / "povišena opasnost za: ...".
HAZARD_NAMES_ACC = {
    "flood": "poplave",
    "seismic": "potresnu opasnost",
    "landslide": "klizišta",
    "liquefaction": "likvefakciju tla",
    "sinkhole": "vrtače",
    "unfavourable": "nepovoljne uvjete za gradnju",
    "groundwater": "podzemnu vodu",
}

SUSCEPTIBILITY_DATIVE = {
    "landslide": "klizištima",
    "liquefaction": "likvefakciji tla",
    "sinkhole": "nastanku vrtača",
}

PODLOZNOST_GENITIVE = {"niska": "niske", "srednja": "srednje", "visoka": "visoke"}

LEVEL_LABELS = {
    Level.HIGH: "visoko",
    Level.MEDIUM: "srednje",
    Level.LOW: "nisko",
    Level.NONE: "nema prema karti",
    Level.NO_DATA: "nema podataka",
    Level.SEISMIC_VERY_LOW: "vrlo niska seizmičnost",
    Level.SEISMIC_LOW: "niska seizmičnost",
    Level.SEISMIC_ABOVE_LOW: "iznad praga niske seizmičnosti",
}

FALLBACK_TEXT = "Podatak je obrađen prema javno dostupnim izvorima."


def _num(x: float, nd: int) -> str:
    """Format a number with a decimal comma."""
    return f"{x:.{nd}f}".replace(".", ",")


def _hv_scenario_text(label: str, depth_class: str) -> str:
    depth = DEPTH_LABELS.get(depth_class, depth_class)
    return (f"Prema karti opasnosti od poplava Hrvatskih voda (2019.) lokacija je u zoni {label} "
            f"vjerojatnosti poplave, procijenjena dubina vode: {depth}.")


def _explain_flood_hv(r: HazardResult) -> str | None:
    d = r.detail
    if r.level is Level.NONE:
        return ("Prema kartama opasnosti od poplava Hrvatskih voda (2019.) lokacija je izvan poplavnih zona "
                "(poplavnih područja) za sva tri scenarija (velika, srednja i mala vjerojatnost).")
    if any(v == "permanent_water" for v in d.values()):
        return "Prema karti Hrvatskih voda (2019.) točka se nalazi na stalnoj vodenoj površini."
    if d.get("velika") in FLOODED:
        return _hv_scenario_text("velike", d["velika"])
    if d.get("srednja") in FLOODED:
        return _hv_scenario_text("srednje", d["srednja"])
    if d.get("mala") in FLOODED:
        return (_hv_scenario_text("male", d["mala"])[:-1]
                + "; izvan zona velike i srednje vjerojatnosti.")
    return None


EFAS_OUTAGE_WHY = "Model se koristi jer servis Hrvatskih voda trenutačno ne odgovara."


def _explain_flood_efas(r: HazardResult) -> str:
    if r.detail.get("hv_status") == "unavailable":
        why = EFAS_OUTAGE_WHY
    else:
        why = "Model se koristi samo kad podatak Hrvatskih voda nije dostupan."
    if r.level is Level.NONE:
        return ("Procjena (europski model EFAS, 90 m, okvirno): dubina plavljenja je 0 m za povratna "
                f"razdoblja 10, 100 i 500 god. {why}")
    parts = [f"RP{k[2:]}: {_num(val, 2)} m" for k, val in r.detail.items()
             if k.startswith("rp") and val and val > 0]
    joined = ", ".join(parts)
    return (f"Procjena (europski model EFAS, 90 m, okvirno): moguće je plavljenje; dubine po povratnom razdoblju "
            f"(RP, u godinama): {joined}. {why}")


def _explain_seismic(r: HazardResult) -> str | None:
    ag = r.detail.get("ag_g")
    if not isinstance(ag, (int, float)):
        return None
    ag_txt = _num(ag, 3)
    base = f"ag = {ag_txt} g za povratno razdoblje od 475 god."
    if r.level is Level.SEISMIC_VERY_LOW:
        return f"Potresna opasnost: vrlo niska seizmičnost prema Eurokodu 8 ({base}; prag ≤ 0,04 g)."
    if r.level is Level.SEISMIC_LOW:
        return f"Potresna opasnost: niska seizmičnost prema Eurokodu 8 ({base}; raspon 0,04 – 0,08 g)."
    if r.level is Level.SEISMIC_ABOVE_LOW:
        return (f"Potresna opasnost: iznad praga niske seizmičnosti prema Eurokodu 8 ({base}; "
                f"> 0,08 g).")
    return None


def _explain_groundwater(r: HazardResult) -> str | None:
    depth = r.detail.get("dubina_do")
    if not isinstance(depth, (int, float)):
        return None
    if depth < 0:
        what = f"podzemnu vodu iznad razine terena ({_num(abs(depth), 2)} m)"
    else:
        what = f"podzemnu vodu na dubini {_num(depth, 2)} m"
    text = f"Najbliže mjerenje (MPGI, 2021.) bilježi {what}."
    if r.notes:
        return text + " " + " ".join(r.notes)
    dist = r.detail.get("udaljenost_m")
    return text + (f" Bušotina je udaljena {dist} m." if dist is not None else "")


def explain_hazard(r: HazardResult) -> str:
    """Return a plain-language Croatian explanation for a single HazardResult."""
    if r.level is Level.NO_DATA:
        name = HAZARD_NAMES_ACC.get(r.hazard, r.hazard)
        return " ".join([f"Nema podataka za {name}.", *r.notes])

    text: str | None = None
    if r.hazard == "flood" and r.source == "flood_hv":
        text = _explain_flood_hv(r)
    elif r.hazard == "flood" and r.source == "flood_efas":
        text = _explain_flood_efas(r)
    elif r.hazard == "seismic":
        text = _explain_seismic(r)
    elif r.hazard in SUSCEPTIBILITY_DATIVE:
        raw = r.detail.get("podloznost")
        if raw is not None:
            gen = PODLOZNOST_GENITIVE.get(str(raw).strip().lower(), str(raw))
            text = (f"Prema studiji geohazarda MPGI-ja (2021.) lokacija je u zoni {gen} podložnosti "
                    f"{SUSCEPTIBILITY_DATIVE[r.hazard]} (razred u studiji: {raw}).")
    elif r.hazard == "unfavourable":
        if r.level is Level.HIGH:
            text = ("Lokacija se nalazi unutar poligona koji je u studiji geohazarda (MPGI, 2021.) "
                    "izdvojen kao područje nepovoljno za gradnju.")
        elif r.level is Level.NONE:
            text = "Lokacija nije unutar poligona izdvojenih kao nepovoljna za gradnju (MPGI, 2021.)."
    elif r.hazard == "groundwater":
        text = _explain_groundwater(r)
    return text or FALLBACK_TEXT


def build_summary(results: list[HazardResult], top: HazardResult | None, in_banovina_coverage: bool) -> str:
    """Return a concise Croatian summary paragraph for the report header."""
    scope_sentence = (
        "Lokacija se nalazi unutar obuhvata detaljne studije geohazarda za Banovinu (MPGI, 2021.)."
        if in_banovina_coverage
        else "Detaljni podaci o geohazardima (MPGI, 2021.) postoje samo za područje Banovine."
    )
    order = {h: i for i, h in enumerate(HAZARD_ORDER)}
    ordered = sorted(results, key=lambda r: order.get(r.hazard, len(order)))
    no_data = [HAZARD_NAMES_ACC.get(r.hazard, r.hazard) for r in ordered if r.level is Level.NO_DATA]
    with_data = [HAZARD_NAMES_ACC.get(r.hazard, r.hazard) for r in ordered if r.level is not Level.NO_DATA]
    no_data_sentence = f"Nema podataka za: {', '.join(no_data)}." if no_data else ""

    flood = next((r for r in results if r.hazard == "flood"), None)
    outage_sentence = ""
    if flood is not None and flood.detail.get("hv_status") == "unavailable":
        outage_sentence = (
            "Servis Hrvatskih voda trenutačno ne odgovara; podatak o poplavama nije dostupan."
            if flood.level is Level.NO_DATA
            else "Servis Hrvatskih voda trenutačno ne odgovara; podatak o poplavama je nepotpun ili "
                 "procijenjen europskim modelom EFAS.")

    if results and not with_data:
        return (f"Za ovu lokaciju trenutno nema dostupnih podataka o promatranim opasnostima. "
                f"{outage_sentence} {scope_sentence}").replace("  ", " ")
    if top is None:
        if no_data:
            return (f"Prema dostupnim kartama nije utvrđena povišena opasnost za: {', '.join(with_data)}. "
                    f"{no_data_sentence} {outage_sentence} {scope_sentence}").replace("  ", " ")
        return ("Prema dostupnim kartama na odabranoj lokaciji nije utvrđena povišena opasnost. "
                f"{outage_sentence} {scope_sentence}").replace("  ", " ")
    hazard_label = HAZARD_NAMES.get(top.hazard, top.hazard)
    level_label = LEVEL_LABELS.get(top.level, top.level.value)
    top_text = explain_hazard(top)
    if outage_sentence:  # the outage is stated once in the summary (D22)
        top_text = top_text.replace(" " + EFAS_OUTAGE_WHY, "")
    parts = [f"Najznačajniji utvrđeni rizik na lokaciji: {hazard_label} (razina: {level_label}).",
             top_text, no_data_sentence, outage_sentence, scope_sentence]
    return " ".join(p for p in parts if p)


def recommended_actions(results: list[HazardResult]) -> list[dict]:
    """Return a curated list of recommended next steps with institution links based on active hazards."""
    by_hazard = {r.hazard: r for r in results}
    actions: list[dict] = []

    flood = by_hazard.get("flood")
    if flood and flood.level in (Level.HIGH, Level.MEDIUM, Level.LOW):
        actions.append({
            "hazard": "flood",
            "title": "Provjerite vodopravne uvjete i kotu prizemlja",
            "description": (
                "Prije gradnje ili rekonstrukcije raspitajte se o vodopravnim uvjetima kod Hrvatskih voda te "
                "provjerite izvedbu hidroizolacije, povratnih ventila odvodnje i visinu poda prizemlja."
            ),
            "institution": "Hrvatske vode",
            "url": "https://www.voda.hr/",
        })

    seismic = by_hazard.get("seismic")
    if seismic and seismic.level in (Level.SEISMIC_ABOVE_LOW, Level.SEISMIC_LOW):
        actions.append({
            "hazard": "seismic",
            "title": "Provjerite potresnu otpornost zgrade",
            "description": (
                "Preporučuje se provjera potresne otpornosti zgrade uz ovlaštenog inženjera građevinarstva, "
                "osobito kod starijih zgrada, pukotina ili dogradnji."
            ),
            "institution": "Ministarstvo prostornoga uređenja, graditeljstva i državne imovine",
            "url": "https://mpgi.gov.hr/",
        })

    geo_elevated = any(
        by_hazard.get(h) and by_hazard[h].level in (Level.HIGH, Level.MEDIUM)
        for h in ("landslide", "liquefaction", "sinkhole", "unfavourable", "groundwater")
    )
    if geo_elevated:
        actions.append({
            "hazard": "geohazards",
            "title": "Naručite geotehnički i inženjerskogeološki pregled terena",
            "description": (
                "Studija geohazarda (MPGI) regionalnog je karaktera. Za konkretnu česticu preporučuje se "
                "terenski uvid geomehaničara radi provjere stabilnosti padine, temelja, drenaže i podzemne vode."
            ),
            "institution": "Informacijski sustav prostornog uređenja (ISPU)",
            "url": "https://ispu.mgipu.hr/",
        })

    actions.append({
        "hazard": "general",
        "title": "Provjerite podatke o katastarskoj čestici",
        "description": (
            "Na portalu Uređena zemlja provjerite podatke i granice katastarske čestice "
            "prije donošenja odluke o kupnji ili gradnji."
        ),
        "institution": "Uređena zemlja (Državna geodetska uprava)",
        "url": "https://oss.uredjenazemlja.hr/",
    })

    return actions
