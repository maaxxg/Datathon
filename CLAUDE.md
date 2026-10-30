# CLAUDE.md — Geo-rizik

Web app that turns a Croatian address into a plain-language, verifiable report on exposure to floods, earthquakes and geological hazards, built from public-sector open data. Entry for **Datathon Portala otvorenih podataka 2026**, challenge B (Okoliš i održivi prostor). Team of 4 + mentor.

**Communicate with the user in Croatian.** Code, comments, identifiers and commit messages in English. All UI text in Croatian.

## Hard deadline and what is scored

- Submission: **9. 11. 2026. 24:00** by e-mail to open.data@mpudt.hr. Team target: send by 18:00. No video (≤ 3 min) → not scored.
- Score (max 60): feasibility 10, UI/UX 10, presentation/video 10; 5 each: use of open data, linking data, relevance, impact, innovation, technical architecture/integration. Tie-break: feasibility, then open-data use.
- **Half the points are a working prototype, UX and video.** A small finished product beats a broad concept. When in doubt, cut scope.
- Rules (Pravila, III and VIII): must use public-sector open data, data.gov.hr preferred; other public sources (EU/national/local portals, public-sector APIs) allowed if the licence permits. Every dataset, publisher and link must be listed. Open-source software; all tools and libraries **including AI tools** must be listed. Solution must be the team's original work.

## Documents (read the relevant ones before non-trivial work)

| File | Purpose |
|---|---|
| `docs/SPEC.md` | Approved scope: MUST / SHOULD / COULD, risk rules (section 6), out of scope |
| `docs/ARCHITECTURE.md` | Components, data flow, interoperability, risks |
| `docs/PLAN.md` | Day-by-day plan to 9. 11. with checkpoints and owners |
| `docs/DECISIONS.md` | Decision log D1… (append new rows; never rewrite old ones) |
| `docs/DATA_INVENTORY.md` | Verified facts about every data source (GO / NO-GO / RIZIK) |
| `docs/SUBMISSION_CHECKLIST.md` | Submission contents, e-mail template, video script |
| `backend/app/layers.yaml` | **Single source of truth** for data sources: publisher, licence, URL, coverage, resolution |

`SPEC.md` is approved. Anything outside it needs the user's explicit OK and a new row in `DECISIONS.md`.

## Repository layout

```
backend/app/        FastAPI app: main.py, risk_rules.py, hv_flood.py, geohazards.py, layers.yaml
backend/tests/      pytest (deterministic part: rules, spatial lookups, decoders)
pipeline/           one-off data preparation scripts (download, clip, index)
scripts/            source verification (check_sources.py)
frontend/           SvelteKit + MapLibre GL (to be scaffolded)
data/               generated/downloaded data (git-ignored) + LICENSE-DATA.md
docs/               project documentation (see above)
misc/coding-team/   Task Briefs for the agent workflow
.claude/agents/     subagent definitions
```

## Commands

```bash
cd backend && python -m pytest -q                       # must pass before any review
cd backend && uvicorn app.main:app --reload             # API on :8000
python pipeline/fetch_geohazards.py                     # -> data/geohazards/*.geojson
python pipeline/build_address_index.py <zip> --inspect  # inspect DGU GML before building
python scripts/check_sources.py                         # re-verify live sources
```

## Non-negotiable conventions

1. **Risk levels are deterministic.** Computed only in `risk_rules.py` from the table in SPEC section 6. The LLM never computes, adjusts or invents a level, depth, class or source. Every rule change gets a test.
2. **"No hazard" ≠ "no data".** `Level.NONE` = source covers the point and shows nothing; `Level.NO_DATA` = not covered, service failed, or not integrated. Never collapse these.
3. **Every displayed datum carries its source** (title, publisher, year, resolution, link), taken from `layers.yaml`. Adding a source = adding it to `layers.yaml` first, with a verified licence.
4. **No overall risk score.** Per-hazard levels plus "most significant", per D4.
5. **Earthquake classes follow Eurocode 8** (D13): ≤ 0.04 g very low, ≤ 0.08 g low, > 0.08 g above the low-seismicity threshold, with the exact value. No invented "high" threshold.
6. **Privacy:** never store or log addresses or exact user coordinates. Caches are keyed by fixed tiles/grid cells. No third-party analytics.
7. **Never fabricate data or results.** If something was not run or verified, say "nije provjereno" and why. Do not claim something works until you ran it.
8. **App must work without the LLM** (template text, manual filters). LLM is an open model via Ollama with JSON-schema constrained output (D9).
9. Disclaimer on every report: informative view from public data, not an expert opinion or official certificate.
10. **YAGNI.** Ten days. No speculative abstraction, no PostGIS (D6), no user accounts, no features outside SPEC.
11. Accessibility: WCAG AA contrast; levels shown by text + icon, never colour alone; mobile-first.

## Data facts and gotchas (verified 30. 10. 2026.; details in DATA_INVENTORY)

- **HV flood hazard maps 2019** (`servisi.voda.hr/wms`, layers `poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-{velika,srednja,mala}-vjerojatnost_2019`) are rasters with `queryable=0` → GetFeatureInfo fails. We read the pixel from a GetMap tile. Legend colours: `#BEE8FF` <0.5 m, `#73DFFF` 0.5–1.5 m, `#73B2FF` 1.5–2.5 m, `#7A8EF5` >2.5 m, `#004DA8` permanent water. Layers do **not render at small scales**: keep tiles small (0.01°). HV risk-map layers return empty GFI → not used. HV flood datasets are **not on data.gov.hr** (only dev-data); state this honestly in docs.
- **WMS 1.3.0 + EPSG:4326 uses lat,lon axis order** in BBOX. WFS 2.0 bbox with `urn:ogc:def:crs:EPSG::4326` also lat,lon. Always test a known point after any CRS change.
- **MPGI geohazards** (WFS `gis{1..4}.mgipu.hr/srv1/RGN_MGIPU_Public/wfs`): gis1 returned 502, gis2 worked; try hosts in order. Coverage is **Banovina only** (lon 15.73–16.92, lat 44.96–45.68), not all of Croatia despite NIPP metadata. Susceptibility layers have 2–3 big multipolygons with attribute `podloznost` (niska/srednja/visoka); one request can take ~24 s → download once, query locally. A bbox query returns all intersecting polygons; use point-in-polygon.
- **DGU cadastre WFS** works but ~18 s per bbox query → never on the request path without cache.
- **DGU addresses**: ATOM zip ~84 MB, GML 3.2.1 in ETRS89/LAEA (EPSG:3035); names are separate features linked by xlink. Parser not yet run on the real file.
- **DGU elevation**: GeoTIFF tiles via ATOM (ETRS89/TM33); resolution not verified.
- **EFAS** flood hazard v3.1.1 (JRC): GeoTIFF, 90 m, WGS84, **ODbL** → derived H3 grid must be published under ODbL (D14). Used only where HV has no data.
- National CRS: HTRS96/TM = EPSG:3765.
- `http://` services (AZO noise/air quality) fail from browsers due to mixed content; verify with scripts, not the browser.

## Agent workflow

Subagents live in `.claude/agents/`:

- **@architect**: plans a task, writes the Task Brief to `misc/coding-team/<topic>/NNN-title.md`, drives the loop, evaluates against acceptance criteria. Never implements.
- **@developer**: implements exactly one Task Brief, runs tests, requests parallel review.
- **@data-validator**: reviews data plumbing (CRS, axis order, coverage, classes, licences, lineage). Read-only.
- **@reviewer**: reviews correctness of rules, API, LLM boundary, privacy, UX/a11y and tests. Read-only.

Use @architect for anything bigger than a small tweak. Small fixes (typo, one-line bug, copy change) can be done directly. Signoff from the user is the word **"approved"** (or "odobreno").

## Current status

- 30. 10.: Phases 1–3 done (data feasibility, decisions, spec approved). Repo scaffolded; risk rules, HV flood sampler, geohazard lookup and `/api/report` implemented with 31 passing tests (HV mocked in tests).
- Next checkpoint: **1. 11. vertical prototype**, Petrinja address → report end-to-end.
- Open: earthquake source (official Croatian map vs ESHM20, decide by 1. 11.), app name.

Update this section when a checkpoint from `PLAN.md` is reached or missed.
