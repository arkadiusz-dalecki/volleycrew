# E3 — modele spotkań i kalendarz

Data: 2026-11-06. Stan: zaimplementowany i sprawdzony lokalnie. Bez wdrożenia HA, commita ani publikacji. Etap obejmuje terminy i ich odczyt; deklaracje uczestnictwa i alokacja miejsc należą do E4.

## Odbiór E3

| Kryterium | Realizacja i dowód |
| --- | --- |
| ScheduleVersion, Meeting, Enrollment | Migracja `0003_meetings`: wersje harmonogramu z wykluczeniem nakładających się przedziałów, unikalny termin źródłowy, para spotkanie/gracz, sekwencja kolejności i indeksy. `alembic check` nie wykrywa różnic względem modeli |
| Domyślny harmonogram | Wtorek 18:00, 120 minut, Europe/Warsaw, I LO w Gdańsku; limit 14. Migracja dodaje wyłącznie regułę, bez fikcyjnych meczów i zawodników |
| Wyliczanie i scalenie | Czysty moduł `app/domain/schedule.py`, daty lokalne przeliczane na UTC. Wystąpienia wirtualne są scalane z trwałymi rekordami. Przesunięty rekord zastępuje pierwotny termin, odwołany pozostaje widoczny |
| Dalsze miesiące | API zakresu 1–366 dni z paginacją; miesiąc można wybrać bezpośrednio i przeglądać dalej. Brak granicy najbliższego tygodnia ani roku. Testy odczytują 2040/2041, a E2E otwiera termin 10 lat po miesiącu testowym |
| Idempotentne otwarcie | UUIDv5 wynika z ID wersji harmonogramu i daty źródłowej. `POST /meetings/resolve` waliduje regułę, tworzy rekord przez INSERT ON CONFLICT i zwraca go. Testy dwóch żądań HTTP oraz dwóch niezależnych transakcji DB dowodzą identycznego ID i jednego rekordu |
| DST, dzień tygodnia i granice | Testy marcowej i październikowej zmiany czasu, roku przestępnego, przejścia przez rok i zmiany wtorku na czwartek/piątek. Przedziały wersji są lewostronnie domknięte, prawostronnie otwarte |
| Stabilna historia | ID i data źródłowa zostają po przesunięciu rzeczywistego startu; odczyt pod tym samym adresem działa po zakończeniu terminu. Niewytworzone minione wystąpienia nie udają historii rozegranych spotkań |
| Prywatność | Kalendarz, szczegóły, harmonogram i lista grupy wymagają sesji. DTO uczestnika/gracza zawiera tylko ID, imię, nazwisko i przydomek; brak statusu priorytetu, roli, PIN-u i danych prywatnej historii. Zablokowany profil nie otwiera nowych rekordów |
| UI wariantu A | Miesięczny kalendarz i lista, wybór miesiąca/dnia, oznaczenie odwołania, najbliższy termin z API, szczegóły i powrót do miesiąca spotkania. Puste stany, błąd z ponowieniem i informacja o starych danych przy błędzie odświeżania |

## Kontrakt i zachowanie

- `GET /api/v1/schedule`: wersje reguły (poniedziałek=0, niedziela=6).
- `GET /api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD&limit=50&offset=0`: daty kalendarzowe Europe/Warsaw, `to` wyłączne, maksymalnie 366 dni na żądanie. Zwraca `items`, `total` i `next_offset`. Obsługiwane lata zapytań 1970–9998; to granica reprezentacji technicznej, bez ograniczenia do najbliższych terminów.
- `POST /api/v1/meetings/resolve`: `{schedule_version_id, source_date}`. Samo otwarcie nie deklaruje obecności, nie zajmuje miejsca i nie tworzy Enrollment. Nowy rekord może dotyczyć przyszłego lub jeszcze trwającego poprawnego wystąpienia; minionego nie można utworzyć. Już zapisany rekord pozostaje odczytywalny i idempotentnie rozwiązywany również po czasie, zmianie reguły i odwołaniu. Deklaracje E4 muszą oddzielnie sprawdzać przyszły start i stan spotkania.
- `GET /api/v1/meetings/next`: najwcześniejsze nieodwołane i niezakończone spotkanie, którego koniec jeszcze nie minął, także aktualnie trwające; brak terminu daje `null`.
- `GET /api/v1/meetings/{id}`: trwały termin i bezpieczne listy uczestników/rezerwy.
- `GET /api/v1/players`: paginowana lista aktywnych profili dla zalogowanej grupy. Anonimowy katalog logowania nadal jest osobnym, maskowanym DTO z E2.

Źródło reguły domyślnej ma datę początkową 1970-01-01, co nie tworzy historycznych spotkań. Czas trwania liczymy jako rzeczywisty odstęp od początku w UTC. Dotychczas nie ustalono zachowania dla lokalnej godziny, która nie istnieje lub występuje dwukrotnie podczas zmiany czasu; czysta funkcja jawnie odrzuca taki początek zamiast przesuwać go po cichu. Domyślne 18:00 tego problemu nie ma. E5 musi zwalidować proponowaną regułę przed jej zapisem i, jeśli potrzebna będzie taka godzina, uzyskać rozstrzygnięcie polityki DST.

## Weryfikacja

Środowisko lokalne: macOS arm64, Python 3.13.18, PostgreSQL 14.24 na 127.0.0.1:55432; osobna baza `volleycrew_test`. Testy integracyjne i seeder E2E wymagają sufiksu `_test`, nie korzystają z dev ani maybe-finance.

- `npm run lint` — Ruff, ESLint i Prettier poprawnie.
- `npm run typecheck` — poprawnie.
- `npm run api:check` — aktualny OpenAPI i wygenerowane typy.
- `VOLLEYCREW_TEST_DATABASE_URL=<baza *_test> npm run test:backend` — **35 zaliczonych**. Jedno ostrzeżenie zależności Starlette o przyszłej zmianie transportu TestClient, bez błędu testów.
- `npm run test:frontend` — **1 test Vitest zaliczony**.
- `VOLLEYCREW_E2E_DATABASE_URL=<baza *_test> npm run test:e2e` — **6 zaliczonych** w Chromium 158: wcześniejsze ścieżki E2, nawigacja i nowy pełny scenariusz kalendarza. Kontrola overflow i screenshoty 360/390/430/1440 px; błąd sieci przez przerwanie żądań przeglądarki i ponowienie do prawdziwego API.
- `npm run build` — poprawny build produkcyjny.
- Alembic `check` na testowej DB — `No new upgrade operations detected`.

Screenshoty (ignorowane w git): `volleycrew/frontend/test-results/calendar-calendar-future-n-16f7f-sistent-detail-and-recovery-{desktop,mobile}/`, pliki `calendar-360.png`, `calendar-390.png`, `calendar-430.png`, `calendar-1440.png` i `meeting-detail.png` stosownie do projektu. Wizualnie sprawdzono kalendarz 360 px i mobilne szczegóły. To emulacja Chromium, bez testu fizycznego telefonu/Safari. Fikcyjne odwołanie istnieje wyłącznie w seedzie E2E.

## Przekazanie do E4

- Enrollment jest fundamentem bez endpointu zapisu. E4 wdraża całą alokację pod blokadą Meeting: limit, trzy priorytety, rezerwacje, oferty i ponowienia. Otwarcie terminu w E3 nie oznacza odebrania kryterium zapisu zawodnika z E4.
- `declared_at` i `queue_number` porządkują zgłoszenia. Ponowny zapis po wycofaniu wymaga nowego czasu i numeru; powtórzenie bieżącej deklaracji musi zachować oba. Samo odświeżenie strony niczego nie zmienia.
- Pole `accepted_late_offer` trzeba powiązać z rzeczywistym zdarzeniem/SeatOffer w E4, bez możliwości nadania wyjątku przez klienta.
- Dopiero E4 dołącza zwolnienie przyszłych miejsc/ofert do blokady profilu i umożliwia zmianę prywatnego priorytetu administratorowi. Zachować kolejność blokad identity → harmonogram/spotkanie, aby nie wprowadzić deadlocków; operacje harmonogramu E5 współpracują z blokadą reguły używaną w resolverze.
- E5 dostarcza edycję i odwoływanie z UI/API; obecny kod odczytu już poprawnie uwzględnia takie rekordy, testowane bezpośrednią zmianą fixture DB.
- PostgreSQL 17/CI, pakiet HA, Ingress, test Pi 4 i backup/restore nadal oczekują na właściwe etapy. Lokalny test nie jest dowodem wdrożenia.

Następny gotowy etap po zleceniu: **E4 — deklaracje, priorytety i rezerwa**.
