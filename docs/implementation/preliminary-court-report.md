# Wstępne boisko — 2026-11-09

Zakres: uzupełnienie E4/E6/E9 zlecone przez użytkownika. Wersja pakietu HA: **0.3.2** (patch po 0.3.1). Implementacja na gałęzi `feat/manage-series-and-print-signatures`; bez zmian w produkcyjnej bazie.

## Kryteria odbioru

- Przed sprawdzeniem obecności szczegóły spotkania pokazują boisko z potwierdzonych miejsc. Domyślny podział minimalizuje różnicę średnich aktualnego ELO, jest deterministyczny i obejmuje każdą osobę dokładnie raz. Obowiązują limit 14 i maksymalnie 7 na stronę; dla 0–1 jest czytelny stan pusty.
- Rezerwa, oferty, nieaktywne profile i oczekujący na ponowne potwierdzenie pozostają poza boiskiem. Podgląd nie zapisuje obecności, oficjalnych drużyn ani rankingu.
- Własny zapis/rezygnacja/przyjęcie oferty odświeżają podgląd natychmiast. Inne urządzenia odczytują zmiany co 30 s oraz po powrocie do karty. Nie jest to transmisja push.
- Administrator zapisuje wspólny podział losowy, ręczne zamiany albo wraca do ELO. Zmiana deklaracji, terminu lub punktów unieważnia wyjątek. Powrót tej samej listy osób po rezygnacji nie przywraca starego podziału.
- Token wejścia, rewizja oraz blokada spotkania odrzucają nieaktualny zapis i równoległe zmiany (409). Użytkownik ma podgląd bez narzędzi administracyjnych; serwer sprawdza rolę i CSRF. DTO nie ujawnia prywatnych statusów ani powodów korekt.
- Po zatwierdzeniu obecności „Użyj wstępnego podziału” tworzy oficjalny szkic z podglądu, jeżeli osoby i punkty są zgodne. Inaczej wyrównuje faktycznie obecnych. Oficjalne zatwierdzenie drużyn pozostaje osobnym krokiem.

## Implementacja i migracja

Osobny serwis `preliminary_teams.py`, GET publiczny dla zalogowanych i PUT administratora. Migracja `0010_preliminary_teams` po 0009 dodaje tabelę wyjątków administratora; nie przenosi danych obecności ani demo. Domyślny ELO powstaje podczas odczytu bez zapisu do tabeli. Zmiany podglądu nie zwiększają wersji spotkania, więc nie unieważniają wydruku ani formularza obecności. Przed aktualizacją HA obowiązuje istniejąca procedura kopii i migracji. Migracja wykonana lokalnie na bazie developerskiej.

Frontend korzysta z tego samego boiska wariantu A co oficjalne składy. Wybrane osoby są powiązane z odciskiem i rewizją, by nie wykonać zamiany na nieaktualnej liście. Odczyt z błędem wskazuje ostatni podział; ponowiony zapis po utracie odpowiedzi nie wykonuje drugiego losowania.

## Weryfikacja

Środowisko: macOS arm64, Python 3.13.18, lokalny PostgreSQL, izolowana baza `volleycrew_test`; Chromium 158.0.8127.18 i WebKit Playwright (emulacja iPhone, nie fizyczny Safari).

- `VOLLEYCREW_TEST_DATABASE_URL=… npm run test:backend`: **144 zaliczone**, w tym 11 nowych przypadków podglądu. Obejmują 0/1/2/8/14 osób, zgodność ELO, prywatność i brak skutków ubocznych, rezerwę/oferty, zmianę terminu/punktów, join–cancel, niepoprawne podziały, uprawnienia i konkurencyjne zapisy oraz przekazanie do oficjalnych drużyn.
- `npm run lint`, `npm run typecheck`, `npm run api:check`: zaliczone.
- `npm run test:frontend`: **4 zaliczone**; `npm run build`: zaliczony.
- `VOLLEYCREW_E2E_DATABASE_URL=… npm run test:e2e`: **71 zaliczonych, 1 celowo pominięty** (desktopowy przypadek klawiatury mobilnej), pełny przebieg 3,7 min w projektach desktop Chromium, mobile Chromium i iPhone/WebKit. Nowy scenariusz sprawdza wspólną ręczną zamianę, podgląd użytkownika, natychmiastowy join/cancel, odświeżenie drugiej karty, brak zatwierdzonej obecności, dostępność i brak poziomego przewijania.
- Lokalny podgląd developerski terminu 17 listopada: API 200, boisko widoczne z aktualnych zapisów, screenshot `/tmp/volleycrew-preliminary-local.png`; bez zmiany deklaracji podczas kontroli.
- Kontrola wizualna screenshotu WebKit 390 px: wstępne boisko i narzędzia administratora mieszczą się w karcie; obie strony i nazwiska są czytelne.

## Pozostałe zależności

Odbiór wyglądu przez użytkownika, fizyczny telefon i instalacja/aktualizacja na HA pozostają do wykonania. Nowe dane demo z 17 listopada istnieją tylko w lokalnej bazie developerskiej. Nie wykonano wdrożenia produkcyjnego ani testów obrazu HA w tym uzupełnieniu.

## Uzupełnienie etykiety deklaracji

Na prośbę użytkownika „Będę” zastąpiono „Potwierdzam obecność”. Akcja nadal zapisuje deklarację, a obecność na sali pozostaje osobnym zatwierdzeniem administratora. Zaktualizowano selektory istniejących scenariuszy. Po zmianie: typecheck oraz 3 E2E wstępnego boiska (desktop/mobile/WebKit) zaliczone; brak nowych zależności.

## Przygotowanie PR 0.3.2 — 2026-11-10

Manifest HA podbity z 0.3.1 do 0.3.2; changelog zawiera cały zakres gałęzi. Przed publikacją ponownie zaliczone lint, typecheck, kontrakt OpenAPI, `git diff --check` oraz 13 testów konfiguracji/pakietu. Wcześniejsze pełne wyniki 144 backend / 71 E2E oraz końcowe 3 E2E po zmianie etykiety pozostają dowodami funkcjonalnymi. CI sprawdzi bieżący commit i obrazy obu architektur. PR nie wdraża aplikacji na HA.

## Poprawka CI PR #6 — 2026-11-11

Oba obrazy zbudowały się, lecz scenariusz `scripts/test_container.py` próbował deklaracji na trwające najbliższe spotkanie. Uruchomienie CI 2026-11-10 o 17:09–17:14 UTC przypadło po wtorkowym starcie 18:00 w Warszawie; API słusznie zwracało 409 `enrollment_closed`. Endpoint najbliższego spotkania celowo uwzględnia trwający mecz.

Fixture wybiera teraz zaplanowane wystąpienie z kalendarza od jutra w strefie Europe/Warsaw, z dwutygodniowym oknem. Dalszy cykl nadal zapisuje deklaracje przez rzeczywiste API, a dopiero potem przesuwa testowe spotkanie na salę. Nie zmieniono reguł produkcyjnych ani limitów zapisów. Dodano 4 regresje na rzeczywistym API/PostgreSQL: wtorek przed startem, w godzinie startu, w trakcie i po spotkaniu; każda rozwiązuje przyszły termin i skutecznie zapisuje deklarację. Wszystkie 4 zaliczone, lint i kompilacja skryptu zaliczone. Pełne testy obrazów obu CPU weryfikuje ponowny przebieg CI po publikacji poprawki.
