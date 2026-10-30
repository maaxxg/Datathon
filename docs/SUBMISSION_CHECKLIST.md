# SUBMISSION_CHECKLIST — Geo-rizik

Rok: **9. 11. 2026. u 24:00**, isključivo e-poštom na **open.data@mpudt.hr**. Ciljamo slanje do 18:00. Bez videa se rješenje ne ocjenjuje.

## Sadržaj predaje (Pravila, VIII.)

- [ ] Poveznica na javni repozitorij (GitHub) s licencom (MIT; izvedeni EFAS podaci pod ODbL)
- [ ] README: opis, pokretanje (Docker Compose), arhitektura, ograničenja
- [ ] Tehnička i projektna dokumentacija: `ARCHITECTURE.md`, `SPEC.md`, `DATA_INVENTORY.md`, `DECISIONS.md`
- [ ] **Popis svih skupova podataka s izdavačima i poveznicama** (iz `layers.yaml`)
- [ ] **Popis svih alata i biblioteka, uključujući AI alate** (otvoreni LLM: naziv i verzija; AI asistenti korišteni u razvoju)
- [ ] Demo: poveznica na radni prototip + snimke zaslona (početna, izvještaj, istraži, mobilni prikaz)
- [ ] Video ≤ 3 min (poveznica ako je datoteka prevelika; dostupna barem do objave rezultata 17. 11.)
- [ ] Provjera: rješenje je izvorno djelo tima; licence podataka poštovane i navedene
- [ ] Privola za javnu objavu videa (daje se u prijavnom obrascu)

## Predložak e-pošte

**Predmet:** Datathon 2026 – Izazov B – [naziv tima] – rješenje „Geo-rizik"

Poštovani,

u ime tima [naziv tima] (mentor: [ime i prezime], [fakultet]) dostavljamo rješenje za izazov B: Okoliš i održivi prostor.

- Repozitorij: [poveznica]
- Radni prototip: [poveznica]
- Video (do 3 min): [poveznica]
- Dokumentacija i popis skupova podataka: [poveznica na mapu docs/ u repozitoriju]

Članovi tima: [ime i prezime, studij] × 4

Molimo potvrdu primitka.

Srdačan pozdrav,
[ime i prezime], voditelj tima

## Skripta za video (≤ 3:00)

| Vrijeme | Sadržaj | Slika |
|---|---|---|
| 0:00–0:20 | **Problem:** kupujete kuću na Banovini, a podaci o poplavama i tlu su razbacani i stručni | snimke Petrinje / ortofoto nakon potresa |
| 0:20–0:35 | **Korisnici:** kupci i najmoprimci; općine i projektanti | tekst na ekranu |
| 0:35–1:25 | **Demo glavnog scenarija:** unos adrese u Petrinji → izvještaj → najznačajniji rizik → objašnjenje → izvori → PDF | snimka ekrana |
| 1:25–2:00 | **Istraži:** "pronađi područja oko Petrinje bez poplava i s niskom podložnosti klizištima" → filteri → karta; poruka o onome što nije moguće | snimka ekrana |
| 2:00–2:25 | **Izvori podataka:** data.gov.hr (DGU, MPGI), Hrvatske vode, EFAS, ESHM20; povezivanje OGC/INSPIRE servisa | dijagram izvora |
| 2:25–2:45 | **Arhitektura:** deterministička ocjena + otvoreni LLM samo za prevođenje upita; otvoreni kod, API | dijagram arhitekture |
| 2:45–3:00 | **Vrijednost i daljnji razvoj:** proširenje geohazarda na cijelu RH kad podaci postanu dostupni, ugradnja u općinske portale | završni ekran |
