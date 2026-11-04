# Validacija na 10 poznatih lokacija u Hrvatskoj (PLAN 2. 11. — D)

Datum provjere: **2. 11. 2026.**  
Skripta za ponavljanje provjere: [`scripts/validate_known_points.py`](../scripts/validate_known_points.py)  
Regresijski testovi: [`backend/tests/test_known_points.py`](../backend/tests/test_known_points.py)

## 1. Ključni nalaz pri validaciji (popravak mjerila HV WMS-a, D19)

Pri izvođenju provjere na 10 referentnih točaka utvrđeno je da kombinacija `TILE_DEG = 0.01` i `TILE_PX = 512` u `backend/app/hv_flood.py` daje OGC WMS mjerilo ~1:7 700, što je ispod praga `MinScaleDenominator` na GeoServeru Hrvatskih voda te vraća prazan (proziran) PNG za sve točke u Hrvatskoj.

Promjenom na **`TILE_DEG = 0.02` (~2,2 km)** i **`TILE_PX = 256` (~8,5 m/px, mjerilo ~1:31 000)** sloj se ispravno iscrtava i točno reproducira referentne vrijednosti iz `DATA_INVENTORY.md` (npr. Karlovac `mala = 1,5–2,5 m`, Zagreb uz Savu `mala = 0,5–1,5 m`).

## 2. Rezultati po referentnim točkama

| # | Lokacija | WGS84 (`lat, lon`) | Obuhvat Banovine | Poplava HV (`velika / srednja / mala`) | EFAS (`RP10 / RP100 / RP500` m) | Potres ESHM20 ($a_g$, 475 god.) | Geohazardi (MPGI) | Najznačajniji rizik |
|---|---|---|---|---|---|---|---|---|
| 1 | **Petrinja — središte** | `45.4375, 16.2739` | Da | `outside / outside / 1,5–2,5 m` (`nisko`) | `0 / 0 / 0` | `0,1145 g` (`iznad praga niske`) | likvefakcija: **visoka**, podzemna voda: `1,96 m` (70 m) | **Likvefakcija (`visoko`)** |
| 2 | **Petrinja — Matije Gupca 12** | `45.4410, 16.2718` | Da | `outside / outside / outside` (`nema prema karti`) | `0 / 0 / 0` | `0,1145 g` (`iznad praga niske`) | likvefakcija: **visoka** | **Likvefakcija (`visoko`)** |
| 3 | **Sisak — Rimska ulica 19** | `45.4896, 16.3713` | Da | `outside / outside / outside` (`nema prema karti`) | `0 / 0 / 0` | `0,1086 g` (`iznad praga niske`) | likvefakcija: **visoka** | **Likvefakcija (`visoko`)** |
| 4 | **Glina — središte** | `45.3381, 16.0886` | Da | `outside / outside / < 0,5 m` (`nisko`) | `0 / 0 / 0` | `0,1159 g` (`iznad praga niske`) | likvefakcija: **visoka** | **Likvefakcija (`visoko`)** |
| 5 | **Hrvatska Kostajnica (uz Unu)** | `45.2292, 16.5392` | Da | `outside / outside / outside` (`nema prema karti`) | `0 / 0 / 0` | `0,1052 g` (`iznad praga niske`) | klizišta: **visoka** | **Klizišta (`visoko`)** |
| 6 | **Karlovac (uz Kupu)** | `45.4870, 15.5480` | Ne | `outside / outside / 1,5–2,5 m` (`nisko`) | `0 / 0 / 0` | `0,1759 g` (`iznad praga niske`) | `nema podataka` (izvan obuhvata) | **Potres (`iznad praga niske`)** |
| 7 | **Gunja (županjska Posavina)** | `44.8810, 18.8450` | Ne | `outside / outside / 1,5–2,5 m` (`nisko`) | `0,17 / 1,03 / 1,42` | `0,1036 g` (`iznad praga niske`) | `nema podataka` (izvan obuhvata) | **Potres (`iznad praga niske`)** |
| 8 | **Zagreb — priobalje Save** | `45.7930, 15.9600` | Ne | `outside / outside / 0,5–1,5 m` (`nisko`) | `0 / 0 / 0` | `0,2452 g` (`iznad praga niske`) | `nema podataka` (izvan obuhvata) | **Potres (`iznad praga niske`)** |
| 9 | **Split — središte** | `43.5081, 16.4402` | Ne | `outside / outside / 0,5–1,5 m` (`nisko`) | `0 / 0 / 0` | `0,1694 g` (`iznad praga niske`) | `nema podataka` (izvan obuhvata) | **Potres (`iznad praga niske`)** |
| 10 | **Osijek — središte** | `45.5550, 18.6955` | Ne | `outside / outside / outside` (`nema prema karti`) | `0 / 0 / 0` | `0,0688 g` (`niska seizmičnost`) | `nema podataka` (izvan obuhvata) | **Potres (`niska seizmičnost`)** |

## 3. Ponovna provjera 4. 11. 2026. (živi API, Docker)

Odjeljci 1 i 2 ostaju nepromijenjeni. Ovdje su vrijednosti koje korisnik stvarno vidi, dobivene iz `GET /api/report` na pokrenutom Docker stogu (Caddy + API), a ne izravnim pozivom funkcija pravila.

**Kako je pokrenuto**

- Commit `main`: `b8c98d9` (grana `chore/known-points-rerun-4-11` dodaje samo način rada `--api` u skriptu i ovaj odjeljak).
- Naredba: `backend/.venv/bin/python scripts/validate_known_points.py --api https://localhost --insecure` (`--insecure` samo zbog interne CA Caddyja; nije zadano). Trajanje oko 6 s za 10 točaka.
- `/api/health`: `geohazards_loaded`, `addresses_loaded`, `seismic_loaded`, `efas_loaded`, `map_layers_loaded` = `true`.
- HV se dohvaća uživo sa `servisi.voda.hr`; za svih 10 točaka odgovorio je bez greške (nijedna HV ćelija nije "nije provjereno").
- Sirovi izlaz (JSON, 10 zapisa, bez grešaka): `known_points_api_4_11.json` u privremenom direktoriju sesije (nije u repozitoriju).

**Rezultati** (razine doslovno iz API-ja; `nema podataka` = `NO_DATA`, `nema prema karti` = `NONE`)

| # | Lokacija | Poplava (izvor) i HV razredi `velika / srednja / mala` | Potres $a_g$ (razina) | Klizišta | Likvefakcija | Vrtače | Nepovoljno za gradnju | Podzemna voda | Najznačajniji |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Petrinja — središte | `nisko` (HV): `outside / outside / 1,5–2,5 m` | `0,114 g` (iznad praga niske) | nema podataka (izvan poligona studije) | `visoko` | nema podataka (izvan poligona studije) | nema prema karti | `srednje`: 1,96 m, 16. 2. 2021., 70 m | Likvefakcija (`visoko`) |
| 2 | Petrinja — Matije Gupca 12 | `nema prema karti` (HV): `outside / outside / outside` | `0,114 g` (iznad praga niske) | nema podataka (izvan poligona) | `visoko` | nema podataka (izvan poligona) | nema prema karti | `srednje`: 2,745 m, 16. 2. 2021., 13 m | Likvefakcija (`visoko`) |
| 3 | Sisak — Rimska ulica 19 | `nema prema karti` (HV): `outside / outside / outside` | `0,109 g` (iznad praga niske) | nema podataka (izvan poligona) | `visoko` | nema podataka (izvan poligona) | nema prema karti | `nisko`: 5,4 m, 24. 2. 2021., 57 m | Likvefakcija (`visoko`) |
| 4 | Glina — središte | `nisko` (HV): `outside / outside / < 0,5 m` | `0,116 g` (iznad praga niske) | nema podataka (izvan poligona) | `visoko` | nema podataka (izvan poligona) | nema prema karti | `visoko`: 1,065 m, 11. 2. 2021., 46 m | Likvefakcija (`visoko`) |
| 5 | Hrvatska Kostajnica | `nema prema karti` (HV): `outside / outside / outside` | `0,105 g` (iznad praga niske) | `visoko` | nema podataka (izvan poligona) | nema podataka (izvan poligona) | nema prema karti | nema podataka (nema bušotine u 1 km) | Klizišta (`visoko`) |
| 6 | Karlovac (uz Kupu) | `nisko` (HV): `outside / outside / 1,5–2,5 m` | `0,176 g` (iznad praga niske) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | Potres (iznad praga niske) |
| 7 | Gunja | `nisko` (HV): `outside / outside / 1,5–2,5 m`; EFAS se ne prikazuje | `0,104 g` (iznad praga niske) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | Potres (iznad praga niske) |
| 8 | Zagreb — priobalje Save | `nisko` (HV): `outside / outside / 0,5–1,5 m` | `0,245 g` (iznad praga niske) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | Potres (iznad praga niske) |
| 9 | Split — središte | `nisko` (HV): `outside / outside / 0,5–1,5 m` | `0,169 g` (iznad praga niske) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | Potres (iznad praga niske) |
| 10 | Osijek — središte | `nema prema karti` (HV): `outside / outside / outside` | `0,069 g` (niska seizmičnost) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | nema podataka (izvan Banovine) | Potres (niska seizmičnost) |

`all_no_data` je `false` za svih 10 točaka.

**EFAS u korisničkom izvješću.** EFAS se u izvješću pojavljuje samo gdje je HV `NO_DATA` (`combine_flood`). HV je za svih 10 točaka imao podatak, pa se EFAS ni za jednu točku ne prikazuje; napose za Gunju stupac EFAS iz odjeljka 2 (`0,17 / 1,03 / 1,42 m`) korisnik ne vidi, prikazuje se HV (`nisko`, 1,5–2,5 m).

**Razlike u odnosu na 2. 11.**

Poplava (razina i HV razredi) je u svih 10 točaka jednaka odjeljku 2: nema razlike uživo HV vrijednosti.

- Petrinja 1–4, Sisak, Glina, Kostajnica, Karlovac, Gunja, Zagreb, Split, Osijek, potres $a_g$ (sve točke): npr. `0,1145` je sada `0,114`, `0,1086` je `0,109`, `0,1759` je `0,176`, `0,0688` je `0,069` i sl. Razina potresa nepromijenjena. Uzrok: rounding/presentation (API zaokružuje na 3 decimale).
- Gunja, EFAS `0,17 / 1,03 / 1,42 m`: više se ne prikazuje. Uzrok: combine_flood prikazuje EFAS samo kad je HV `NO_DATA` (opisano gore; nije promjena podataka). Ostali EFAS stupci (`0 / 0 / 0`) iz odjeljka 2 više nisu relevantni: uzrok D20 (nodata/izvan rastera je `NO_DATA`, ne 0), a u izvješću se ionako ne koriste jer HV ima podatak.
- Petrinja 2, 3, Glina, Kostajnica, Karlovac, Gunja, Zagreb, Split, Osijek, podzemna voda: u odjeljku 2 nije bila (samo Petrinja 1: `1,96 m`, 70 m, ista vrijednost). Uzrok: D16 groundwater added (u Banovini: Petrinja 2 `2,745 m` / 13 m, Sisak `5,4 m` / 57 m, Glina `1,065 m` / 46 m, Kostajnica `NO_DATA`, nema bušotine u 1 km; izvan Banovine `NO_DATA`).
- Petrinja 1–4, klizišta/vrtače (i likvefakcija/vrtače za Kostajnicu): u odjeljku 2 nisu bili prikazani; sada `NO_DATA` s bilješkom "Točka nije unutar poligona studije." Uzrok: brief 010 missing/outside-polygon → NO_DATA (uspoređivanje s odjeljkom 2 nije moguće ćeliju po ćeliju jer ih tamo nema).
- Nepovoljno za gradnju: za točke u Banovini `nema prema karti` (`NONE`), u odjeljku 2 nije bilo prikazano. Uzrok: isti razlog kao gore (nova prezentacija svih ćelija u API-ju), ne promjena podataka.
- Petrinja 2, podzemna voda, format datuma: izvor daje `16.2.2021. 9:14:35`, a Petrinja 1 `16.02.2021.`; bilješka u izvješću je normalizirana ("16. 2. 2021."). Uzrok: rounding/presentation.
- Najznačajniji rizik: nepromijenjen u svih 10 točaka (`Likvefakcija`, `Klizišta`, `Potres`).

Broj razlika bez objašnjenja (`unexplained`): **0**.
