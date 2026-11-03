# SPEC — Geo-rizik

Datathon Portala otvorenih podataka 2026, izazov B: Okoliš i održivi prostor. Verzija 1.0 (30. 10. 2026.), **odobreno**.

## 1. Problem

Kupci i najmoprimci nekretnina u Hrvatskoj teško saznaju kojim je prirodnim opasnostima izložena lokacija. Podaci postoje (Hrvatske vode, MPGI, DGU, europski servisi), ali su razbacani po geoportalima, u stručnom obliku i često bez upita po adresi. Nakon potresa 2020. i poplava Kupe, Banovina je primjer gdje je ta informacija kritična.

## 2. Rješenje u jednoj rečenici

Web aplikacija u kojoj korisnik unese adresu i u nekoliko sekundi dobije razumljiv, provjerljiv izvještaj o izloženosti poplavama, potresu i geološkim opasnostima, s izvorom uz svaki podatak. Može i prirodnim jezikom pretraživati područja s traženim svojstvima.

## 3. Korisnici

- **Primarni:** kupci i najmoprimci nekretnina (laici).
- **Sekundarni:** općine i civilna zaštita, projektanti i geodeti, novinari.

## 4. Korisnički scenariji

- **S1 (glavni, video):** Obitelj razmatra kuću u Petrinji. Unese adresu, dobije izvještaj: poplave po scenarijima, potresna opasnost, podložnost klizištima, likvefakciji i vrtačama, dubina podzemne vode. Pročita objašnjenje i preporučene korake, otvori izvore, ispiše PDF.
- **S2:** Korisnik klikne na kartu bilo gdje u RH i dobije izvještaj nacionalne razine (poplave, potres), uz jasnu oznaku da detaljni geohazardi ovdje nisu dostupni.
- **S3 (SHOULD):** Korisnik napiše "pronađi mi područja oko Petrinje bez poplava i s niskom podložnosti klizištima". Vidi filtere koje je sustav razumio, poruku o onome što nije moguće i istaknuta područja na karti.
- **S4 (SHOULD):** "Usporedi ovu adresu s Ulicom X u Sisku": dva izvještaja jedan uz drugi.

## 5. Funkcionalnosti

### MUST
1. Pretraga adrese (vlastiti indeks iz DGU Adresa INSPIRE) s automatskim dovršavanjem; odabir lokacije klikom na kartu.
2. Izvještaj za točku:
   - **Poplave:** HV karte opasnosti 2019. za 3 scenarija (razred dubine); gdje HV nema podatka, EFAS (dubina za povratna razdoblja).
   - **Potres:** ESHM20 (nakon potvrde pristupa; vidi rizike).
   - **Banovina:** podložnost klizištima, likvefakciji i vrtačama; dubina podzemne vode; "nepovoljno za gradnju".
3. Razina po opasnosti prema javnoj tablici pravila (odjeljak 6); "najznačajniji rizik" na vrhu; razlika "nema rizika prema karti" / "nema podataka".
4. Uz svaku stavku izvor: naziv skupa, izdavač, godina, rezolucija, poveznica. Zasebna stranica "Izvori podataka".
5. Karta (MapLibre) s lokacijom i uključivim slojevima (HV WMS, geohazardi, EFAS).
6. Objašnjenje izvještaja na hrvatskom iz predloška teksta (radi bez LLM-a) i kurirani preporučeni koraci s poveznicama na institucije.
7. Disclaimer na svakom izvještaju; adrese se ne spremaju.
8. Mobile-first, WCAG AA kontrast, razina tekstom i ikonom.
9. Javni repozitorij s otvorenom licencom, README, deploy.

### SHOULD
10. Ekran "Istraži": prirodni jezik → JSON upit (otvoreni LLM preko Ollame, JSON shema) → orkestrator provjerava katalog slojeva → determinističko izvršavanje nad H3 mrežom → rezultati na karti. Filteri vidljivi i uredljivi kao čipovi.
11. Usporedba dvije lokacije.
12. LLM objašnjenje i "pitaj o ovom izvještaju" (samo iz JSON-a izvještaja).
13. Ispis/PDF izvještaja.

### COULD
14. Buka (strateške karte) i kvaliteta zraka, ako se http servisi potvrde.
15. EGMS pomaci tla.
16. Ortofoto 1:500 nakon potresa kao podloga u Banovini.
17. Javni API (`/api/report?lat=&lon=`, GeoJSON) s OpenAPI opisom za integracije.

## 6. Metodologija razina (prijedlog, provjerava se testovima)

Razine: **visoko**, **srednje**, **nisko**, **nema prema karti**, **nema podataka**.

| Opasnost | Izvor | Pravilo |
|---|---|---|
| Poplava | HV 2019. | velika vjerojatnost (bilo koja dubina) → visoko; srednja vjerojatnost s dubinom > 1,5 m → visoko; srednja ≤ 1,5 m → srednje; samo mala vjerojatnost → nisko; izvan svih zona unutar obuhvata karte → nema prema karti; stalna vodena površina → posebna oznaka |
| Poplava | EFAS (samo gdje HV nema podatka) | dubina > 0 za RP10 → visoko; za RP100 → srednje; samo za RP500 → nisko; inače nema prema karti. Oznaka "europski model, 90 m, okvirno" |
| Potres | ESHM20 (EFEHR, 475 god., CC BY 4.0, D17); okvirno; mreža ~10 km; stijena Vs30 = 760 m/s; izvor nije s data.gov.hr | razredi prema Eurokodu 8 (EN 1998-1, 3.2.1): ag ≤ 0,04 g **vrlo niska seizmičnost**; ≤ 0,08 g **niska seizmičnost**; > 0,08 g **iznad praga niske seizmičnosti**, uz prikaz točne vrijednosti i usporedbu s poznatim mjestima. Bez razreda "visoko" jer za njega nema normiranog praga |
| Klizišta, likvefakcija, vrtače | MPGI geohazardi | razred podložnosti iz podataka (niska/srednja/visoka) izravno; izvan obuhvata → nema podataka |
| Nepovoljno za gradnju | MPGI | unutar poligona → visoko (oznaka) |
| Podzemna voda | MPGI | razredi prema atributu dubine (atribut još nije provjeren) |

"Najznačajniji rizik" je opasnost s najvišom razinom. Kod jednakih razina redoslijed je: poplava, potres, klizišta, likvefakcija, vrtače.

## 7. Izvan opsega

Požari, ML na reljefu, korisnički računi i spremanje izvještaja, cijene nekretnina, službena potvrda ili stručno mišljenje, pretraga područja sa svim slojevima izvan Banovine, karte rizika HV (GFI prazan).

## 8. Nefunkcionalni zahtjevi

- Izvještaj za < 5 s (keš za ponovljene točke).
- Rad i bez LLM-a (predlošci, ručni filteri).
- Privatnost: bez spremanja adresa, keš po koordinatama zaokruženima na ~100 m, bez analitike trećih strana.
- Sve na hrvatskom; kod i komentari na engleskom.
- Testovi za deterministički dio na poznatim točkama.

## 9. Status

Odobreno 30. 10. 2026. Riješeno: razredi za potres prema Eurokodu 8 (D13), licenca koda MIT + ODbL za izvedene EFAS podatke (D14). Otvoreno: ime aplikacije (radni naziv "Geo-rizik").
