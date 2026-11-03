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
| 3. 11. | Deploy v1 (svi MUST) na VPS-u | **nije ispunjeno**: svi PR-ovi iz reda merge-a su na `main` (#6 ✅ → #8 ✅ → #1 ✅ → #7 ✅ → #2 ✅ → #3 ✅ → #9 ✅ → #4 ✅); deploy na VPS još nije napravljen (SCRUM-42) |

Odluke D16 (pragovi podzemne vode) i D17 (ESHM20 za potres) korisnik je odobrio 3. 11.; red D17 je u `DECISIONS.md` (PR #7, mergan 3. 11.), red D16 je u `DECISIONS.md` (PR #3, mergan 3. 11.; 5 placeholder točaka i 4 bušotine bez datuma odbačene, 12 bušotina s dubinom 0 m i datumom zadržano).

PR #9 mergan 3. 11. (zadatak 001, SCRUM-34, 35): sažetak nikad ne tvrdi "nije utvrđena povišena opasnost" kad nema podataka; tekstovi bez neizvorenih tvrdnji (povratna razdoblja HV, "1964."), decimalni zarez; 196 testova prolazi. Nije provjereno uživo: EFAS tekst i `all_no_data=true` (samo testovi). `flood_hv.info_url` u `layers.yaml` zamijenjen jer je stari vraćao 404 (nova stranica HV-a vraća 200, ali ne spominje izričito 2019.).

PR #4 mergan 3. 11. (zadatak 011, zamjenjuje 002; SCRUM-20, 21, 29, 30, 31, 33, 36, 37, 41): frontend usklađen s API-jem na `main` (razina tekstom + ikonom, `all_no_data` → "nema podataka za ovu lokaciju", izvor i `source.note` na svakoj kartici, decimalni zarez, stranica Izvori iz `/api/sources` s pravilima prema SPEC §6), uklonjen `sw.js` i unpkg, CI dobio `frontend` posao (`npm ci && npm run build`). HV sloj na karti: CORS u redu, iscrtava se samo na zumu 12–14. Na `main`: 196 testova prolazi, build prolazi. Nije provjereno uživo: EFAS kartica (u Gunji odgovara HV), greška 422 i nedostupan geokoder. Otvoreno: dvostruka napomena na ESHM20 kartici, zaštita od zastarjelog odgovora, OSM pločice (SCRUM-42).

`docs/PLAN.md` je zajednički zapis statusa za tim (`CLAUDE.md` je lokalan, u `.gitignore`).
