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
