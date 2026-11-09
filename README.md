# Geo-rizik

## 1. Opis

Geo-rizik pretvara hrvatsku adresu ili odabranu točku na karti u razumljiv, provjerljiv izvještaj o izloženosti lokacije poplavama, potresu i geološkim opasnostima (klizišta, likvefakcija, vrtače, nepovoljni uvjeti za gradnju, podzemna voda), te omogućuje pretragu područja prirodnim jezikom na višerezolucijskoj **Uber H3** šesterokutnoj mreži. Sve je izgrađeno od otvorenih podataka javnog sektora i europskih znanstvenih servisa; svaki prikazani podatak navodi izvor, godinu, rezoluciju i licencu.

Razine opasnosti računaju se **isključivo determinističkim pravilima** (`backend/app/risk_rules.py`, javna tablica na stranici „Izvori i metodologija”), nikada umjetnom inteligencijom. Lokalni jezični model (**Ollama** / `qwen2.5:1.5b`) koristi se samo za prevođenje upita prirodnim jezikom u strogu JSON shemu filtera te za sažeto objašnjenje i odgovore na pitanja isključivo iz već izračunatog determinističkog JSON izvještaja — uz ugrađene determinističke hrvatske predloške i parser koji osiguravaju puni rad aplikacije i kad Ollama nije dostupna. Izvještaj je prilagođen i za izravan **A4 ispis / PDF**. Projekt je izrađen za **Datathon Portala otvorenih podataka 2026**, izazov B: Okoliš i održivi prostor.

Primjer scenarija: korisnik upiše „Petrinja”, odabere adresu (ili klikne na kartu) i dobije izvještaj za točku 45,4375 N, 16,2739 E s najznačajnijim utvrđenim rizikom, razinom po svakoj opasnosti, izvorom, ograničenjima podatka, preporučenim koracima prema nadležnim institucijama i mogućnošću postavljanja pitanja o izvještaju ili pretrage okolnih zona na H3 mreži.

> Izvještaj je informativan prikaz iz javnih podataka. Nije stručno mišljenje ni službena potvrda.

## 2. Arhitektura

- **Frontend:** SvelteKit (statička SPA) + MapLibre GL (`/` — tražilica adresa s automatskim dovršavanjem, interaktivna karta s uključivim slojevima i dinamičkom višerezolucijskom H3 mrežom ovisno o zumu, pretraga područja prirodnim jezikom i ručnim filterima, kartice izvještaja sa sažetim prikazom nedostupnih podataka, AI objašnjenje i pitanja o izvještaju, A4 ispis/PDF; `/izvori` — katalog izvora, javna tablica pravila, privatnost i licence). Pozadina karte čita se s OpenStreetMapa, a sloj poplava izravno s WMS servisa Hrvatskih voda.
- **Backend:** FastAPI (`backend/app`); deterministička pravila razina u `risk_rules.py`; katalog izvora u `backend/app/layers.yaml`; JSON shema upita i validacija prema katalogu u `query_schema.py`; višerezolucijska Uber H3 mreža (rezolucije 5–10 usidrene na kopnene adrese iz DGU registra) u `h3_grid.py`; Ollama klijent i determinističke hrvatske rezerve u `llm.py` i `templates.py`.
- **Podaci:** lokalne datoteke u `data/` (MPGI geohazardi, Copernicus EFAS, EFEHR ESHM20, SQLite FTS5 indeks DGU adresa, pojednostavljeni prikazni slojevi karte u `data/map/`); karte opasnosti Hrvatskih voda čitaju se uživo preko WMS `GetMap` upita s keširanjem (uz EFAS kao automatsku rezervu i izričitu napomenu pri privremenom ispadu servisa Hrvatskih voda).
- **Pipeline:** skripte u `pipeline/` i `scripts/prepare_data.sh` pripremaju `data/` (preuzimanje, indeksiranje, generiranje slojeva za kartu).
- **Deploy:** Docker Compose, Caddy ispred (`/api/*` → FastAPI, ostalo statički frontend), uz povezivanje na Ollama servis na host poslužitelju (`host.docker.internal:11434`).

Detalji: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/SPEC.md`](docs/SPEC.md). Odluke: [`docs/DECISIONS.md`](docs/DECISIONS.md).

## 3. Lokalno pokretanje

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --reload --no-access-log
# http://localhost:8000/api/health  (start traje 10-20 s kad su geohazardi učitani)
# http://localhost:8000/api/report?lat=45.4375&lon=16.2739
```

`--no-access-log` je obavezan: adrese i točne koordinate nalaze se u URL-u i ne smiju završiti u logovima.

Opcijski lokalni LLM (Ollama):
- Postavke se čitaju iz varijabli okruženja `OLLAMA_URL` (zadano `http://localhost:11434`), `OLLAMA_MODEL` (na produkcijskom poslužitelju `qwen2.5:1.5b`, lokalno zadano `qwen2.5:3b`) i `OLLAMA_TIMEOUT` (zadano `60`).
- Ako Ollama nije pokrenuta ili model nije dostupan, sve rute (`/api/query`, `/api/report/explain`, `/api/report/ask`) automatski koriste deterministički hrvatski parser i predloške bez prekida rada.

Glavne API rute:
- `GET /api/health` — status učitanih slojeva (`geohazards_loaded`, `addresses_loaded`, `seismic_loaded`, `efas_loaded`, `map_layers_loaded`) i naziv konfiguriranog LLM modela (`llm_model`).
- `GET /api/sources` — strojno čitljivi katalog svih izvora podataka iz `layers.yaml`.
- `GET /api/addresses?q=...` — lokalni FTS5 geokoder nad DGU Adresama INSPIRE.
- `GET /api/report?lat=...&lon=...` — deterministički izvještaj o opasnostima za točku u Hrvatskoj.
- `POST /api/query` i `POST /api/query/validate` — prevođenje upita prirodnim jezikom u JSON shemu, validacija prema katalogu i izračun višerezolucijske Uber H3 mreže.
- `POST /api/report/explain` i `POST /api/report/ask` — sažeto objašnjenje i odgovori na pitanja isključivo iz JSON-a izvještaja.

Frontend (Node 20):

```bash
cd frontend
npm ci
npm run dev        # Vite proxy šalje /api na localhost:8000
npm run build      # statički build u frontend/build
```

Bez datoteka u `data/` aplikacija se pokreće, ali su odgovarajući slojevi „nema podataka” (stanje se vidi na `/api/health`).

## 4. Priprema podataka

`data/` nije u gitu. Jedna skripta priprema sve (preskače korake čiji izlaz već postoji; `--force` ponavlja):

```bash
scripts/prepare_data.sh [--data DIR] [--force]    # DIR: zadano $GEORIZIK_DATA ili ./data
```

Koristi `backend/.venv/bin/python` ako postoji (inače `python3`, ili `$PYTHON`). Koraci i izmjerene/poznate veličine:

| Korak | Izlaz | Veličina / trajanje |
|---|---|---|
| `fetch_geohazards.py` (MPGI, Banovina) | `data/geohazards/*.geojson` | ~186 MB (`landslide.geojson` ~182 MB) |
| `fetch_seismic.py` (ESHM20) | `data/seismic/eshm20_pga475.json` | ~122 KB, ~4 s |
| `fetch_efas.py` (EFAS) | `data/efas/rp{10,100,500}.tif` | ~22 MB |
| preuzimanje DGU zipa (URL iz `layers.yaml`) + `build_address_index.py` | `data/raw/INSPIRE_Addresses_(AD).zip`, `data/addresses.sqlite` | zip ~86 MB, indeks ~170 MB; izgradnja indeksa ~2,5 min (1 683 411 adresa) |
| `build_map_layers.py` (poslije geohazarda i EFAS-a) | `data/map/` | ~4,5 MB, ~25 s |

Ponovno pokretanje s već postojećim podacima preskače sve korake (manje od 1 s) i ispisuje sažetak OK/MISSING. Skriptu pokrenite na hostu (u kontejneru `api` je `data/` montiran samo za čitanje).

## 5. Docker Compose

Potrebno: Docker s Compose pluginom i pripremljen `data/` (korak 4).

```bash
cp .env.example .env           # DOMAIN= prazno -> https://localhost; OLLAMA_MODEL=qwen2.5:1.5b
docker compose up -d --build
scripts/wait_healthy.sh        # čeka da svi *_loaded budu true (najviše 120 s); BASE_URL=... za drugu adresu
```

- Dva kontejnera: `api` (FastAPI, uvicorn `--no-access-log`, `data/` montiran samo za čitanje, nije izložen izvana; pristupa Ollami na hostu preko `host.docker.internal:11434`) i `web` (Caddy + statički build, portovi 80/443).
- `DOMAIN` prazan: Caddy koristi svoj interni CA za `localhost`; preglednik će upozoriti na certifikat, a `curl` treba `-k`. Javna domena u `DOMAIN` (DNS na ovaj stroj, otvoreni portovi 80 i 443): certifikat (Let's Encrypt) dobiva se automatski.
- Privatnost: Caddy nema `log` direktivu (nema pristupnog loga), a globalni `log default { exclude http.log.error }` odbacuje i zapise grešaka proxyja (sadrže puni URI; odgovori 502 ne ostavljaju URI ni koordinate u logovima), uvicorn radi s `--no-access-log`, upiti prema WMS-u Hrvatskih voda zaokružuju se na fiksnu mrežu pločica od 0,02° (~2,2 km), a pri pozivu LLM-a iz JSON-a izvještaja uklanjaju se koordinate i adresa (`sanitize_report_for_llm`). Odgovor ima `Referrer-Policy: strict-origin-when-cross-origin` (OSM zahtijeva Referer; drugim stranicama šalje se samo domena ove stranice, nikad putanja ni koordinate).
- Ažuriranje: `git pull && docker compose up -d --build`; podaci u `data/` ostaju.

## 6. Izvori podataka i licence

Izvor istine je [`backend/app/layers.yaml`](backend/app/layers.yaml); tablica je generirana s `python scripts/sources_table.py`. Detalji provjere svakog izvora: [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md).

| Ključ | Naziv | Izdavač | Licenca | Poveznica |
|---|---|---|---|---|
| `flood_hv` | Karte opasnosti od poplava 2019. | Hrvatske vode | bez ograničenja pristupa (WMS AccessConstraints NONE); skup nije objavljen na data.gov.hr | https://servisi.voda.hr/wms |
| `flood_efas` | EFAS river flood hazard maps v3.1.1 | Europska komisija, JRC (Copernicus EMS) | ODbL 1.0 | https://jeodpp.jrc.ec.europa.eu/ftp/public/JRC-OpenData/CEMS-EFAS/flood_hazard/ |
| `seismic` | Europski model potresne opasnosti ESHM20 (PGA, 475 god.) | EFEHR / ETH Zürich (Danciu et al.) | CC BY 4.0 | https://efehr-services.ethz.ch/hazard/api/v1 |
| `landslide` | Podložnost klizištima | Ministarstvo prostornoga uređenja, graditeljstva i državne imovine | Otvorena dozvola RH | https://data.gov.hr/ckan/hr/dataset/geohazardi |
| `liquefaction` | Podložnost likvefakciji | Ministarstvo prostornoga uređenja, graditeljstva i državne imovine | Otvorena dozvola RH | https://data.gov.hr/ckan/hr/dataset/geohazardi |
| `sinkhole` | Podložnost vrtačama | Ministarstvo prostornoga uređenja, graditeljstva i državne imovine | Otvorena dozvola RH | https://data.gov.hr/ckan/hr/dataset/geohazardi |
| `unfavourable` | Područja nepovoljna za gradnju | Ministarstvo prostornoga uređenja, graditeljstva i državne imovine | Otvorena dozvola RH | https://data.gov.hr/ckan/hr/dataset/geohazardi |
| `groundwater` | Dubina podzemne vode | Ministarstvo prostornoga uređenja, graditeljstva i državne imovine | Otvorena dozvola RH | https://data.gov.hr/ckan/hr/dataset/geohazardi |
| `addresses` | Adrese INSPIRE | Državna geodetska uprava | Otvorena dozvola RH | https://data.gov.hr/ckan/hr/dataset/adrese-inspire |

Napomene:

- **Karte opasnosti od poplava Hrvatskih voda nisu objavljene na data.gov.hr** (nalaze se samo na razvojnoj instanci dev-data.gov.hr); koristimo ih preko javnog WMS servisa Hrvatskih voda (`AccessConstraints: NONE`).
- **EFAS i ESHM20** europski su znanstveni izvori (nisu s data.gov.hr). Za EFAS JRC `copyright.txt` navodi CC BY 4.0, a README (odjeljak A02) navodi **ODbL 1.0**; primjenjujemo strožu licencu (**ODbL 1.0**). ESHM20 je pod **CC BY 4.0** (Danciu et al., 2021, DOI: `10.12686/a15`) i predstavlja okvirnu procjenu za referentnu stijenu ($V_{s30} = 760\text{ m/s}$).
- **Podloga karte:** © suradnici OpenStreetMapa (ODbL), pločice s `tile.openstreetmap.org` ([uvjeti korištenja](https://operations.osmfoundation.org/policies/tiles/)). Koristi se isključivo kao pozadina, ne kao izvor podataka o opasnostima. Preglednik pločice dohvaća izravno s OSM poslužitelja, pa oni vide IP adresu posjetitelja i prikazano područje.

## 7. Ograničenja

- **Obuhvat geohazarda:** Geohazardi MPGI-ja (klizišta, likvefakcija, vrtače, nepovoljno za gradnju, podzemna voda) pokrivaju **samo Banovinu** (Sisačko-moslavačku županiju); drugdje u Hrvatskoj izvještaj prikazuje „nema podataka”, a H3 pretraga upozorava da su ti slojevi izvan obuhvata.
- **Hrvatske vode (WMS):** Karte opasnosti su rasteri bez mogućnosti upita po točki (`GetFeatureInfo`), pa se razred dubine u izvještaju čita iz piksela prikazane slike (`GetMap`); sloj se na interaktivnoj karti iscrtava u rasponu zumiranja 12–14. Pri privremenom ispadu WMS servisa Hrvatskih voda koristi se rezerva iz EFAS-a uz izričitu napomenu o kojim se nedostupnim scenarijima radi (`D22`).
- **EFAS i H3 regionalna mreža:** EFAS ima rezoluciju 90 m i pokriva samo poplave uz veće rijeke. U pojedinačnom izvještaju služi kao rezerva kad Hrvatske vode nemaju podatak, dok se u regionalnoj H3 pretrazi područja (`POST /api/query`) koristi za brzu procjenu poplava na svim ćelijama mreže (jer WMS Hrvatskih voda ne dopušta masovno vektorsko uzorkovanje).
- **ESHM20 (potres):** Okvirna procjena s mrežom točaka ~10 km (najbliža točka bez interpolacije) za referentnu stijenu $V_{s30} = 760\text{ m/s}$; razredi su određeni prema normi HRN EN 1998-1 (Eurokod 8).
- **Podzemna voda:** Temelji se na jednom mjerenju iz veljače/ožujka 2021. po bušotini (602 bušotine u Banovini, radijus pretrage do 1 km); u izvještaju se uvijek prikazuju datum mjerenja i udaljenost do bušotine.
- **Pretraga prirodnim jezikom i lokalni LLM:** Lokalni model (`qwen2.5:1.5b`) može pri složenijim hrvatskim upitima pogriješiti u padežu, zbog čega orkestrator provodi determinističku normalizaciju regija, provjeru nepodržanih kriterija prema katalogu slojeva i omogućuje ručno uređivanje filtera. Kod namjere usporedbe lokacija (`compare_locations`) sustav izdvaja tražene lokacije kao gumbe za brzi prijelaz na izvještaj.
- Izvještaj nije stručno mišljenje ni službena potvrda.

## 8. Alati i biblioteke

- **Backend:** Python 3.12, FastAPI, Pydantic, uvicorn, httpx, Pillow, rasterio (GDAL), shapely, pyproj, `h3` (Uber H3 v4), PyYAML, pytest.
- **Frontend:** SvelteKit 2, Svelte 5, Vite, `@sveltejs/adapter-static`, MapLibre GL.
- **Deploy:** Docker, Docker Compose, Caddy 2.
- **Podloga karte:** OpenStreetMap (samo kao pozadina).
- **AI alati:**
  - **Na poslužitelju (izvršavanje upita i sažimanje):** **Ollama** (MIT) + otvoreni model **Qwen2.5-1.5B (`qwen2.5:1.5b`)** (Alibaba Cloud, licenca **Apache 2.0**). Koristi se samo za prevođenje prirodnog jezika u JSON shemu (`QUERY_JSON_SCHEMA`) i sažimanje determinističkog JSON izvještaja; ne računa razine rizika.
  - **Tijekom razvoja:** **Claude Code (Anthropic)** i **Gemini / Antigravity (Google DeepMind)** korišteni su kao pomoć pri razvoju (planiranje, pisanje i pregled koda, testova, sučelja i dokumentacije); sve je pregledao i odobrio tim.

## 9. Licenca

- **Izvorni kod:** **MIT** ([`LICENSE`](LICENSE)).
- **Podaci i izvedeni slojevi:** Svaki izvor podataka zadržava vlastitu licencu (vidi tablicu u odjeljku 6 i [`data/LICENSE-DATA.md`](data/LICENSE-DATA.md)): **Otvorena dozvola RH** (DGU Adrese INSPIRE, MPGI Geohazardi), **CC BY 4.0** (EFEHR ESHM20), javni WMS bez ograničenja pristupa (Hrvatske vode), te **ODbL 1.0** za Copernicus EFAS i sve izvedene podatke koji sadrže EFAS vrijednosti (`data/map/efas_rp*.png` i višerezolucijska H3 mreža).
- **Jezični model na poslužitelju:** Model **Qwen2.5-1.5B (`qwen2.5:1.5b`)** izvršava se putem sustava **Ollama** (MIT licenca) pod otvorenom licencom **Apache 2.0** (Alibaba Cloud).

