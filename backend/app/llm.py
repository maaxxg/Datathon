"""Ollama LLM adapter for natural-language JSON queries, report explanations, and Q&A (SPEC SHOULD #10 & #12, D5, D7, D9, D18).

Strict grounding rules:
- The LLM NEVER computes or modifies risk levels; all risk levels come from `risk_rules.py`.
- For NL search (`POST /api/query`), Ollama's `format` parameter is constrained to `QUERY_JSON_SCHEMA`.
- For report explanation (`POST /api/report/explain`) and Q&A (`POST /api/report/ask`), the LLM receives
  ONLY the deterministic report JSON (levels, details, sources, notes, recommended actions, disclaimer).
- When Ollama is offline or unreachable, deterministic Croatian fallbacks ensure the application
  continues to work without failure (SPEC §8).
"""
from __future__ import annotations

import json
import os
import re
import httpx

from .query_schema import (
    QUERY_JSON_SCHEMA,
    HazardFilter,
    Intent,
    ParsedQuery,
)
from .templates import HAZARD_NAMES, LEVEL_LABELS
from .risk_rules import Level

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_OLLAMA_TIMEOUT = 25.0

NL_QUERY_SYSTEM_PROMPT = """Ti si prevoditelj hrvatskih korisničkih upita u strogi JSON format za sustav Geo-rizik.
Tvoj jedini zadatak je pretvoriti tekstualni upit korisnika u JSON objekt prema zadanoj JSON shemi.
Nikada ne izmišljaj polja izvan sheme.

Pravila mapiranja:
1. `intent`:
   - "find_area": korisnik traži područja/lokacije/zone prema uvjetima opasnosti (npr. "Pronađi područja oko Petrinje bez poplava...").
   - "compare_locations": korisnik traži usporedbu dviju adresa ili lokacija (npr. "Usporedi Ulicu X u Petrinji s Ulicom Y u Sisku").
   - "show_layer": korisnik traži uključivanje ili prikaz određenog sloja na karti (npr. "Uključi na karti sloj podložnosti likvefakciji").

2. `region`:
   - Naziv naselja, općine, grada ili regije u nominativu jednine malim slovima (npr. "petrinja", "sisak", "glina", "banovina", "hrvatska kostajnica", "lekenik", "sunja", "topusko", "dvor", "split", "osijek", "zagreb", "karlovac").
   - Ako regija nije navedena (npr. kod compare_locations ili općeg show_layer), postavi na `null`.

3. `filters` (samo za `find_area`):
   - Kanonski nazivi opasnosti (`hazard`):
     - "flood" (poplave)
     - "seismic" (potres, seizmičnost)
     - "landslide" (klizišta)
     - "liquefaction" (likvefakcija tla)
     - "sinkhole" (vrtače, ponikve)
     - "unfavourable" (nepovoljno za gradnju / povoljno za gradnju)
     - "groundwater" (podzemna voda)
   - Dopuštene vrijednosti `max_level`:
     - "nema_prema_karti": kad korisnik traži "bez poplava", "izvan poplavnih zona", "nije nepovoljno za gradnju", "povoljno za gradnju".
     - "nisko": kad korisnik traži "niska podložnost", "nizak rizik", "duboka podzemna voda", ili kaže "bez klizišta / bez vrtača / bez likvefakcije" (jer ti slojevi imaju razrede niska/srednja/visoka).
     - "srednje": kad korisnik dopušta do srednje razine ("najviše srednja").
     - "vrlo_niska_seizmicnost": za vrlo nisku seizmičnost (≤ 0,04 g).
     - "niska_seizmicnost": za nisku seizmičnost (≤ 0,08 g).
     - "iznad_praga_niske_seizmicnosti": za seizmičnost iznad niske.

4. `locations` (samo za `compare_locations`):
   - Niz od najviše 2 adrese/lokacije u čitljivom nominativnom obliku "Ulica i broj, Grad" (npr. ["Ulica Matije Gupca 12, Petrinja", "Rimska ulica 19, Sisak"]).

5. `layer` (samo za `show_layer`):
   - Jedan od ključeva sloja: "flood_hv", "flood_efas", "seismic", "landslide", "liquefaction", "sinkhole", "unfavourable", "groundwater".

6. `unsupported`:
   - Kratki hrvatski nazivi kriterija koje korisnik spominje, a nisu u gornjem katalogu prirodnih opasnosti:
     npr. "cijene nekretnina", "buka", "požari", "kvaliteta zraka", "udaljenost od osnovne škole", "nagib terena".
"""

REPORT_EXPLAIN_SYSTEM_PROMPT = """Ti si stručni komunikacijski asistent sustava Geo-rizik za građane (kupce i najmoprimce nekretnina u Hrvatskoj).
Dobit ćeš isključivo deterministički JSON izvještaj o izloženosti lokacije prirodnim opasnostima.

Stroga pravila:
1. Piši na jasnom, prirodnom i pristupačnom hrvatskom jeziku (3 do 5 kratkih odlomaka ili preglednih točaka).
2. NIKADA ne izmišljaj podatke, razine opasnosti, brojke, povratna razdoblja, dubine, ubrzanja tla (ag) niti izvore koji nisu u priloženom JSON-u.
3. Ne mijenjaj razine opasnosti iz JSON-a. Sve razine su već izračunate determinističkim pravilima.
4. Strogo razlikuj "nema_prema_karti" (izvor pokriva lokaciju i ne prikazuje opasnost) od "nema_podataka" (za tu lokaciju izvor nema podataka, npr. geohazardi MPGI-ja pokrivaju samo Banovinu).
5. Obavezno spomeni važna ograničenja iz polja `notes` i `source.note` (npr. ESHM20 potres je okvirni model na mreži ~10 km za referentnu stijenu Vs30 = 760 m/s; podzemna voda je jedno mjerenje iz 2021.; eventualni privremeni prekid Hrvatskih voda).
6. Na kraju kratko podsjeti na preporučene korake iz polja `recommended_actions` i napomenu da izvještaj nije stručno mišljenje ni službena potvrda.
"""

REPORT_QA_SYSTEM_PROMPT = """Ti si asistent sustava Geo-rizik koji odgovara na pitanja korisnika isključivo na temelju priloženog determinističkog JSON izvještaja za odabranu lokaciju.

Stroga pravila:
1. Odgovaraj isključivo na hrvatskom jeziku, kratko, jasno i točno.
2. Koristi SAMO činjenice, razine, detalje, napomene (`notes`), izvore (`source`) i preporučene korake (`recommended_actions`) iz priloženog JSON izvještaja.
3. NIKADA ne računaj nove razine rizika i ne nagađaj o svojstvima terena ili zgrade koja nisu u JSON-u.
4. Strogo razlikuj "nema rizika prema karti" (`nema_prema_karti`) i "nema podataka" (`nema_podataka`).
5. Ako korisnik pita za nešto što nije u izvještaju (npr. cijene nekretnina, šumski požari, kvaliteta zraka, buka, statika konkretne zgrade, građevinska dozvola), izričito reci da taj podatak nije dio ovog izvještaja ni korištenih otvorenih podataka te uputi korisnika na nadležne institucije iz `recommended_actions`.
"""


# --- Deterministic Croatian Fallbacks (when Ollama is offline) ---------------

_REGION_PATTERNS: list[tuple[str, str]] = [
    (r"\bhrvatsk\w+\s+kostajnic\w*\b", "hrvatska kostajnica"),
    (r"\bmartinsk\w+\s+ves\w*\b", "martinska ves"),
    (r"\bdonj\w+\s+kukuruzar\w*\b", "donji kukuruzari"),
    (r"\bsisačko-moslavačk\w*\b", "sisačko-moslavačka"),
    (r"\bpetrinj\w*\b", "petrinja"),
    (r"\bsisk\w*\b|\bsisak\b", "sisak"),
    (r"\bglin\w*\b", "glina"),
    (r"\bbanovin\w*\b", "banovina"),
    (r"\blekenik\w*\b", "lekenik"),
    (r"\bsunj\w*\b", "sunja"),
    (r"\btopusk\w*\b", "topusko"),
    (r"\bdvor\w*\b", "dvor"),
    (r"\bmajur\w*\b", "majur"),
    (r"\bgvozd\w*\b", "gvozd"),
    (r"\bsplit\w*\b", "split"),
    (r"\bosijek\w*\b", "osijek"),
    (r"\bzagreb\w*\b", "zagreb"),
    (r"\bkarlovc\w*\b|\bkarlovac\b", "karlovac"),
    (r"\bgunj\w*\b", "gunja"),
    (r"\brijec\w*\b|\brijek\w*\b", "rijeka"),
    (r"\bzadr\w*\b|\bzadar\b", "zadar"),
]


def _extract_region(text_lower: str) -> str | None:
    for pattern, canonical in _REGION_PATTERNS:
        if re.search(pattern, text_lower):
            return canonical
    return None


def _normalize_compared_location(raw: str) -> str:
    """Turn inflected Croatian street + city phrases into 'Nominative Street, City'."""
    s = raw.strip().rstrip(".?,!")
    s = re.sub(r"^(za|između|adresu|lokaciju)\s+", "", s, flags=re.IGNORECASE)
    s = s.replace("Владимира", "Vladimira")

    # Normalize common Croatian street case inflections (accusative/instrumental -> nominative)
    s = re.sub(r"\bUlicu\b", "Ulica", s)
    s = re.sub(r"\bulicom\b", "ulica", s)
    s = re.sub(r"\bCestu\b", "Cesta", s)
    s = re.sub(r"\bcestu\b", "cesta", s)
    s = re.sub(r"\bcestom\b", "cesta", s)
    s = re.sub(r"\bObalu\b", "Obala", s)
    s = re.sub(r"\b(\w+)sku\s+cesta\b", r"\1ska cesta", s)
    s = re.sub(r"\b(\w+)skom\s+ulica\b", r"\1ska ulica", s)
    s = re.sub(r"\b(\w+)evu\b", r"\1eva", s)

    m = re.search(r"^(.*?)\s+u\s+([A-ZČĆŽŠĐa-zčćžšđ\s]+)$", s)
    if m:
        street = m.group(1).strip()
        city_raw = m.group(2).strip().lower()
        city_canon = _extract_region(city_raw) or city_raw
        city_title = " ".join(w.capitalize() for w in city_canon.split())
        return f"{street}, {city_title}"
    return s


def fallback_parse_nl_query(text: str) -> ParsedQuery:
    """Deterministic Croatian parser used when Ollama is offline or unreachable."""
    t = text.strip()
    tl = t.lower()

    # 1. Check for compare_locations intent
    if "usporedi" in tl or "usporedbu" in tl or "usporedba" in tl:
        cleaned = re.sub(
            r"^(napravi\s+usporedbu\s+rizika\s+za|usporedi\s+rizike\s+za|usporedi)\s+",
            "",
            t,
            flags=re.IGNORECASE,
        ).rstrip(".?,!")
        parts = re.split(r"\s+(?:s|sa|i)\s+(?=[A-ZČĆŽŠĐ])", cleaned, maxsplit=1)
        locations = [_normalize_compared_location(p) for p in parts if p.strip()][:2]
        return ParsedQuery(
            intent=Intent.COMPARE_LOCATIONS,
            region=None,
            filters=[],
            locations=locations,
            layer=None,
            unsupported=[],
        )

    region = _extract_region(tl)

    # 2. Check for show_layer intent
    if any(kw in tl for kw in ("uključi", "prikaži sloj", "pokaži mi na karti", "pokaži kartu", "prikaži kartu", "uključi sloj", "sloj ")):
        layer = None
        if "likvefakc" in tl:
            layer = "liquefaction"
        elif "hrvatskih voda" in tl or "službeni sloj opasnosti od poplava" in tl:
            layer = "flood_hv"
        elif "efas" in tl:
            layer = "flood_efas"
        elif "klizišt" in tl:
            layer = "landslide"
        elif "vrtač" in tl:
            layer = "sinkhole"
        elif "nepovoljn" in tl:
            layer = "unfavourable"
        elif "podzemn" in tl:
            layer = "groundwater"
        elif "potres" in tl or "seizm" in tl:
            layer = "seismic"
        elif "poplav" in tl:
            layer = "flood_hv"
        if layer is not None:
            return ParsedQuery(
                intent=Intent.SHOW_LAYER,
                region=region,
                filters=[],
                locations=[],
                layer=layer,
                unsupported=[],
            )

    # 3. Default: find_area intent -> extract filters in order of appearance in text
    filter_hits: list[tuple[int, HazardFilter]] = []

    # Flood
    m_flood = re.search(r"poplav\w*", tl)
    if m_flood:
        if "srednj" in tl and re.search(r"poplav\w*[^.,;]*srednj|srednj\w*[^.,;]*poplav", tl):
            lvl = "srednje"
        elif re.search(r"nisk\w*\s+rizik\w*\s+od\s+poplav|nisk\w*\s+opasnost\w*\s+od\s+poplav", tl):
            lvl = "nisko"
        else:
            lvl = "nema_prema_karti"
        filter_hits.append((m_flood.start(), HazardFilter(hazard="flood", max_level=lvl)))

    # Unfavourable for building
    m_unf = re.search(r"(?:ne)?povoljn\w*\s+za\s+gradnj\w*", tl)
    if m_unf:
        filter_hits.append((m_unf.start(), HazardFilter(hazard="unfavourable", max_level="nema_prema_karti")))

    # Landslide
    m_land = re.search(r"klizišt\w*", tl)
    if m_land:
        lvl = "srednje" if re.search(r"srednj\w*[^.,;]*klizišt", tl) else "nisko"
        filter_hits.append((m_land.start(), HazardFilter(hazard="landslide", max_level=lvl)))

    # Liquefaction
    m_liq = re.search(r"likvefakcij\w*", tl)
    if m_liq:
        lvl = "srednje" if re.search(r"srednj\w*[^.,;]*likvefakcij", tl) else "nisko"
        filter_hits.append((m_liq.start(), HazardFilter(hazard="liquefaction", max_level=lvl)))

    # Sinkhole
    m_sink = re.search(r"vrtač\w*", tl)
    if m_sink:
        lvl = "srednje" if re.search(r"srednj\w*[^.,;]*vrtač", tl) else "nisko"
        filter_hits.append((m_sink.start(), HazardFilter(hazard="sinkhole", max_level=lvl)))

    # Groundwater
    m_gw = re.search(r"podzemn\w+\s+vod\w*", tl)
    if m_gw:
        filter_hits.append((m_gw.start(), HazardFilter(hazard="groundwater", max_level="nisko")))

    # Seismic
    m_seis = re.search(r"seizmičnost\w*|potres\w*", tl)
    if m_seis:
        if "vrlo nisk" in tl:
            lvl = "vrlo_niska_seizmicnost"
        else:
            lvl = "niska_seizmicnost"
        filter_hits.append((m_seis.start(), HazardFilter(hazard="seismic", max_level=lvl)))

    filter_hits.sort(key=lambda pair: pair[0])
    filters = [f for _, f in filter_hits]

    # Unsupported criteria extraction
    unsupported_hits: list[tuple[int, str]] = []
    unsupported_patterns = [
        (r"cijen\w*|kvadrat\w*|eur\w*", "cijene nekretnina"),
        (r"\bbuk\w*", "buka"),
        (r"požar\w*", "požari"),
        (r"kvalitet\w*\s+zrak\w*|\bzrak\w*", "kvaliteta zraka"),
        (r"osnovn\w*\s+škol\w*|\bškol\w*", "udaljenost od osnovne škole"),
        (r"nagib\w*\s+teren\w*", "nagib terena"),
    ]
    for pat, label in unsupported_patterns:
        m_u = re.search(pat, tl)
        if m_u:
            unsupported_hits.append((m_u.start(), label))
    unsupported_hits.sort(key=lambda pair: pair[0])
    unsupported = [lbl for _, lbl in unsupported_hits]

    return ParsedQuery(
        intent=Intent.FIND_AREA,
        region=region,
        filters=filters,
        locations=[],
        layer=None,
        unsupported=unsupported,
    )


def sanitize_report_for_llm(report_data: dict) -> dict:
    """Keep only deterministic hazard facts, sources, notes, summary, and recommended actions (no coordinates/PII)."""
    hazards_clean = []
    for h in report_data.get("hazards", []):
        if not isinstance(h, dict):
            continue
        hazards_clean.append({
            "hazard": h.get("hazard"),
            "hazard_name_hr": HAZARD_NAMES.get(h.get("hazard", ""), h.get("hazard")),
            "level": h.get("level"),
            "level_label_hr": LEVEL_LABELS.get(
                Level(h["level"]) if h.get("level") in Level._value2member_map_ else Level.NO_DATA,
                h.get("level"),
            ),
            "explanation": h.get("explanation"),
            "detail": h.get("detail", {}),
            "notes": h.get("notes", []),
            "source": h.get("source", {}),
        })

    top = report_data.get("most_significant")
    top_clean = None
    if isinstance(top, dict):
        top_clean = {
            "hazard": top.get("hazard"),
            "hazard_name_hr": HAZARD_NAMES.get(top.get("hazard", ""), top.get("hazard")),
            "level": top.get("level"),
            "explanation": top.get("explanation"),
        }

    return {
        "summary": report_data.get("summary", ""),
        "most_significant": top_clean,
        "all_no_data": bool(report_data.get("all_no_data", False)),
        "hazards": hazards_clean,
        "recommended_actions": report_data.get("recommended_actions", []),
        "disclaimer": report_data.get("disclaimer", ""),
    }


def fallback_explain_report(report_data: dict) -> str:
    """Deterministic structured Croatian explanation derived strictly from the report JSON when Ollama is offline."""
    clean = sanitize_report_for_llm(report_data)
    parts: list[str] = []

    if clean["summary"]:
        parts.append(clean["summary"])

    available = [h for h in clean["hazards"] if h.get("level") != "nema_podataka"]
    no_data = [h for h in clean["hazards"] if h.get("level") == "nema_podataka"]

    if available:
        bullet_lines = []
        for h in available:
            name = h.get("hazard_name_hr") or h.get("hazard")
            exp = h.get("explanation") or ""
            src = h.get("source", {})
            src_str = f" (Izvor: {src.get('title')}, {src.get('publisher')})" if src.get("title") else ""
            bullet_lines.append(f"• {name.capitalize()}: {exp}{src_str}")
        parts.append("Pregled obrađenih opasnosti:\n" + "\n".join(bullet_lines))

    if no_data:
        names = ", ".join(h.get("hazard_name_hr") or str(h.get("hazard")) for h in no_data)
        parts.append(
            f"Opasnosti bez dostupnih podataka na ovoj lokaciji ({names}): „nema podataka” ne znači da opasnost ne "
            "postoji, nego da javni izvor ne pokriva ovu točku (npr. studija geohazarda MPGI-ja pokriva samo Banovinu)."
        )

    actions = clean.get("recommended_actions", [])
    if actions:
        act_titles = "; ".join(f"{a.get('title')} ({a.get('institution')})" for a in actions if isinstance(a, dict))
        parts.append(f"Preporučeni koraci: {act_titles}.")

    return "\n\n".join(p for p in parts if p)


def fallback_answer_report_question(question: str, report_data: dict) -> str:
    """Deterministic Croatian Q&A responder grounded strictly in the report JSON when Ollama is offline."""
    clean = sanitize_report_for_llm(report_data)
    ql = question.strip().lower()
    hazards_by_key = {h["hazard"]: h for h in clean["hazards"] if isinstance(h, dict) and h.get("hazard")}

    # 1. Check out-of-scope topics explicitly
    out_of_scope = [
        (["cijen", "kvadrat", "vrijednost", "kupoprodaj"], "cijenama nekretnina"),
        (["požar", "vatr"], "šumskim ili otvorenim požarima"),
        (["buk", "promet"], "buci"),
        (["zrak", "onečišćenj", "smog"], "kvaliteti zraka"),
        (["dozvol", "legalizacij", "uporabn"], "građevinskim ili uporabnim dozvolama"),
    ]
    for keywords, topic in out_of_scope:
        if any(k in ql for k in keywords):
            return (
                f"Ovaj izvještaj ne sadrži podatke o {topic} jer ti podaci nisu dio korištenog kataloga "
                "otvorenih podataka o prirodnim opasnostima. Izvještaj obuhvaća samo poplave, potresnu opasnost "
                "i geološke opasnosti (klizišta, likvefakciju, vrtače, nepovoljne uvjete za gradnju i podzemnu vodu). "
                "Za provjeru čestice i uvjeta gradnje obratite se nadležnim institucijama (Uređena zemlja / ISPU)."
            )

    # 2. Check specific hazard questions
    hazard_keywords = [
        ("flood", ["poplav", "vod", "rijek", "efas", "hrvatske vode"]),
        ("seismic", ["potres", "seizm", "eurokod", "eshm", "ubrzanj", "ag"]),
        ("landslide", ["klizišt", "padin", "odron"]),
        ("liquefaction", ["likvefakc", "pijesak", "nosivost"]),
        ("sinkhole", ["vrtač", "ponikv", "krš"]),
        ("unfavourable", ["nepovoljn", "gradnj"]),
        ("groundwater", ["podzemn", "bušotin", "zdenac", "dubin"]),
    ]
    matched_hazards = []
    for hkey, kw_list in hazard_keywords:
        if any(kw in ql for kw in kw_list) and hkey in hazards_by_key:
            matched_hazards.append(hazards_by_key[hkey])

    if matched_hazards:
        lines = []
        for h in matched_hazards:
            src = h.get("source", {})
            notes_txt = " ".join(h.get("notes", []))
            src_note = src.get("note") or ""
            src_info = f"Izvor: {src.get('title', 'nepoznat')} ({src.get('publisher', '')}, {src.get('year', '')})."
            extra = " ".join(x for x in [notes_txt, src_note] if x)
            lines.append(
                f"{h['hazard_name_hr'].capitalize()} — razina: {h['level_label_hr']}. "
                f"{h.get('explanation', '')} {extra} {src_info}".strip()
            )
        return "\n\n".join(lines)

    # 3. Questions about recommended steps / actions
    if any(kw in ql for kw in ["korac", "preporuk", "što dalje", "sto dalje", "institucij", "kome se obratiti", "savjet"]):
        actions = clean.get("recommended_actions", [])
        if not actions:
            return "U izvještaju nisu navedeni posebni dodatni koraci."
        items = [f"• {a.get('title')}: {a.get('description')} ({a.get('institution')} — {a.get('url')})" for a in actions]
        return "Preporučeni koraci prema izvještaju:\n" + "\n".join(items)

    # 4. Questions about missing data ("nema podataka")
    if any(kw in ql for kw in ["nema podataka", "nedostupn", "zašto nema", "zasto nema", "banovin"]):
        no_data = [h for h in clean["hazards"] if h.get("level") == "nema_podataka"]
        if not no_data:
            return "Za odabranu lokaciju svi promatrani slojevi imaju dostupne podatke u izvještaju."
        names = ", ".join(h["hazard_name_hr"] for h in no_data)
        return (
            f"U ovom izvještaju oznaku „nema podataka” imaju: {names}. "
            "Oznaka „nema podataka” znači da izvor ne pokriva odabranu točku (primjerice, detaljna studija "
            "geohazarda MPGI-ja iz 2021. pokriva isključivo područje Banovine) ili da servis privremeno nije odgovorio. "
            "To ne znači da opasnost na terenu ne postoji."
        )

    # 5. Questions about sources / reliability
    if any(kw in ql for kw in ["izvor", "odakle", "pouzdan", "točn", "ograničenj", "metodologij"]):
        src_lines = []
        for h in clean["hazards"]:
            src = h.get("source", {})
            if src.get("title"):
                note = f" Napomena: {src.get('note')}" if src.get("note") else ""
                src_lines.append(
                    f"• {h['hazard_name_hr'].capitalize()}: {src.get('title')} — {src.get('publisher')} "
                    f"({src.get('year')}, rezolucija: {src.get('resolution')}).{note}"
                )
        return "Izvori i ograničenja podataka u ovom izvještaju:\n" + "\n".join(src_lines)

    # 6. Default: top risk & summary
    return fallback_explain_report(report_data)


class OllamaClient:
    """Async client for local/server Ollama instance with strict JSON schema support and deterministic fallbacks."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("OLLAMA_URL") or DEFAULT_OLLAMA_URL).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else float(os.environ.get("OLLAMA_TIMEOUT", DEFAULT_OLLAMA_TIMEOUT))
        self._client: httpx.AsyncClient | None = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def parse_query(self, text: str) -> tuple[ParsedQuery, bool]:
        """Translate Croatian natural-language query into `ParsedQuery`.

        Returns `(parsed_query, llm_used)`. If Ollama is reachable and returns a valid
        schema-conforming JSON, `llm_used` is True; otherwise falls back to deterministic rules.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": NL_QUERY_SYSTEM_PROMPT},
                {"role": "user", "content": text.strip()},
            ],
            "format": QUERY_JSON_SCHEMA,
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            res = await self._get_client().post(f"{self.base_url}/api/chat", json=payload)
            res.raise_for_status()
            body = res.json()
            content = body.get("message", {}).get("content", "")
            parsed = ParsedQuery.model_validate_json(content)
            return parsed, True
        except Exception:
            return fallback_parse_nl_query(text), False

    async def explain_report(self, report_data: dict) -> dict:
        """Generate a plain-language Croatian explanation strictly from the deterministic report JSON."""
        clean = sanitize_report_for_llm(report_data)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": REPORT_EXPLAIN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Objasni sljedeći deterministički JSON izvještaj na jasnom hrvatskom jeziku, "
                        "koristeći isključivo podatke iz JSON-a:\n\n"
                        + json.dumps(clean, ensure_ascii=False, indent=2)
                    ),
                },
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            res = await self._get_client().post(f"{self.base_url}/api/chat", json=payload)
            res.raise_for_status()
            body = res.json()
            content = (body.get("message", {}).get("content") or "").strip()
            if not content:
                raise ValueError("Empty LLM response")
            return {
                "explanation": content,
                "llm_used": True,
                "model": self.model,
            }
        except Exception:
            return {
                "explanation": fallback_explain_report(report_data),
                "llm_used": False,
                "model": "predložak (Ollama nije dostupna)",
            }

    async def ask_report(self, question: str, report_data: dict) -> dict:
        """Answer a user's question in Croatian strictly grounded in the deterministic report JSON."""
        clean = sanitize_report_for_llm(report_data)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": REPORT_QA_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Deterministički JSON izvještaj za odabranu lokaciju:\n"
                        + json.dumps(clean, ensure_ascii=False, indent=2)
                        + "\n\nPitanje korisnika: "
                        + question.strip()
                    ),
                },
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            res = await self._get_client().post(f"{self.base_url}/api/chat", json=payload)
            res.raise_for_status()
            body = res.json()
            content = (body.get("message", {}).get("content") or "").strip()
            if not content:
                raise ValueError("Empty LLM response")
            return {
                "answer": content,
                "llm_used": True,
                "model": self.model,
            }
        except Exception:
            return {
                "answer": fallback_answer_report_question(question, report_data),
                "llm_used": False,
                "model": "predložak (Ollama nije dostupna)",
            }
