# E7 — lista podpisów PDF

Data: 2026-11-07. Stan: zaimplementowany i sprawdzony lokalnie. Bez commita, publikacji ani wdrożenia Home Assistant. D7 było już zatwierdzone; etap nie wymagał nowych decyzji użytkownika ani migracji bazy.

## Odbiór

| Kryterium | Realizacja i dowód |
| --- | --- |
| Wyłącznie faktycznie obecni | Zapytanie po Attendance.confirmed_state=present; brak deklaracji, rezerwy i nieobecnych. Przed zatwierdzeniem obecności API odmawia 409; przycisk jest nieaktywny. Odwołanie także daje 409 |
| Dane dla szkoły | Data i lokalne godziny spotkania, I LO w Gdańsku, liczba obecnych; tabela Lp., imię i nazwisko, podpis. Bez przydomków, statusów, punktów i powodów korekt |
| Aktualizacja po korekcie | Każdy GET tworzy nowy PDF z bieżącego snapshotu obecności. W E2E stara karta podglądu pobiera po korekcie listę 13 osób zamiast wcześniejszych 14; usunięta osoba i prywatny powód nie trafiają do dokumentu |
| Prywatność i uprawnienia | Rola administratora sprawdzana w backendzie i trasie frontendu. Zwykły gracz 403, anonimowy 401, nieznane spotkanie 404. Test również dla ?download=true. Wszystkie odpowiedzi no-store |
| Spójność odczytu | Ta sama blokada Meeting co przy korektach/dopisywaniu; pobranie rewizji i nazwisk przed zwolnieniem blokady. Generowanie z niezmiennego snapshotu w puli wątków. Eksport nie zmienia wersji spotkania ani obecności |
| Polskie znaki i font | Noto Sans Regular/Bold dostarczone z backendem, z licencją OFL i źródłem/hashami; osadzone w PDF. Odczyt pypdf oraz wizualna kontrola Poppler: ł, Ł, ś, ć, ń, ó, ą, ę, ż, ź w nazwiskach bez uszkodzonych glifów |
| A4 i długie nazwiska | Zwykła lista 14 osób z nazwiskiem Brzęczyszczykiewicz-Kowalska mieści się na jednej stronie. Wiersze min.14 mm i szeroka kolumna podpisu. Skrajny test 80 znaków imienia + 80 nazwiska dla 14 osób daje dwie strony A4; nagłówek powtórzony, wszystkie nazwiska i pozycje zachowane |
| Podgląd i pobranie | „Lista podpisów” w nagłówku panelu organizatora prowadzi do osobnego widoku. Rzeczywisty PDF renderowany przez lokalny PDF.js na canvas, z tekstem dla czytników ekranu. Pobranie z sensowną nazwą pliku, odświeżenie, osobna karta i powrót do spotkania |
| Telefon i błędy | Chromium desktop oraz emulacja telefonu 360/390/430 px, bez poziomego overflow. Sprawdzony rzeczywisty wyrenderowany canvas, pobieranie i błąd sieci → odświeżenie → ponowny podgląd. Nie polegamy na wbudowanym pluginie PDF, który w emulacji telefonu wyświetlał pustą ramkę |
| Brak zewnętrznego generatora | ReportLab i fonty lokalne. PDF.js i worker w buildzie aplikacji, bez CDN. Runtime nie używa Popplera ani serwisu zewnętrznego i nie zapisuje archiwum PDF na dysku |

## Implementacja

- `backend/app/services/signature_list.py`: kontrolowany snapshot i generator A4; nazwy sortowane po nazwisku, imieniu i ID, bez ID na wydruku. Tekst użytkownika jest escapowany przed Paragraph, więc znaczniki nie stają się formatowaniem/linkami. Serializacja renderowania w puli wątków chroni współdzieloną rejestrację fontów ReportLab; test równoległych dokumentów nie miesza nazwisk.
- `backend/app/api/documents.py`: `GET /api/v1/admin/meetings/{id}/signature-list`, application/pdf, inline domyślnie lub attachment dla download=true, `X-Attendance-Revision`, nosniff. Odmowy mają standardowy format błędów aplikacji.
- `frontend/src/features/documents/SignatureList.tsx`, `PdfViewer.tsx`: autoryzowana trasa, aktualne pobranie, podgląd wszystkich stron, loading/error/retry, ostrzeżenie przy innej rewizji obecności. URL-e Blob są zwalniane, pobieranie anulowane przy opuszczeniu strony; parser/worker niszczony przy zmianie dokumentu. Brak trwałego cache dokumentu w aplikacji.
- Zależności i lockfile: ReportLab **4.5.1**, pypdf **6.21.4** wyłącznie w dev/test, PDF.js **6.5.438** ładowany dynamicznie dopiero przy podglądzie. Fonty z przypiętego commita Noto, licencja i sumy SHA-256 w `backend/app/assets/fonts/README.md`.
- Kontrakt OpenAPI oraz typy klienta wygenerowane; API, domena, frontend i README zaktualizowane. Bez zmian modelu danych/migracji.

## Wykonane testy

macOS arm64, Python 3.13.18, PostgreSQL 14.24 na porcie 55432; testy na izolowanej `volleycrew_test`. Bez danych produkcji i maybe-finance.

- `npm run lint` — Ruff, format Pythona, ESLint i Prettier poprawnie.
- `npm run typecheck`, `npm run api:check`, `npm run build` — poprawnie. Build emituje osobny chunk parsera i lokalny worker PDF.js.
- `VOLLEYCREW_TEST_DATABASE_URL=<baza *_test> npm run test:backend -- -x --tb=short` — **91 zaliczonych**, w tym **6 testów E7**: A4/14 nazwisk/font, pusta lista i literalne znaczniki, skrajne długości z paginacją, równoległy rendering, uprawnienia i stan obecności, aktualizacja po korekcie/niezmienność źródła, rezerwa/odwołanie/404. Ostrzeżenie zależności Starlette o przyszłym transporcie TestClient pozostaje bez zmian.
- `npm run test:frontend` — **1 test Vitest zaliczony**; funkcje E7 sprawdzone dodatkowo w E2E z rzeczywistym API i PostgreSQL.
- `VOLLEYCREW_E2E_DATABASE_URL=<baza *_test> npm run test:e2e` — **12 zaliczonych**, regresja E2–E6 i rozszerzony scenariusz sali o listę PDF, pobranie/odczyt pypdf dla 14 i 13 osób, odmowę dla gracza, błąd sieci i ponowienie. Dodatkowe uruchomienie samego `room.spec.ts` kontroluje canvas i screenshoty po zakończeniu renderowania.
- `npm --prefix volleycrew/frontend audit` i `audit --omit=dev` — **0 zgłoszonych podatności** dla bieżącego lockfile.

Chromium **158.0.8127.18**, desktop 1440 px i emulacja Pixel 7 z kontrolą 360/390/430 px. Poppler **26.11.0** służył do rasteryzacji PDF i wizualnej kontroli wszystkich stron. Nie wykonano fizycznego druku, próby na rzeczywistym telefonie ani Safari/iOS.

Przykłady QA z wyłącznie fikcyjnymi nazwiskami (ignorowane w git): `output/pdf/e7-lista-podpisow-przyklad.pdf`, `e7-lista-podpisow-skrajne-nazwiska.pdf` oraz wyrenderowane `e7-przyklad-1.png`, `e7-skrajne-{1,2}.png`. Odtworzenie: `python3 -c 'import scripts.dev as d; d.run(d.backend("python", "-m", "tests.test_signature_list"))'`.

Dowody E2E (ignorowane w git): `volleycrew/frontend/test-results/room-attendance-court-swap-fbfa0--PDF-and-private-correction-{desktop,mobile}/signature-before.pdf`, `signature-after.pdf`, `signature-preview-{1440,360,390,430}.png`. Screenshoty wykonywane po zakończeniu renderowania podglądu.

## Dalsze zależności

Następny etap po zleceniu: **E8 — wyniki, ELO i korekty**. Pozostają decyzje D8: skala oczekiwań, korekty historycznych składów i kolejność spotkań o tej samej dacie. K=32, brak pośredniego zaokrąglania, 0:0 i korekty wyniku z przeliczeniem późniejszych spotkań są już zatwierdzone. Nie rozszerzano E7 o te reguły.

Próby fizycznych telefonów i Safari — E9. CI/PostgreSQL 17, docelowy obraz z fontami, Pi 4/aarch64, amd64, Ingress z dynamicznym prefiksem (również worker PDF.js), backup/restore i instalacja HA — E10. Zielony build lokalny nie oznacza gotowego wdrożenia.

## Źródła techniczne

- [ReportLab: tabele i powtarzane nagłówki](https://docs.reportlab.com/reportlab/userguide/ch7_tables/).
- [Noto Sans — przypięte źródło i licencja](https://github.com/notofonts/noto-fonts/tree/ffebf8c1ee449e544955a7e813c54f9b73848eac/hinted/ttf/NotoSans).
- [PDF.js — przykłady renderowania](https://mozilla.github.io/pdf.js/examples/) oraz typy API z zainstalowanego pdfjs-dist.
