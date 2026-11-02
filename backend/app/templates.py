"""Deterministic Croatian explanation templates and curated recommended actions (SPEC MUST #6, D5).

Works without an LLM: every text and action is derived strictly from HazardResult values.
"""
from __future__ import annotations

from .risk_rules import FLOODED, HazardResult, Level

DEPTH_LABELS = {
    "d_lt_0_5": "do 0,5 m",
    "d_0_5_1_5": "0,5 – 1,5 m",
    "d_1_5_2_5": "1,5 – 2,5 m",
    "d_gt_2_5": "više od 2,5 m",
    "permanent_water": "stalna vodena površina",
}

HAZARD_NAMES = {
    "flood": "poplave",
    "seismic": "potresna opasnost",
    "landslide": "klizišta",
    "liquefaction": "likvefakcija tla",
    "sinkhole": "vrtače (urušne ponikve)",
    "unfavourable": "nepovoljni uvjeti za gradnju",
    "groundwater": "plitka podzemna voda",
}

SUSCEPTIBILITY_DATIVE = {
    "landslide": "klizištima",
    "liquefaction": "likvefakciji tla",
    "sinkhole": "nastanku vrtača",
}


def explain_hazard(r: HazardResult) -> str:
    """Return a plain-language Croatian explanation for a single HazardResult."""
    if r.hazard == "flood" and r.source == "flood_hv":
        if r.level is Level.NO_DATA:
            return "Za ovu lokaciju podatak iz servisa Hrvatskih voda trenutno nije dostupan."
        if r.level is Level.NONE:
            return ("Prema službenim kartama opasnosti od poplava Hrvatskih voda (2019.), "
                    "lokacija je izvan poplavnih zona za veliku, srednju i malu vjerojatnost.")
        if any(v == "permanent_water" for v in r.detail.values()):
            return "Prema karti Hrvatskih voda (2019.), točka se nalazi na stalnoj vodenoj površini."
        if r.detail.get("velika") in FLOODED:
            d = DEPTH_LABELS.get(r.detail["velika"], r.detail["velika"])
            return (f"Lokacija je u zoni velike vjerojatnosti poplave (povratno razdoblje 25 godina) "
                    f"s procijenjenom dubinom vode {d}.")
        if r.detail.get("srednja") in FLOODED:
            d = DEPTH_LABELS.get(r.detail["srednja"], r.detail["srednja"])
            return (f"Lokacija je u zoni srednje vjerojatnosti poplave (100-godišnje vode) "
                    f"s procijenjenom dubinom vode {d}.")
        if r.detail.get("mala") in FLOODED:
            d = DEPTH_LABELS.get(r.detail["mala"], r.detail["mala"])
            return (f"Lokacija je izvan zona čestih i 100-godišnjih poplava, ali ulazi u zonu male "
                    f"vjerojatnosti (ekstremne poplave) s procijenjenom dubinom vode {d}.")

    if r.hazard == "flood" and r.source == "flood_efas":
        if r.level is Level.NONE:
            return ("Prema europskom modelu riječnih poplava EFAS (rezolucija 90 m), "
                    "na lokaciji nije modelirano plavljenje za povratna razdoblja do 500 godina.")
        parts = [f"RP{rp[2:]}: {val:.2f} m" for rp, val in r.detail.items() if val and val > 0]
        joined = ", ".join(parts) if parts else "zabilježena dubina > 0 m"
        return (f"Okvirni europski model EFAS (90 m) upućuje na mogućnost plavljenja ({joined}); "
                "koristi se jer službena karta Hrvatskih voda ovdje nema podatka.")

    if r.hazard == "seismic":
        ag = r.detail.get("ag_g")
        ag_txt = f"{ag:.3f} g".replace(".", ",") if isinstance(ag, (int, float)) else "nepoznato"
        if r.level is Level.SEISMIC_VERY_LOW:
            return (f"Vrlo niska seizmičnost prema Eurokodu 8 (referentno vršno ubrzanje tla "
                    f"ag = {ag_txt} ≤ 0,04 g za povratno razdoblje od 475 godina).")
        if r.level is Level.SEISMIC_LOW:
            return (f"Niska seizmičnost prema Eurokodu 8 (ag = {ag_txt}, u rasponu 0,04–0,08 g "
                    "za povratno razdoblje od 475 godina).")
        if r.level is Level.SEISMIC_ABOVE_LOW:
            return (f"Potresna opasnost je iznad praga niske seizmičnosti prema Eurokodu 8 "
                    f"(ag = {ag_txt} > 0,08 g za 475 godina); pri gradnji i rekonstrukciji "
                    "obvezan je puni protupotresni proračun.")
        return "Podatak o referentnom vršnom ubrzanju tla (potresnoj opasnosti) još nije dostupan."

    if r.hazard in SUSCEPTIBILITY_DATIVE:
        dativ = SUSCEPTIBILITY_DATIVE[r.hazard]
        if r.level is Level.NO_DATA:
            return (f"Podatak o podložnosti {dativ} nije dostupan (studija MPGI-ja iz 2021. "
                    "pokriva područje Banovine ili točka nije unutar poligona studije).")
        if r.level is Level.NONE:
            return f"Prema studiji geohazarda (MPGI, 2021.), na lokaciji nije utvrđena podložnost {dativ}."
        raw = r.detail.get("podloznost", r.level.value)
        return (f"Prema studiji geohazarda (MPGI, 2021.), lokacija se nalazi u zoni "
                f"s razredom podložnosti {dativ}: {raw}.")

    if r.hazard == "unfavourable":
        if r.level is Level.NO_DATA:
            return "Podatak o područjima nepovoljnima za gradnju dostupan je samo za obuhvat studije u Banovini."
        if r.level is Level.HIGH:
            return ("Lokacija se nalazi unutar poligona koji je u studiji geohazarda (MPGI, 2021.) "
                    "izdvojen kao područje nepovoljno za gradnju.")
        return "Lokacija nije unutar poligona izdvojenih kao nepovoljna za gradnju (MPGI, 2021.)."

    if r.hazard == "groundwater":
        if r.level is Level.NO_DATA:
            return "Nema dostupnog mjerenja dubine podzemne vode u radijusu od 1 km (studija Banovina, 2021.)."
        depth = r.detail.get("dubina_do")
        dist = r.detail.get("udaljenost_m")
        date = r.detail.get("datum_mjerenja") or "2021."
        depth_txt = f"{depth:.2f} m".replace(".", ",") if isinstance(depth, (int, float)) else f"{depth} m"
        return (f"Najbliže točkasto mjerenje podzemne vode (udaljeno {dist} m, datum {date}) "
                f"bilježi razinu podzemne vode na dubini od {depth_txt}.")

    return "Podatak je obrađen prema javno dostupnim izvorima."


def build_summary(results: list[HazardResult], top: HazardResult | None, in_banovina_coverage: bool) -> str:
    """Return a concise Croatian summary paragraph for the report header."""
    scope_sentence = (
        "Lokacija se nalazi unutar obuhvata detaljne studije geohazarda za Banovinu (MPGI, 2021.)."
        if in_banovina_coverage
        else "Za ovu lokaciju dostupni su nacionalni slojevi (poplave i potres), dok detaljni geohazardi "
             "MPGI-ja pokrivaju samo Sisačko-moslavačku županiju (Banovinu)."
    )
    if top is None:
        return (f"Prema dostupnim kartama na odabranoj lokaciji nije utvrđena povišena opasnost. "
                f"{scope_sentence}")
    hazard_label = HAZARD_NAMES.get(top.hazard, top.hazard)
    level_label = top.level.value.replace("_", " ")
    return (f"Najznačajniji utvrđeni rizik na lokaciji: {hazard_label} (razina: {level_label}). "
            f"{explain_hazard(top)} {scope_sentence}")


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
                "Prije kupnje ili gradnje zatražite službene vodopravne uvjete od Hrvatskih voda te "
                "provjerite izvedbu hidroizolacije, povratnih ventila odvodnje i visinu poda prizemlja."
            ),
            "institution": "Hrvatske vode",
            "url": "https://www.voda.hr/hr/karte-opasnosti-od-poplava-karte-rizika-od-poplava-2019",
        })

    seismic = by_hazard.get("seismic")
    if seismic and seismic.level in (Level.SEISMIC_ABOVE_LOW, Level.SEISMIC_LOW):
        actions.append({
            "hazard": "seismic",
            "title": "Provjerite godinu gradnje i potresnu otpornost zgrade",
            "description": (
                "Zgrade građene prije 1964. (bez protupotresnih propisa) ili prije uvođenja Eurokoda 8 "
                "zahtijevaju pregled ovlaštenog inženjera građevinarstva, osobito ako postoje pukotine ili dogradnje."
            ),
            "institution": "MPGI / Hrvatska komora inženjera građevinarstva",
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
            "institution": "Informacijski sustav prostornog uređenja (ISPU) / Hrvatski geološki institut",
            "url": "https://ispu.mgipu.hr/",
        })

    actions.append({
        "hazard": "general",
        "title": "Provjerite prostorni plan, katastar i upute civilne zaštite",
        "description": (
            "Uvidom u ISPU i Uređenu zemlju provjerite uvjete gradnje na katastarskoj čestici, "
            "a na stranicama Ravnateljstva civilne zaštite pregledajte lokalne planove djelovanja."
        ),
        "institution": "Uređena zemlja (DGU) i Ravnateljstvo civilne zaštite",
        "url": "https://oss.uredjenazemlja.hr/",
    })

    return actions
