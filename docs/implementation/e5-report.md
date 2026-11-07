# E5 — zmiana harmonogramu i odwołanie

Data: 2026-11-06. Stan: zaimplementowany i sprawdzony lokalnie. Bez commita, publikacji i wdrożenia Home Assistant.

D4 pozostaje obowiązujące: każda zmiana terminu wymaga nowego potwierdzenia, zachowując pierwotną kolejność i rezerwacje. W tej rozmowie użytkownik zatwierdził dodatkowo przenoszenie terminów na nowy dzień w tym samym tygodniu poniedziałek–niedziela, zachowanie odwołań oraz zachowanie indywidualnych wyjątków. Decyzja jest zapisana w `decisions.md`.

## Odbiór E5

| Kryterium | Realizacja i dowód |
| --- | --- |
| Podgląd od wybranej daty | Formularz administratora pokazuje istniejące terminy przed/po, liczbę nowych potwierdzeń, zachowane wyjątki i przykłady nowej reguły. Dopiero osobna akcja zatwierdza zapis |
| Wersje i ochrona dwóch kart | ScheduleState.version, Meeting.version oraz odcisk podglądu. Inna zmiana reguły, terminu lub zapisów po podglądzie daje 409 zamiast cichego nadpisania. Testy równoczesnych dwóch administratorów i starej karty |
| Istniejące i przyszłe wystąpienia | Reguła zmienia zarówno utrwalone spotkania, jak i przyszłe wyliczane terminy. Przyszłe zastąpione reguły pozostają w DB jako superseded, z zachowaniem FK; nie są nadal generowane |
| Stabilne ID bez duplikatów | Oryginalne źródło i ID Meeting pozostają bez zmian. Osobne aktualne powiązanie z wystąpieniem nowej reguły tłumi jego wirtualny odpowiednik. Stary i nowy klucz rozwiązują się do tego samego rekordu |
| Pojedynczy termin | Administrator wybiera datę/godzinę/czas gry, widzi skutki i zatwierdza. Powstaje indywidualny wyjątek; późniejsza zmiana stałej reguły go nie przesuwa |
| Ponowne potwierdzenia | Dotychczasowe seat stają się reserved/reconfirmation, bez automatycznego timeoutu. Potwierdzenie aktualnej wersji przywraca miejsce bez nowego czasu/sekwencji zgłoszenia. Rezerwa także potwierdza nowy termin; nie trafia automatycznie do uczestników |
| Dwie kolejne zmiany | Każda zwiększa term_version i unieważnia poprzednie potwierdzenie, także gdy użytkownik zdążył odpowiedzieć na wcześniejszą zmianę. Test potwierdzania w odwrotnej kolejności nie zmienia porządku listy |
| Oferty przy zmianie | Stare aktywne granty są revoked. Rezerwacja czeka pod nowym grantem w stanie reserved dla aktualnego terminu. Organizator ponownie proponuje miejsce; przyjęcie starego ID/wersji jest odrzucone |
| Ręczne zwolnienie | Administrator potwierdza zwolnienie miejsca oczekującego na nowe potwierdzenie. Zgłoszenie zostaje wycofane; kolejna osoba otrzymuje rezerwację zgodnie z D2. Brak automatycznego przyjęcia albo kary |
| Odwołanie | Przyszłe nierozpoczęte spotkanie pozostaje w kalendarzu/historycznym adresie jako cancelled. Wszystkie alokacje/oferty są zwalniane, deklaracje i zdarzenia zachowane. Nie powstaje no-show ani późna rezygnacja |
| UI A na telefonie | Ustawienia harmonogramu, panel pojedynczego terminu, stare/nowe daty, karta nowego potwierdzenia i osobna lista oczekujących. Potwierdzenia skutków i komunikaty konfliktów; powrót do aktualnego miesiąca |

## Model i transakcje

Migracja `0005_schedule_changes` dodaje:

- ScheduleState — globalna wersja ustawień.
- MeetingTermRevision — trwałe rewizje dat z autorem, czasem, poprzednim i nowym przedziałem oraz rodzajem zmiany.
- Meeting.calendar_schedule_id/calendar_source_date — aktualne powiązanie z harmonogramem, oddzielne od oryginalnego źródła tożsamości; unikalność w DB.
- Meeting.is_exception oraz poprzednie daty do bieżącego widoku starego/nowego terminu.
- Enrollment.reconfirmation_required — obejmuje także rezerwę i propozycje.
- ScheduleVersion.superseded i wykluczenie nakładających się przedziałów dla niezastąpionych wersji.

Kolejność blokad: tożsamość z E2 → stan harmonogramu → reguła/Meeting. Resolver pobiera współdzieloną blokadę stanu przed materializacją, dzięki czemu w trakcie zbiorczej zmiany nie powstaje pominięty rekord starej reguły. Kalendarz pobiera współdzieloną blokadę, aby nie mieszać starej reguły z już przesuniętymi rekordami. Mutacje wszystkich alokacji nadal stosują blokadę Meeting z E4.

Podgląd nie zmienia DB. Przy zatwierdzeniu jest liczony ponownie; porównanie tokenu uwzględnia treść żądania, wersje/stan istniejących spotkań i obowiązujące reguły. W międzyczasie nowy zapis lub otwarcie terminu może zmienić zakres — administrator otrzymuje konflikt i robi nowy podgląd. Ponowne potwierdzenie udziału ma Idempotency-Key i aktualną term_version jak deklaracje E4.

## Granice i kolizje

Zmiana stałej reguły zastępuje zaplanowane reguły od wybranej daty, zachowując wcześniejszą historię. Zachowane indywidualne daty są wyraźnie oznaczone w podglądzie i nie dostają nowego żądania potwierdzenia, jeśli ich termin rzeczywiście się nie zmienił. Odwołane pozostają odwołane także po przesunięciu wynikającym z nowej reguły.

Nowy dzień jest wyliczany w tym samym tygodniu poniedziałek–niedziela. Jeżeli przeniósłby utrwalony termin przed datę obowiązywania albo w przeszłość, podgląd blokuje zmianę i sugeruje początek tygodnia lub inny zakres. Nie scala ani nie usuwa zgłoszeń. Kolizje są sprawdzane także z jeszcze niewytworzonymi terminami reguły: brak rekordu w DB nie oznacza wolnego przedziału. Zachowany wyjątek z innego tygodnia nie może zdublować nowego wirtualnego spotkania.

Nieistniejąca lub niejednoznaczna lokalna godzina w dniu DST jest jawnie odrzucana. Dla stałej reguły sprawdzamy pełny 400-letni cykl kalendarza według zainstalowanej Europe/Warsaw. Nie wprowadzono niezatwierdzonego automatycznego przesuwania 02:30. Normalne przejścia DST nadal utrzymują lokalną godzinę; testy E3 pozostają zielone. Aktualność tzdata i działanie na Pi 4 należą do odbioru E10.

Zmiany dotyczą przyszłych nierozpoczętych spotkań; zakończone/obsługiwane spotkania nie są edytowane tą ścieżką. Ręczne zwolnienie oczekującego miejsca również dotyczy przyszłego terminu. E6 musi uwzględnić obsługę niepotwierdzonych zgłoszeń podczas faktycznej obecności, bez automatycznego no-show dla samego braku nowego potwierdzenia.

## API

Wszystkie endpointy poniżej wymagają roli administratora; mutacje również CSRF i Origin.

- `GET /api/v1/admin/schedule` — wersja i niezastąpione reguły.
- `POST /admin/schedule/preview` — expected_version, effective_from, weekday (0–6), local_time, duration_minutes, venue; podgląd i preview_token.
- `POST /admin/schedule/versions` — ta sama treść oraz preview_token; zapis po ponownej weryfikacji.
- `POST /admin/meetings/{id}/reschedule` — expected_version, local_date, local_time, duration_minutes.
- `POST /admin/meetings/{id}/cancel` — expected_version.
- `POST /admin/meetings/{id}/release-reconfirmation` — expected_version i player_id.

Własna karta E4 udostępnia needs_reconfirmation. Szczegóły grupowe pokazują previous_starts_at/previous_ends_at, is_exception i awaiting_confirmation, bez cudzych priorytetów lub prywatnej historii. Własne potwierdzenie nadal używa PUT /meetings/{id}/my-declaration z going i aktualną wersją terminu; przy propozycji z rezerwy jawne przyjęcie musi dotyczyć nowej oferty.

## Weryfikacja lokalna

macOS arm64, Python 3.13.18, PostgreSQL 14.24 na izolowanym porcie 55432; testy wyłącznie w `volleycrew_test`. Nie używano dev do danych testowych, bazy maybe-finance ani produkcji.

- `npm run lint` — Ruff/ESLint/Prettier poprawnie.
- `npm run typecheck`, `npm run api:check`, `npm run build` — poprawnie.
- `VOLLEYCREW_TEST_DATABASE_URL=<baza *_test> npm run test:backend` — **63 zaliczone**, w tym 11 przypadków E5: pojedynczy i zbiorczy termin, dwa przesunięcia, kolejność potwierdzeń, stare oferty, zwolnienie rezerwacji, odwołanie bez nieobecności, zachowanie wyjątków, zastąpienie przyszłych reguł/FK, konflikt podglądu i dwóch administratorów, DST/granica zakresu oraz kolizje wirtualnych terminów. Jedno ostrzeżenie zależności Starlette o przyszłej zmianie transportu TestClient.
- `npm run test:frontend` — **1 test Vitest zaliczony**. Główne ścieżki sprawdza przeglądarka z prawdziwym API.
- `VOLLEYCREW_E2E_DATABASE_URL=<baza *_test> npm run test:e2e` — **10 zaliczonych**: wcześniejsze E2–E4 i nowy scenariusz pojedynczego wyjątku → nowego potwierdzenia → podglądu nowej reguły → zachowania wyjątku → kolejnego potwierdzenia → odmowy starej karty → odwołania w kalendarzu.
- Alembic `check` — `No new upgrade operations detected`.

Chromium 158: desktop 1440 px i emulacja telefonu 390 px; wcześniejsze scenariusze nadal kontrolują 360/390/430 px. Nowa karta ponownego potwierdzenia bez poziomego overflow. Wizualnie sprawdzono mobilną kartę starego/nowego terminu oraz układ podglądu. Screenshoty w ignorowanym `volleycrew/frontend/test-results/schedule-single-exception--045e9-anizer-tab-and-cancellation-{desktop,mobile}/`: `schedule-preview.png`, `reconfirmation.png`. Brak testu fizycznego telefonu/Safari.

## Dalsze zależności

- E6: obecność, prywatna historia i korekty, drużyny i boisko. Zdarzenia anulowania/zmiany oraz stany oczekiwania nie mogą stać się automatycznymi nieobecnościami.
- E8: nadal otwarte szczegóły historycznych składów i skali oczekiwań zgodnie z D8; nie blokują E6.
- CI z PostgreSQL 17, obrazy CPU, docelowe HA/Ingress, Pi 4 i backup/restore nadal czekają na rzeczywisty odbiór. Nie deklarujemy wydania produkcyjnego.
- Migracja 0005 odmawia downgrade po zapisaniu zmian E5, aby nie utracić ich powiązań/historii. Cofnięcie wdrożenia wymaga zgodnego backupu bazy i obrazu; procedura i rzeczywisty restore to E10. Nie wykonano destrukcyjnego rollbacku ani kasowania danych użytkownika.

Następny gotowy etap po zleceniu: **E6 — obecność i drużyny**.
