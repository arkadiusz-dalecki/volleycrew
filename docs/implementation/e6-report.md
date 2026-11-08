# E6 — obecność, prywatna historia i drużyny na boisku

Data: 2026-11-06. Stan: zaimplementowany i sprawdzony lokalnie. Bez commita, publikacji i wdrożenia Home Assistant.

Użytkownik zatwierdził podział dla 2–14 osób, maksymalnie po 7 i z różnicą liczebności najwyżej 1; ponowne otwarcie składów przed wynikiem z powodem; zwalnianie miejsc nieobecnych z zachowaniem rezerwy, potwierdzanie fizycznie obecnego adresata rezerwacji oraz powrót spóźnionego przez korektę przy dostępnym miejscu. Decyzje zapisano w `decisions.md`, reguły w `domain-api.md`, interfejs w `frontend.md`.

## Odbiór E6

| Kryterium | Realizacja i dowód |
| --- | --- |
| Szkic i świadome zatwierdzenie | Szkic nie tworzy historii; nieustalone osoby blokują zatwierdzenie. Zatwierdzenie dopiero od startu, w osobnej potwierdzanej operacji. Test braku no-show przed zatwierdzeniem i blokady przed startem |
| Klasyfikacja historii | Zwykła/późna rezygnacja, wyjątek późnej oferty i no-show są oddzielne. Migracja przenosi wcześniejsze klasyfikowane rezygnacje z EnrollmentEvent; kolejne są zapisywane atomowo ze zdarzeniem źródłowym. Wyjątek późnej oferty nie usprawiedliwia no-show — osobne testy obu ścieżek |
| Miejsca po sprawdzeniu obecności | Nieobecny traci alokację bez utraty źródłowej deklaracji i historii. Rebalans pomija nieobecnych, rezerwując miejsce dla kolejnej osoby; nie przyjmuje jej automatycznie. Niepotwierdzona zmiana terminu nie tworzy no-show |
| Obsługa rezerwy na sali | Organizator potwierdza fizycznie obecnego adresata jego rezerwacji albo ręcznie przekazuje ją dalej. Inny profil nie przejmuje tego miejsca. Brak automatycznych timeoutów i oznaczeń nieobecności dla samej rezerwacji |
| Dopisanie i spóźnienie | Aktywny istniejący profil, wolne niezarezerwowane miejsce, limit 14 i audyt. Spóźniony wcześniej oznaczony nieobecnym wymaga korekty z powodem. Dwie niezależne sesje PostgreSQL próbujące ostatniego miejsca: jedna akceptacja, drugi konflikt wersji; łącznie 14 |
| Prywatna historia i korekty | Własny profil oraz administracyjny odczyt danego gracza z paginacją. Korekta nie nadpisuje źródła, zachowuje autora/czas/powód. Zwykły gracz otrzymuje 403 dla cudzej historii i wszystkich administracyjnych mutacji. Brak prywatnych pól w publicznym boisku i liście uczestników |
| Dwa generatory | Losowy z kontrolowanym źródłem w testach; wyrównany przegląd kombinacji minimalizujący różnicę średnich, deterministyczny tie-break. Testy 2/3/11/12/13/14 osób, odrzucenie 0/1/15. W E6 rzeczywista baza 1000, bez fikcyjnego rankingu |
| Członkostwo i liczebność | Każdy faktycznie obecny dokładnie raz, nikt nieobecny; max.7 na stronę, różnica ≤1. Backend odrzuca duplikaty, brakujące i nieprawidłowe osoby. Podział, poprawki, zatwierdzenie i korekty sprawdzone dla 11–14 |
| Boisko wariantu A | Dwie połowy, pełne nazwiska, siódma osoba w rotacji. Na telefonie połowy pionowo; na szerszej karcie poziomo. Zamiana przez dotknięcie dwóch osób, również obu rotujących przy 7:7. Zapis ręcznych poprawek przed zatwierdzeniem, odtworzenie po reload |
| Szkic i publikacja | Szkic tylko dla organizatora; grupa widzi wyłącznie zatwierdzone drużyny. Otwarcie z powodem archiwizuje poprzedni skład i tworzy nowy szkic. Zmiana faktycznej obecności wymaga uprzedniego otwarcia składów i unieważnia ich szkic; zakończony mecz blokuje zmianę fizycznej obecności do E8 |
| Wersje i ponowienia | Meeting FOR UPDATE, expected_version i trwały Idempotency-Key obejmują wszystkie mutacje sali. Testy ponowień potwierdzenia obecności/składów i losowania bez dodatkowego skutku. E2E gubi odpowiedź po rzeczywistym zapisie losowania: ponowienie odzyskuje tę samą rewizję |
| Regresja harmonogramu | Zmiana terminu/odwołanie usuwa niezatwierdzony szkic; rezygnacja znika z bieżącej listy kandydatów. Całe wcześniejsze testy E2–E5 pozostają zaliczone |

## Kod i API

Migracja `0006_room` dodaje Attendance, AttendanceEvent, TeamSheet, TeamMember, RoomMutation oraz rewizje sali w Meeting. Aktualna rewizja obecności jest zapisana ze szkicem drużyn; walidacja przy zatwierdzeniu ponownie sprawdza kompletność członkostwa. Poprzednie zatwierdzone składy i wpisy historii nie są nadpisywane. Downgrade z danymi obecności/historii/składów jest celowo blokowany; powrót wymaga zgodnego backupu.

Endpointy i schematy: `backend/app/api/room.py`, `room_schemas.py`; transakcje: `services/room.py`; czysty generator: `domain/teams.py`. Wszystkie endpointy są pod `/api/v1`, administracyjne wymagają faktycznej roli i CSRF. Publiczny dla zalogowanej grupy odczyt `/meetings/{id}/teams` zwraca zatwierdzony skład albo null; historia nigdy nie jest do niego dołączana. Kontrakt OpenAPI i typy frontendu są wygenerowane.

Frontend: `features/room/RoomPanel.tsx`, `Court.tsx`, `HistoryPanel.tsx`, `useRoomAction.ts`. Sukces dopiero po odpowiedzi, zachowanie operacji do ponowienia po utracie odpowiedzi, odświeżenie po konflikcie bez cichego nadpisania lokalnych poprawek. Własny profil zawiera historię; organizator otwiera `/admin/players/:playerId/history` z ustawień lub listy obecności.

## Wykonane sprawdzenia

macOS arm64, Python 3.13.18, PostgreSQL 14.24 na 55432. Testy danych wyłącznie w dedykowanej `volleycrew_test`; bez bazy maybe-finance i produkcji. Migracja developerska wykonana w `volleycrew_dev`.

- `npm run lint` — Ruff, format Pythona, ESLint i Prettier poprawnie.
- `npm run typecheck`, `npm run api:check`, `npm run build` — poprawnie.
- `VOLLEYCREW_TEST_DATABASE_URL=<baza *_test> npm run test:backend -- -x --tb=short` — **85 zaliczonych**, w tym **22 przypadki E6**. Jedno ostrzeżenie zależności Starlette o przyszłej zmianie transportu TestClient.
- `npm run test:frontend` — **1 test Vitest zaliczony**. Przepływy E6 sprawdzone przeglądarkowo z rzeczywistym API i PostgreSQL.
- `VOLLEYCREW_E2E_DATABASE_URL=<baza *_test> npm run test:e2e` — **12 zaliczonych**, obejmują wcześniejsze E2–E5 oraz scenariusz sali desktop/mobile: obecność → utrata odpowiedzi po podziale → bezpieczne ponowienie → zamiana rotujących przy 7:7 → zapis/reload → zatwierdzenie/publiczne boisko → otwarcie z powodem → korekta obecności → własna historia i odmowa cudzej.
- Alembic `check` na dev i dedykowanej bazie testowej — `No new upgrade operations detected`.

Chromium **158.0.8127.18**: desktop 1440 px, emulacja Pixel 7 390 px i kontrola boiska przy 360/390/430 px, bez poziomego overflow. Screenshoty i wizualny odczyt pełnych/długich polskich nazwisk oraz rotacji. Nie wykonywano testu fizycznego telefonu ani Safari/iOS. W scenariuszu E6 sprawdzany też brak błędów renderowania i powielonych kluczy React.

Dowody w ignorowanym `volleycrew/frontend/test-results/room-attendance-full-court-fc31b-eams-and-private-correction-{desktop,mobile}/`: `court-1440.png`, `court-360.png`, `court-390.png`, `court-430.png` oraz zbliżenia `court-detail-*.png`. Seeder tworzy osobne trwające mecze wyłącznie w bazie `_test`.

## Pozostałe zależności

- **E7 — PDF z faktycznie obecnych** jest następnym gotowym etapem po zleceniu. D7 już zatwierdzone.
- **E8 — wyniki i ELO**: podłączenie punktów do generatora, wyniki/0:0 oraz zasady korekt historycznych składów, przeliczenia i skali oczekiwań. E6 nie zapisuje wyniku, nie zmienia ELO i nie edytuje fizycznej obecności zakończonego meczu.
- E9 obejmuje końcowe ujednolicenie całego interfejsu i próby na fizycznych telefonach.
- CI/PostgreSQL 17, instalowalny pakiet HA/Ingress, obie architektury, Pi 4 oraz rzeczywisty backup/restore pozostają do odbioru E10. Lokalne zielone testy nie oznaczają gotowego wydania produkcyjnego.
