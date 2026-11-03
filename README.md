# Geo-rizik

Izvještaj o izloženosti lokacije poplavama, potresu i geološkim opasnostima iz otvorenih podataka javnog sektora. Projekt za **Datathon Portala otvorenih podataka 2026**, izazov B: Okoliš i održivi prostor.

> Status: rana faza (vertikalni prototip u izradi). Dokumentacija je u [`docs/`](docs/).

## Pokretanje (backend)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest            # deterministički testovi
uvicorn app.main:app --reload --no-access-log
# http://localhost:8000/api/report?lat=45.4375&lon=16.2739
# --no-access-log is required: adrese i točne koordinate su u URL-u i ne smiju završiti u logovima
```

## Priprema podataka

```bash
pip install httpx pyproj
python pipeline/fetch_geohazards.py                 # MPGI geohazardi -> data/geohazards/*.geojson
# preuzeti ručno (~84 MB): https://geoportal.dgu.hr/services/atom/INSPIRE_Addresses_(AD).zip -> data/raw/
python pipeline/build_address_index.py "data/raw/INSPIRE_Addresses_(AD).zip" --inspect   # prvo provjera strukture
python pipeline/build_address_index.py "data/raw/INSPIRE_Addresses_(AD).zip"             # -> data/addresses.sqlite
python pipeline/build_map_layers.py                  # slojevi za kartu -> data/map/ (nakon geohazarda i EFAS-a)
```

## Izvori podataka

Popis izvora s izdavačima, licencama i poveznicama je u [`backend/app/layers.yaml`](backend/app/layers.yaml) i [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md).

## Licenca

Kod: MIT ([`LICENSE`](LICENSE)). Podaci imaju vlastite licence, a izvedena mreža s EFAS vrijednostima objavljuje se pod ODbL 1.0 ([`data/LICENSE-DATA.md`](data/LICENSE-DATA.md)).

Izvještaj je informativan prikaz iz javnih podataka, nije stručno mišljenje ni službena potvrda.
