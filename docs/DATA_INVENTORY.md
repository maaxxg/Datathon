# DATA_INVENTORY — Geo-rizik (Datathon 2026, izazov B)

Provjereno 30. 10. 2026. iz preglednika (CKAN API + živi upiti na servise). Testne točke (WGS84, lat/lon):
Petrinja 45.4375/16.2739, Sisak 45.4840/16.3740, Karlovac 45.4870/15.5480, Gunja 44.8810/18.8450, Zagreb uz Savu 45.7930/15.9600, Split 43.5081/16.4402.

## Sažetak

| Skup | Izdavač | Servis / URL | Format | Licenca | Pokrivenost | Ažurnost | Rezultat testa | Ocjena |
|---|---|---|---|---|---|---|---|---|
| Geohazardi | MPGI (Zavod za prostorni razvoj) | `https://gis2.mgipu.hr/srv1/RGN_MGIPU_Public/wfs` (gis1 vraća **502**; gis3/gis4 nisu testirani izravno) | WFS 2.0.0, izlaz GeoJSON/SHAPE-ZIP/CSV | Otvorena dozvola (OD); AccessConstraints NONE | **Samo Banovina/Sisačko-moslavačka**: lon 15.73–16.92, lat 44.96–45.68 (CKAN `spatial_text`: Sisačko-moslavačka županija) | studija 2021., CKAN zapis 15. 10. 2026. | 8 slojeva rade; upit po točki 20–250 ms, iznimka `kliziste_podloznost` **23,7 s** | **GO (samo regija)** |
| Karte opasnosti od poplava 2019. | Hrvatske vode | `https://servisi.voda.hr/wms`, slojevi `poplave_opasnosti_2019:hr.fd.opasnost-od-poplave-{velika,srednja,mala}-vjerojatnost_2019` | WMS 1.3.0, **raster** | AccessConstraints NONE, Fees NONE; vektor (SHP) samo na zahtjev | cijela RH (područja s izrađenim kartama) | 2019. | GetFeatureInfo **ne radi** (`LayerNotQueryable`). **Radi** čitanje boje piksela iz GetMap PNG-a: boje točno odgovaraju legendi (5 razreda dubine) | **RIZIK → GO uz zaobilazno rješenje** |
| Karte rizika od poplava 2019. | Hrvatske vode | isti WMS, `poplave_rizici_2019:hr.karta-rizika-od-poplava-*_2019` | WMS (queryable=1) | kao gore | cijela RH | 2019. | GFI vraća **prazan** FeatureCollection na svim 6 točaka i na 3 točke gdje karta ima piksele | **NO-GO** (za sada) |
| Skupovi poplava na data.gov.hr | — | slugovi `karte-opasnosti-od-poplava` i `karte-rizika-od-poplava` | — | — | — | — | **ne postoje** na data.gov.hr (CKAN: *Not Found*); postoje samo na dev-data.gov.hr. Na portalu HV ima 25 skupova (npr. `podrucja-sa-potencijalno-znacajnim-rizicima-od-poplava`) | **RIZIK** za bod "upotreba otvorenih podataka" |
| Katastarske čestice INSPIRE | DGU | `https://api.uredjenazemlja.hr/services/inspire/cp/wfs` (`cp:CadastralParcel`, `cp:CadastralZoning`) | WFS 2.0.0 (GML) | OD; NONE | cijela RH | CKAN 22. 10. 2026.; čestice od 2025-12 | bbox oko točke u Sisku: 10 čestica, 3 vraćene za **18,2 s** | **RIZIK** (prespor za živi upit; keširati ili preskočiti) |
| Zgrade (DKP) INSPIRE | DGU | `https://api.uredjenazemlja.hr/services/inspire/bu/wfs` (`bu:Building`) | WFS 2.0.0 | OD; NONE | cijela RH | 22. 10. 2026. | Capabilities OK (25 ms); GetFeature nije testiran | **nije provjereno** |
| Adrese INSPIRE | DGU | ATOM: `https://geoportal.dgu.hr/services/atom/INSPIRE_Addresses_(AD).zip` | GML 3.2.1 zip, **84 MB**, ETRS89/LAEA | OD | cijela RH | 22. 10. 2026. | preuzimanje dostupno (veličina iz ATOM feeda, datoteka nije preuzeta); WMS nije dostupan iz preglednika (CORS) | **GO** za lokalni geokoder |
| Visine (DMR) INSPIRE | DGU | ATOM: `RH_ELEV_<n>.tif` (~34 MB po pločici) | **GeoTIFF**, ETRS89/TM33 | OD | cijela RH | 22. 10. 2026. | sirove visine postoje; rezolucija i vrijednosti nisu provjerene | **GO** (provjeriti rezoluciju) |
| Digitalni model reljefa (WMS) | DGU | `geoportal.dgu.hr/services/auth/dmr/wms` | WMS s `authKey` | OD | RH | — | traži ključ; nepotrebno zbog GeoTIFF-a | **NO-GO** |
| Hidrografija INSPIRE | DGU | `geoportal.dgu.hr/services/inspire/hy/wms` + ATOM | WMS/ATOM | OD | RH | 22. 10. 2026. | nije testirano | **nije provjereno** |
| Upravne jedinice INSPIRE | DGU | `geoportal.dgu.hr/services/inspire/au/wms` + ATOM | WMS/ATOM | OD | RH | 22. 10. 2026. | nije testirano | **nije provjereno** |
| Natura 2000 | HAOP (**NEAKTIVAN**) | `services.iszp.hr/wfs` | WFS (http) | licenca nije navedena | RH | 20. 7. 2026. | servis nedostupan iz preglednika | **RIZIK**; alternativa: HV WMS sloj `zasticena_podrucja:hr.rzp.e_ekoloska-mreza-*` (queryable=1, nije testiran) |
| CORINE Land Cover | HAOP (**NEAKTIVAN**) | `gis.azo.hr/.../Corine_Land_Cover_2012` | WFS/WMS (http) | licenca nije navedena | RH | 2012. podaci | nije testirano | **NO-GO** (zastarjelo, neaktivan izdavač) |

## Ključni nalazi

1. **Poplave: nema upita po točki.** Slojevi opasnosti su raster koji GeoServer ne pušta kroz GetFeatureInfo, vektor je samo na zahtjev. Zaobilazno rješenje koje radi: zatražiti GetMap PNG malog područja oko točke (npr. ±0,01°, 201×201 px) i pročitati boju središnjeg piksela. Boje su točne vrijednosti iz legende:
   `#BEE8FF` dubina < 0,5 m · `#73DFFF` 0,5–1,5 m · `#73B2FF` 1,5–2,5 m · `#7A8EF5` > 2,5 m · `#004DA8` stalne vodene površine.
   Ograničenja: sloj se **ne iscrtava na malim mjerilima** (okvir od 1,2° vratio je 0 piksela), pa uvijek tražimo malo područje; rezolucija je ona iz rendera, ne izvornih podataka; ovisimo o tome da HV ne promijeni stil. Rezultat je i dalje deterministički i ponovljiv. Primjer: Karlovac točka = *mala vjerojatnost, 1,5–2,5 m*; Zagreb uz Savu = *mala vjerojatnost, 0,5–1,5 m*; za srednju vjerojatnost sve testne točke su izvan zone (piksel proziran).
2. **Geohazardi pokrivaju samo Banovinu** (lon 15.73–16.92, lat 44.96–45.68), ne cijelu RH kako tvrdi NIPP. Slojevi "podložnost" imaju 2–3 velika multipoligona (razredi niska/srednja/visoka), pa ih **jednom preuzmemo** (GeoJSON) i radimo point-in-polygon lokalno. To rješava i sporost od 23 s.
3. **Geokodiranje:** DGU adrese su otvorene i preuzimljive (84 MB GML). Za regiju Banovine to je mali indeks. Alternativa za ostatak RH: Nominatim/OSM (ODbL, uz navođenje izvora i limit 1 upit/s), ali to nije s data.gov.hr.
4. **Reljef:** postoji sirovi GeoTIFF (OD licenca). Jednostavna izvedena mjera (nagib, visina iznad najbližeg vodotoka) je izvediva; ML na reljefu ne preporučujem zbog roka.
5. **Katastar** radi, ali sporo (18 s). Za demo: unos adrese ili klik na kartu, a čestica samo kao dodatna informacija s keširanjem.

## Prijedlog realnog opsega

- **Regija:** Sisačko-moslavačka županija / Banovina (Petrinja, Sisak, Glina). Jedino tu imamo i poplave i geohazarde, a priča (potres 2020. + poplave Kupe) je jaka za video.
- **Rizici u izvještaju:** (1) poplave, 3 scenarija s razredom dubine; (2) klizišta, likvefakcija, vrtače (podložnost); (3) dubina podzemne vode i "nepovoljno za gradnju"; (4) zaštićena područja/Natura kao informacija, ako se HV sloj potvrdi.
- **Izvan opsega:** cijela RH za geohazarde, ML, karte rizika (GFI prazan), CORINE.

## Što još nije provjereno

- gis3/gis4.mgipu.hr (testiran samo gis2; gis1 vraća 502). Treba fallback na više hostova.
- Atributi slojeva `podzemna_voda_dubina`, `nepovoljno_za_gradnju` (prazni `properties` na testnoj točki) i inventara.
- Rezolucija DMR GeoTIFF-a i sadržaj adresnog GML-a (datoteke nisu preuzete).
- HV sloj Natura 2000 (GetFeatureInfo).
- Uvjeti korištenja na stranicama Hrvatskih voda (u Capabilities piše NONE, ali skup nije objavljen na data.gov.hr).

Skripta za ponavljanje provjere: `scripts/check_sources.py`.

---

## Dodatak (30. 10. 2026.): što Pravila dopuštaju i dodatni izvori

**Pravila, poglavlje III:** rješenje mora koristiti otvorene podatke **javnog sektora**, prednost imaju podaci s Portala. Uz njih se smiju koristiti i drugi javno dostupni izvori (europski, nacionalni i lokalni portali otvorenih podataka, API servisi tijela javnog sektora i sl.), ako dozvola dopušta korištenje. Obavezno je navesti sve skupove, izdavače i poveznice. **Posljedica:** EU izvori (JRC, Copernicus, EEA) su sigurni. OpenStreetMap nije javni sektor, pa ga ne koristimo kao izvor podataka (eventualno samo kao podlogu karte). Jezgra mora i dalje biti data.gov.hr.

### Dodatni kandidati

| Izvor | Izdavač | Što daje | Format / pristup | Licenca | Pokrivenost | Status | Ocjena |
|---|---|---|---|---|---|---|---|
| EFAS river flood hazard maps v3.1.1 | EK, JRC / Copernicus EMS | dubina poplave u m za 9 povratnih razdoblja, 90 m | GeoTIFF, WGS84, izravno s JRC Data Store (FTP) | **ODbL 1.0** | cijela Europa, uključujući RH | preuzeto i izrezano za RH 2. 11. (`RP10`, `RP100`, `RP500`, EPSG:4326, 5160×7740 px, ~22 MB ukupno) | **GO**: nacionalna rezerva gdje HV karte nema; usporedba "službena HV karta vs. europski model" |
| ESHM20 (European Seismic Hazard Model 2020) | EFEHR (ETH Zürich i partneri) | potresna opasnost (karte, krivulje opasnosti) | web platforma hazard.efehr.org + GitLab | **CC BY 4.0** (obavezno citiranje) | cijela Europa | licenca provjerena; točan servis/API za točku nije provjeren | **RIZIK → vjerojatno GO**: potresni rizik za cijelu RH |
| EGMS (European Ground Motion Service) | Copernicus / EEA | InSAR pomaci tla (slijeganje, klizanje) | CLMS preuzimanje | Copernicus: slobodno uz navođenje izvora | Copernicus države, uključujući RH | provjeren samo GNSS model (50 km, pregrub); ortho proizvod (100 m) nije provjeren, a preuzimanje možda traži registraciju | **RIZIK** (COULD) |
| Strateške karte buke | MZOE (**NEAKTIVAN**), na Portalu | buka uz ceste i gradove (izazov B je izričito navodi) | WFS `servisi.azo.hr/zdravlje/wfs` (http) | nije navedena | aglomeracije, glavne ceste | iz preglednika blokirano (http) | **nije provjereno** |
| Indeks kvalitete zraka INSPIRE | DGU / AZO, na Portalu | mjerne postaje i indeks | WFS `servisi.azo.hr/inspire/geos1/hh/wfs` (http) | nije navedena | RH | iz preglednika blokirano (http) | **nije provjereno** |
| Zborna mjesta civilne zaštite | Grad Zagreb, na Portalu | točke okupljanja u nesreći | GeoJSON | OD | samo Zagreb | preuzimanje iz preglednika blokirano | **GO** ako proširimo na Zagreb |
| DOF 1:500 nakon potresa, Sisačko-moslavačka | DGU, na Portalu | ortofoto nakon potresa (vizualno, za video) | WMS (auth verzija odgovara 200) | OD | SMŽ | Capabilities OK | **COULD** |
| Osnovna geološka karta 1:50 000 | HGI, na Portalu | geologija | samo HTML poveznica | nije navedena | RH | bez servisa | **NO-GO** |
| Analiza vatrogasnih intervencija | DUZS (**NEAKTIVAN**) | povijesni požari | CSV preko vanjske stranice | nije navedena | RH | nedostupno | **NO-GO** |

Napomena: neuspjeh `http://` izvora iz preglednika vjerojatno je blokada miješanog sadržaja, ne nužno nedostupan servis. Treba ih ponovno provjeriti skriptom.

### Utjecaj na opseg

S EFAS kartama i ESHM20 izvještaj može pokriti **cijelu RH** u dva sloja točnosti:
1. **Nacionalno:** poplave (HV 2019. gdje postoji, inače EFAS) i potresna opasnost (ESHM20).
2. **Detaljno u Banovini:** dodatno klizišta, likvefakcija, vrtače i podzemna voda (MPGI).

To podiže bodove za povezivanje podataka i relevantnost, a demo scenarij u Petrinji ostaje isti.
