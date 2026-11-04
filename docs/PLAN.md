# PLAN — Geo-rizik (do 9. 11. 2026.)

Uloge: **M** = Max (voditelj, AI, arhitektura), **B** = backend i geopodaci, **C**, **D** = sučelje, sadržaj, testiranje, dokumentacija. Kontrolne točke su obavezne: ako nisu ispunjene, režemo opseg, ne pomičemo rok.

| Dan | M | B | C | D | Kontrolna točka |
|---|---|---|---|---|---|
| **Pet 30. 10.** | odobrenje SPEC-a; repo, struktura, CI, licenca | pipeline: preuzimanje adresa i geohazarda | SvelteKit kostur, MapLibre karta | `layers.yaml`: izvori, licence, poveznice | Specifikacija odobrena |
| **Sub 31. 10.** | `report` servis i tablica pravila + testovi | adresni indeks (FTS5), geokoder API; EFAS izrez za RH, COG | tražilica adrese s dovršavanjem | kurirani preporučeni koraci (tekst + poveznice na institucije) | Adresa → koordinate radi |
| **Ned 1. 11.** | HV uzorkovanje piksela + keš; integracija u izvještaj | ESHM20: istraživanje pristupa, **go/no-go** | kartice izvještaja | predlošci objašnjenja na hrvatskom | **Vertikalni prototip: adresa u Petrinji → izvještaj kraj-na-kraj** |
| **Pon 2. 11.** | testni skup ~20 hrvatskih upita; JSON shema upita | ESHM20 integracija ili rez; EFAS u izvještaju | stranica "Izvori podataka", disclaimer | ručno testiranje na 10 poznatih točaka | Svi MUST slojevi u izvještaju |
| **Uto 3. 11.** | test otvorenih modela (Ollama), odabir | H3 mreža; HV uzorkovanje Banovine (preko noći) | slojevi na karti (uključivanje/isključivanje) | mobilni prikaz i kontrast | **Deploy v1 (svi MUST) na VPS-u** |
| **Sri 4. 11.** | orkestrator + katalog slojeva + validacija | API za H3 pretragu | ekran "Istraži": čipovi filtera, rezultati | testiranje | Pretraga ručnim filterima radi |
| **Čet 5. 11.** | LLM → JSON → orkestrator, poruke o nepodržanom | usporedba dvije lokacije (API) | prikaz usporedbe | README: pokretanje i izvori | Prirodni jezik radi na testnom skupu |
| **Pet 6. 11.** | LLM objašnjenje i pitanja o izvještaju (SHOULD) | ispis/PDF, performanse, keš | UX poliranje | pristupačnost (provjera WCAG AA) | **Zamrzavanje funkcionalnosti navečer** |
| **Sub 7. 11.** | ARCHITECTURE konačno; popravci | popravci, testovi, finalni deploy | popravci | skripta za video, snimke ekrana | Nema poznatih kritičnih grešaka |
| **Ned 8. 11.** | snimanje i montaža videa (≤ 3 min) | provjera repozitorija, licence, popis alata uključujući AI | montaža videa | `SUBMISSION_CHECKLIST` proba | Video gotov |
| **Pon 9. 11.** | **rezerva**; slanje e-pošte **do 18:00** | rezerva | rezerva | rezerva | Rješenje predano, potvrda primitka |

Pretpostavka: radnim danima uz predavanja realno 3–5 sati po osobi. Ako netko ispadne, prvo se reže SHOULD 12 (LLM objašnjenje), zatim 11 (usporedba), pa 10 (Istraži).

## Status kontrolnih točaka

| Datum | Kontrolna točka | Stanje (3. 11. 2026.) |
|---|---|---|
| 30. 10. | Specifikacija odobrena | **ispunjeno** |
| 31. 10. | Adresa → koordinate radi | **ispunjeno 3. 11. (kasni 3 dana)**: PR #1 mergan; geokoder na stvarnom DGU indeksu (1.683.411 adresa), `/api/addresses`, uvicorn s `--no-access-log` (zadaci 004, 008, 009) |
| 1. 11. | Vertikalni prototip (Petrinja kraj-na-kraj) | **ispunjeno 3. 11. (kasni 2 dana)**: PR #4 mergan (frontend SvelteKit + MapLibre, zadatak 011); Petrinja adresa/točka → izvještaj s izvorima na 375 px provjerena lokalno snimkom zaslona (prije merge-a, na grani PR-a) |
| 2. 11. | Svi MUST slojevi u izvještaju | **nije ispunjeno na `main`**; potres na `main` od 3. 11. (PR #7, D17, ESHM20); EFAS na `main` od 3. 11. (PR #2, D20: nodata → nema podataka); podzemna voda na `main` od 3. 11. (PR #3, D16: 602 bušotine, napomena s datumom i udaljenošću mjerenja); nedostajući geohazard sloj u Banovini → nema podataka (PR #16, SCRUM-67) |
| 3. 11. | Deploy v1 (svi MUST) na VPS-u | **djelomično**: deploy lokalno spreman i provjeren (PR #20, Docker Compose + Caddy), poslužitelj i domena još nisu odabrani (SCRUM-42 In Progress); uključivi slojevi na karti na `main` (PR #21, SCRUM-32) |

Odluke D16 (pragovi podzemne vode) i D17 (ESHM20 za potres) korisnik je odobrio 3. 11.; red D17 je u `DECISIONS.md` (PR #7, mergan 3. 11.), red D16 je u `DECISIONS.md` (PR #3, mergan 3. 11.; 5 placeholder točaka i 4 bušotine bez datuma odbačene, 12 bušotina s dubinom 0 m i datumom zadržano).

PR #9 mergan 3. 11. (zadatak 001, SCRUM-34, 35): sažetak nikad ne tvrdi "nije utvrđena povišena opasnost" kad nema podataka; tekstovi bez neizvorenih tvrdnji (povratna razdoblja HV, "1964."), decimalni zarez; 196 testova prolazi. Nije provjereno uživo: EFAS tekst i `all_no_data=true` (samo testovi). `flood_hv.info_url` u `layers.yaml` zamijenjen jer je stari vraćao 404 (nova stranica HV-a vraća 200, ali ne spominje izričito 2019.).

PR #4 mergan 3. 11. (zadatak 011, zamjenjuje 002; SCRUM-20, 21, 29, 30, 31, 33, 36, 37, 41): frontend usklađen s API-jem na `main` (razina tekstom + ikonom, `all_no_data` → "nema podataka za ovu lokaciju", izvor i `source.note` na svakoj kartici, decimalni zarez, stranica Izvori iz `/api/sources` s pravilima prema SPEC §6), uklonjen `sw.js` i unpkg, CI dobio `frontend` posao (`npm ci && npm run build`). HV sloj na karti: CORS u redu, iscrtava se samo na zumu 12–14. Na `main`: 196 testova prolazi, build prolazi. Nije provjereno uživo: EFAS kartica (u Gunji odgovara HV), greška 422 i nedostupan geokoder. Otvoreno: dvostruka napomena na ESHM20 kartici, zaštita od zastarjelog odgovora, OSM pločice (SCRUM-42).

PR #20 mergan 3. 11. (zadatak 013; SCRUM-43 Done, SCRUM-42 djelomično): Docker Compose s dva kontejnera (`api` FastAPI bez access loga, `web` Caddy s HTTPS-om; `DOMAIN` iz env varijable, bez nje `https://localhost`), frontend na `adapter-static` (SPA), `scripts/prepare_data.sh` (svi koraci pripreme `data/`, preskače gotovo, atomarno pisanje preko `.part`), `scripts/wait_healthy.sh`, README na hrvatskom (pokretanje, podaci, izvori i licence iz `layers.yaml`, ograničenja, alati uključujući Claude Code). Caddy ne logira pristupe ni greške proxyja (inače bi URL s koordinatama završio u logu); `Referrer-Policy strict-origin-when-cross-origin` zbog pravila OSM pločica. Lokalno provjereno u Dockeru: svi slojevi učitani, adrese i izvještaj Petrinja kroz Caddy, bez koordinata u logovima ni pri 502. Nije provjereno: preglednik preko https, OSM pločice s novom politikom, stvarno preuzimanje DGU zipa, javna domena (Let's Encrypt). Podloga karte ostaje `tile.openstreetmap.org` (odluka korisnika 3. 11.).

PR #21 mergan 3. 11. (zadatak 012; SCRUM-32 Done): uključivi slojevi na karti s legendom tekstom i izvorom iz `/api/sources`: HV WMS (zum 12–14), MPGI geohazardi (samo Banovina, pojednostavljeni GeoJSON iz `pipeline/build_map_layers.py`, samo prikaz; razred u izvještaju i dalje iz izvornih podataka), EFAS RP10/100/500 kao PNG ~180 m (najveća dubina u bloku, retci poravnani za Web Mercator, ODbL). Posluženo s `/api/map-data` (gzip, ukupno ~4,5 MB). Odluka D21 upisana (klizišta grublje: rubovi većinom do ~40 m, izostavljeni dijelovi do ~2 ha). Na `main`: 207 testova prolazi. Nije provjereno: neuspjelo učitavanje same EFAS slike. Sljedeće: zadatak 014 (provjera razreda klizišta oko neispravne geometrije izvora, ne blokira deploy).

PR #25 mergan 4. 11. (zadatak 015; SCRUM-44 ostaje In Progress, komentar s rezultatima): 10 poznatih točaka ponovno provjereno na `main` kroz lokalni Docker stack (`https://localhost/api/report`, `scripts/validate_known_points.py --api`). Svih 10 točaka odgovorilo, HV uživo radio; razine poplave i HV razredi isti kao 2. 11.; potres iste razine (zaokruživanje na 3 decimale); Gunja više ne prikazuje EFAS jer HV ima podatak; podzemna voda (D16) nova; nerazjašnjenih razlika 0 (`docs/KNOWN_POINTS_VALIDATION.md`, odjeljak 3). Otvoreno: izvan poligona MPGI studije → nema podataka nije izričito u SPEC §6; Kostajnica "nepovoljno za gradnju" = nema prema karti, a vrtače i likvefakcija = nema podataka (zasebna odluka). Ponoviti na javnom poslužitelju nakon deploya (SCRUM-42). 209 testova prolazi.

PR #27 mergan 4. 11. (zadatak 022, D22; SCRUM-69 Done): servis Hrvatskih voda 4. 11. vraća 502 za scenarij male vjerojatnosti. Pri ispadu HV-a EFAS ostaje rezerva, ali izvještaj izričito navodi privremeni prekid, koji scenariji nisu odgovorili i što su pokazali ostali; sažetak to spominje uvijek. API: `detail.hv_status`, `detail.hv_unavailable_scenarios`. 223 testa prolazi. Provjereno uživo kroz Docker stack i u pregledniku (Gunja: EFAS kartica s napomenom o ispadu, 375 px). Audit pristupačnosti i preglednika (zadatak 016, SCRUM-38 In Progress): OSM pločice rade (nema 403); kontrast teksta, razine tekstom i ikonom, tipkovnica i 375 px prolaze; ispravci u zadacima 017 (utrka zahtjeva, PR #28), 018 i 019 (`/izvori`, kontrole karte) i 021 (tekstovi, licenca, točka Sisak); 020 odgođen.

`docs/PLAN.md` je zajednički zapis statusa za tim (`CLAUDE.md` je lokalan, u `.gitignore`).
