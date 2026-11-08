# E4 — deklaracje, priorytety i rezerwa

Data: 2026-11-06. Stan: zaimplementowany i sprawdzony lokalnie. Bez commita, publikacji i wdrożenia HA. Obowiązują zatwierdzone D2/D3/D6 i granica czasu konkretnego spotkania. Brak nowych niezatwierdzonych reguł produktu.

## Odbiór E4

| Kryterium | Realizacja / dowód |
| --- | --- |
| Deklaracje i limit 14 | PUT „będę/nie będę”, DELETE wycofania, osobna rezerwa i rezerwacje. Każda zmiana alokacji blokuje Meeting przez SELECT FOR UPDATE. Testy dwóch HTTP i dwóch niezależnych transakcji DB dowodzą 14 miejsc przy równoczesnych zapisach |
| Trzy prywatne statusy | Założyciel > zawodnik > gość, wewnątrz statusu czas i numer kolejki. Testy wszystkich relacji poziomów i niezależności od roli administratora. DTO grupy nie zawiera priorytetu |
| Wypieranie i granica 24 h | Nowe zgłoszenie lub zmiana statusu może przeliczyć miejsca wyłącznie przed granicą. Od granicy istniejące miejsca są chronione, nadal można zapisać się na wolne. Dokładnie na granicy rezygnacja jest zwykła. Czas jest odczytywany po uzyskaniu blokady, nie przed oczekiwaniem |
| Powtórzenia | Idempotency-Key, osobne trwałe receipts i fingerprint treści. Powtórzenie nie zmienia czasu, numeru kolejki ani historii i nie wznawia zgłoszenia po późniejszym wycofaniu. Ponowny świadomy zapis po wycofaniu dostaje nowy czas i numer |
| Rezerwacja wolnego miejsca | Pierwsza osoba z kolejki otrzymuje rezerwację natychmiast po zwolnieniu miejsca, przed propozycją. Nowe zgłoszenie nie przejmuje rezerwacji. Kilka miejsc daje osobne rezerwacje różnym osobom |
| Jawna propozycja i przyjęcie | Administrator aktywuje propozycję i kontaktuje się ręcznie na Messengerze. Dopiero adresat akceptujący aktualną propozycję trafia do uczestników. Brak automatycznego timeoutu; nie można przyjąć cudzej, zamkniętej, starej lub dotyczącej innego terminu propozycji |
| Odmowa / przekazanie dalej | Odmowa lub ręczne zamknięcie za brak odpowiedzi wycofuje zgłoszenie bez oznaczenia późnej rezygnacji/nieobecności. Miejsce czeka na kolejną osobę. Powtórzone przyjęcie/zamknięcie nie dubluje skutków |
| Wyjątek późnej oferty | Przyjęcie w ostatnich 24 h zapisuje flagę i zdarzenie z czasem/ID oferty. Późniejsza zgłoszona rezygnacja ma wyjątek; zwykły późny zapis go nie dostaje. E6 nie może stosować tego wyjątku do no-show |
| Zmiana statusu i blokada | Administrator zmienia prywatny status w ustawieniach. Przeliczenie zachowuje pierwotną kolejność i rezerwacje. Blokada w tej samej transakcji unieważnia sesje/granty, zwalnia wszystkie przyszłe miejsca/rezerwacje/oferty i obsługuje kolejkę; przeszłe zapisy pozostają. Wyścig blokada/przyjęcie nie przywraca miejsca |
| UI telefonu | Karta udziału nad uczestnikami, miejsce na rezerwie, osobne liczniki potwierdzonych/wolnych/zarezerwowanych, potwierdzenie rezygnacji, panel ofert organizatora i prywatny selektor statusu. Brak sukcesu przed odpowiedzią API; po błędzie/konflikcie odświeżenie i komunikat |

Migracja `0004_enrollment` dodaje `reservation_kind` (offer/reconfirmation), SeatOffer, EnrollmentEvent i EnrollmentMutation. Stan `reserved` w ofercie oznacza chronione miejsce przed aktywacją propozycji; `pending` oznacza propozycję czekającą na odpowiedź. Końcowe stany to accepted/declined/closed/revoked. Brak automatycznego „expired po N minutach”, zgodnie z D2.

## Ważne szczegóły

Rezygnacja i odpowiedź na ofertę uzupełniają wakaty, zachowując pozostałe miejsca. Samo przyjęcie propozycji nie uruchamia ponownego wypierania osoby, która właśnie zaakceptowała rezerwację. Pełne przeliczenie przed granicą następuje po nowym zgłoszeniu i zmianie statusu; aktywne rezerwacje pozostają chronione. Testy wykryły i zabezpieczyły ten przypadek.

Rezygnacja po granicy wymaga `acknowledge_late=true`, jeśli serwer wyliczy rzeczywiście późną rezygnację. Gdy granica minęła pomiędzy podglądem i zatwierdzeniem, API odrzuca niepotwierdzoną późną rezygnację, a UI odświeża informację przed kolejnym potwierdzeniem. Klasyfikacja normal/late/late_offer_exception/none jest zapisana w prywatnym EnrollmentEvent. Nie utworzono jeszcze pełnej AttendanceEvent ani widoku historii — to E6, które ma wykorzystać te źródła bez dublowania zdarzeń.

Globalna transakcyjna blokada tożsamości z E2 pozostaje przed blokadą Meeting, dzięki czemu blokada profilu i zapis/akceptacja współpracują także przy wielu procesach. Poprawność limitu nie zależy wyłącznie od niej: testy bez tego globalnego mechanizmu używają osobnych sesji DB i wspólnej blokady Meeting. Zmiana statusu/blokada wielu przyszłych terminów pobiera je w stabilnej kolejności ID. Po odblokowaniu stare sesje i deklaracje nie wracają.

## Kontrakt HTTP

Wszystkie ścieżki pod `/api/v1`, wymagają sesji; mutacje również CSRF/Origin.

- `GET /meetings/{id}/my-participation` — wyłącznie własna deklaracja, alokacja, pozycja, ewentualna oferta, termin zwykłej rezygnacji i jej aktualna klasyfikacja.
- `PUT /meetings/{id}/my-declaration` — `{declaration: going|not-going, term_version, acknowledge_late?}`.
- `DELETE /meetings/{id}/my-declaration` — `{term_version, acknowledge_late?}`.
- PUT i DELETE wymagają nagłówka `Idempotency-Key` z UUID. Ten sam klucz w obrębie gracza/spotkania i inna treść daje 409. Retry zwraca stan aktualny, nie historyczny snapshot miejsca.
- `GET /admin/meetings/{id}/offers` — rezerwacje i propozycje organizatora.
- `POST /admin/meetings/{id}/offers` — `{player_id, term_version}`; wyłącznie dla istniejącej rezerwacji, ponowienie aktywnej propozycji zwraca ten sam obiekt.
- `POST /offers/{id}/accept` i `/decline` — `{term_version}`; wyłącznie adresat.
- `POST /admin/offers/{id}/close` — `{term_version, reason: no-response}`; ręczne przekazanie dalej.
- `PATCH /admin/players/{id}` — `is_active?` i/lub `priority_status?`; żadna z tych operacji nie zmienia roli administratora.

Mutacje deklaracji/odpowiedzi zwracają aktualne `meeting` i `participation`. Listy grupowe nie zawierają cudzych priorytetów, zdarzeń rezygnacji ani wyjątków. Szczegóły i kalendarz pokazują dodatkowo `reserved_count` i `free_count`; 13 uczestników i 1 rezerwacja oznaczają 0 wolnych miejsc, a nie wolny zapis na ostatnie miejsce.

## Weryfikacja lokalna

macOS arm64, Python 3.13.18, PostgreSQL 14.24; izolowana `volleycrew_test` na 55432. Brak dostępu testów do dev/maybe-finance. Testy backendu i E2E wykonywane sekwencyjnie na tej samej jawnej bazie testowej.

- `npm run lint` — Ruff, ESLint, Prettier poprawnie.
- `npm run typecheck` i `npm run build` — poprawnie.
- `npm run api:check` — kontrakt i typy zgodne z API.
- `VOLLEYCREW_TEST_DATABASE_URL=<baza *_test> npm run test:backend` — **52 zaliczone**, w tym 17 przypadków E4: różne priorytety, limit, last-seat race, równoczesne przyjęcia i nowy zapis, blokada/przyjęcie, zachowanie historii, receipts, granice czasu, wyjątek późnej oferty i oczekiwanie na blokadę aż do startu. Jedno ostrzeżenie biblioteki Starlette dotyczące przyszłej zmiany transportu TestClient, bez błędu testów.
- `npm run test:frontend` — **1 test Vitest zaliczony**; zachowanie E4 sprawdza prawdziwa przeglądarka i API.
- `VOLLEYCREW_E2E_DATABASE_URL=<baza *_test> npm run test:e2e` — **8 zaliczonych**, wcześniejsze ścieżki E2/E3 i nowa rejestracja → dalszy termin → rezerwa → rezygnacja organizatora → propozycja → jawne przyjęcie na drugim urządzeniu → refresh z 14 uczestnikami → prywatna zmiana statusu.
- Alembic `check` na testowej DB — `No new upgrade operations detected`.

Jedno z uruchomień E2E zakończyło się timeoutem po odświeżeniu odwołanego spotkania w istniejącym scenariuszu kalendarza. Pełne ponowienie bez zmiany kodu i limitów czasu zaliczyło wszystkie 8 testów. Przyczyny nie odtworzono; obserwować ten scenariusz w CI.

Chromium 158, desktop 1440 px i emulacja telefonu 360/390/430 px. Brak poziomego overflow w nowych kartach; wizualnie sprawdzono kartę rezerwy 360 px oraz mobilny panel aktywnej propozycji. Screenshoty w ignorowanym `volleycrew/frontend/test-results/enrollment-distant-signup--04825-cceptance-on-another-device-{desktop,mobile}/`: `reserve-*.png` i `organizer-offer.png`. Fizyczny telefon i Safari nadal nie były testowane.

## Pozostałe zależności

- E5: zmiana/odwołanie terminu, nowe potwierdzenia D4, ponowne propozycje po każdej zmianie, ochrona rezerwacji i ręczne zwolnienie przy braku potwierdzenia. `reservation_kind=reconfirmation` jest fundamentem, nie gotowym procesem E5. E5 musi unieważniać stare granty w tej samej transakcji i zachowywać kolejność; obecne endpointy odrzucają niezgodną wersję.
- E6: prywatna historia obecności z korektami i no-show, przy wykorzystaniu EnrollmentEvent. Nie generować nieobecności dla odwołania/odmowy oferty/rezerwy. Wyjątek późnej oferty nie usprawiedliwia no-show.
- E9/E10: fizyczne przeglądarki, PostgreSQL 17/CI, Home Assistant/Ingress, Pi 4 oraz backup/restore nadal wymagają rzeczywistego odbioru. Obecny etap nie jest wydaniem produkcyjnym.

Następny gotowy zakres po zleceniu: **E5 — zmiana harmonogramu i odwołanie**.
