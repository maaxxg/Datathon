# Licence podataka

Kod u ovom repozitoriju je pod MIT licencom (`/LICENSE`). Podaci u ovoj mapi imaju vlastite licence:

| Datoteke | Izvor | Licenca | Obveza |
|---|---|---|---|
| `geohazards/*.geojson` | MPGI, Geohazardi (data.gov.hr) | Otvorena dozvola RH | navesti izvor |
| `map/geohazard_*.geojson`, `map/banovina_coverage.geojson` | izvedeno iz MPGI, Geohazardi (data.gov.hr); pojednostavljeno, samo za prikaz na karti | Otvorena dozvola RH | navesti izvor (MPGI) |
| `addresses.sqlite` | DGU, Adrese INSPIRE (data.gov.hr) | Otvorena dozvola RH | navesti izvor |
| `efas/*.tif` i H3 mreža s EFAS vrijednostima | EK JRC, Copernicus EMS – EFAS flood hazard maps v3.1.1 | **ODbL 1.0** | navesti izvor; izvedena baza objavljuje se pod ODbL 1.0 (https://opendatacommons.org/licenses/odbl/1-0/) |
| `map/efas_rp*.png` | izvedeno iz EK JRC, Copernicus EMS – EFAS flood hazard maps v3.1.1 (klasificirani PNG, ~180 m, samo za prikaz) | **ODbL 1.0** | navesti izvor; izvedena baza pod ODbL 1.0 |
| `seismic/eshm20_pga475.json` | EFEHR / ETH Zürich, European Seismic Hazard Model 2020 (ESHM20, Danciu et al., 2021, DOI: 10.12686/a15) | **CC BY 4.0** | obavezno citiranje i navođenje izvora (https://creativecommons.org/licenses/by/4.0/) |

Izvedena H3 mreža (`grid/*`) sadrži vrijednosti iz EFAS-a i stoga se objavljuje pod **Open Database License (ODbL) v1.0**.
