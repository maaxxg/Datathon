# Geo-rizik

## 1. Opis

Geo-rizik pretvara hrvatsku adresu u razumljiv, provjerljiv izvještaj o izloženosti lokacije poplavama, potresu i geološkim opasnostima (klizišta, likvefakcija, vrtače, podzemna voda). Sve je izgrađeno od otvorenih podataka javnog sektora; svaki prikazani podatak navodi izvor, a razine opasnosti računaju se determinističkim pravilima (tablica je na stranici „Izvori”), ne umjetnom inteligencijom. Projekt je za **Datathon Portala otvorenih podataka 2026**, izazov B: Okoliš i održivi prostor.

Primjer scenarija: korisnik upiše „Petrinja”, odabere adresu i dobije izvještaj za točku 45,4375 N, 16,2739 E s razinom po svakoj opasnosti, izvorom, godinom i ograničenjima podatka.

> Izvještaj je informativan prikaz iz javnih podataka. Nije stručno mišljenje ni službena potvrda.

## 2. Arhitektura

- **Frontend:** SvelteKit (statička SPA) + MapLibre GL; pozadina karte iz OpenStreetMapa, sloj poplava izravno s Hrvatskih voda.
- **Backend:** FastAPI (`backend/app`); razine samo u `risk_rules.py`; katalog izvora u `backend/app/layers.yaml`.
- **Podaci:** lokalne datoteke u `data/` (geohazardi, EFAS, ESHM20, SQLite indeks adresa); karte opasnosti Hrvatskih voda čitaju se uživo.
- **Pipeline:** skripte u `pipeline/` pripremaju `data/` (preuzimanje, indeksiranje).
- **Deploy:** Docker Compose, Caddy ispred (`/api/*` → FastAPI, ostalo statički frontend).

Detalji: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Odluke: [`docs/DECISIONS.md`](docs/DECISIONS.md).

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
| `fetch_geohazards.py` (MPGI, Banovina) | `data/geohazards/*.geojson` | ~186 MB (`landslide.geojson` ~182 MB); trajanje nije mjereno |
| `fetch_seismic.py` (ESHM20) | `data/seismic/eshm20_pga475.json` | ~122 KB, ~4 s |
| `fetch_efas.py` (EFAS) | `data/efas/rp{10,100,500}.tif` | ~22 MB |
| preuzimanje DGU zipa (URL iz `layers.yaml`) + `build_address_index.py` | `data/raw/INSPIRE_Addresses_(AD).zip`, `data/addresses.sqlite` | zip ~86 MB, indeks ~170 MB; izgradnja indeksa izmjerena 3. 11.: ~2,5 min (2:37; 1 683 411 adresa) |
| `build_map_layers.py` | `data/map/` | preskače se dok skripta nije na `main` |

Provjereno 3. 11.: ponovno pokretanje s već postojećim podacima preskače sve korake (manje od 1 s) i ispisuje sažetak OK/MISSING; izgradnja adresnog indeksa iz zip datoteke prošla je. Preuzimanje DGU zipa s mreže nije provjereno u ovoj skripti (korišten je već preuzeti zip). Skriptu pokrenite na hostu (u kontejneru `api` je `data/` montiran samo za čitanje).

## 5. Docker Compose

Potrebno: Docker s Compose pluginom i pripremljen `data/` (korak 4).

```bash
cp .env.example .env           # DOMAIN= prazno -> https://localhost
docker compose up -d --build
scripts/wait_healthy.sh        # čeka da svi *_loaded budu true (najviše 120 s); BASE_URL=... za drugu adresu
```

- Dva kontejnera: `api` (FastAPI, uvicorn `--no-access-log`, `data/` montiran samo za čitanje, nije izložen izvana) i `web` (Caddy + statički build, portovi 80/443).
- `DOMAIN` prazan: Caddy koristi svoj interni CA za `localhost`; preglednik će upozoriti na certifikat, a `curl` treba `-k`. Javna domena u `DOMAIN` (DNS na ovaj stroj, otvoreni portovi 80 i 443): certifikat se dobiva automatski.
- Privatnost: Caddy nema `log` direktivu (nema pristupnog loga), uvicorn radi s `--no-access-log`, odgovor ima `Referrer-Policy: strict-origin-when-cross-origin` (OSM zahtijeva Referer; drugim stranicama šalje se samo domena ove stranice, nikad putanja ni koordinate, jer aplikacija koordinate ne stavlja u URL).
- Ažuriranje: `git pull && docker compose up -d --build`; podaci u `data/` ostaju.

**Nije provjereno (Docker nije bio instaliran 3. 11.):** `docker compose up`, izgradnja slika, healthcheck, certifikat i ponašanje preglednika. Provjereni su samo statički build frontenda, sintaksa skripti i API pokrenut izravno s uvicornom na pripremljenim podacima.

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

- **Karte opasnosti od poplava Hrvatskih voda nisu objavljene na data.gov.hr** (nalaze se samo na razvojnoj instanci dev-data.gov.hr); koristimo ih preko javnog WMS servisa Hrvatskih voda.
- ESHM20 i EFAS europski su izvori (nisu s data.gov.hr); ESHM20 je okvirna procjena za referentnu stijenu (Vs30 = 760 m/s).
- **Podloga karte:** © suradnici OpenStreetMapa (ODbL), pločice s `tile.openstreetmap.org` ([uvjeti](https://operations.osmfoundation.org/policies/tiles/)). Koristi se samo kao pozadina, ne kao izvor podataka o opasnostima. Preglednik pločice dohvaća izravno s OSM poslužitelja, pa oni vide IP adresu posjetitelja i prikazano područje.

## 7. Ograničenja

- Geohazardi MPGI (klizišta, likvefakcija, vrtače, nepovoljno za gradnju, podzemna voda) pokrivaju **samo Banovinu**; drugdje je „nema podataka”.
- Hrvatske vode: karte su rasteri bez upita po točki, pa se razred dubine čita iz prikazane slike (GetMap); sloj se na karti prikazuje samo u rasponu zumiranja 12-14.
- EFAS (rezerva tamo gdje Hrvatske vode nemaju podatka): rezolucija 90 m, europski model, pokriva samo veće rijeke.
- ESHM20: okvirno, mreža ~10 km (najbliža točka), referentna stijena Vs30 = 760 m/s; razredi prema Eurokodu 8.
- Podzemna voda: jedno mjerenje iz 2021. po bušotini; prikazuju se datum i udaljenost.
- Podloga karte učitava se s OSM poslužitelja (vidi privatnost gore). LLM/pretraga prirodnim jezikom nije dio ovog izdanja.
- Nije stručno mišljenje ni službena potvrda.

## 8. Alati i biblioteke

- **Backend:** Python, FastAPI, uvicorn, httpx, Pillow, rasterio (GDAL), shapely, pyproj, PyYAML, pytest.
- **Frontend:** SvelteKit, Svelte, Vite, `@sveltejs/adapter-static`, MapLibre GL.
- **Deploy:** Docker, Docker Compose, Caddy.
- **Podloga karte:** OpenStreetMap (samo kao pozadina).
- **AI alati:** **Claude Code (Anthropic)** korišten je kao pomoć pri razvoju (planiranje, pisanje i pregled koda, testova i dokumentacije); sve je pregledao i odobrio tim. Rezultati u aplikaciji ne dolaze iz umjetne inteligencije. Ollama/otvoreni LLM nije dio ovog izdanja.

## 9. Licenca

Kod: MIT ([`LICENSE`](LICENSE)). Podaci imaju vlastite licence (vidi tablicu iznad); izvedeni podaci s EFAS vrijednostima objavljuju se pod ODbL 1.0 ([`data/LICENSE-DATA.md`](data/LICENSE-DATA.md)).
