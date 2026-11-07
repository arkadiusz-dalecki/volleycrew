# E2 — sesje, PIN i zaproszenia

Data: 2026-11-06. Stan: implementacja lokalna, odbiór funkcji E2 potwierdzony testami opisanymi poniżej. Bez wdrożenia produkcyjnego i bez tworzenia rzeczywistego konta Arkadiusza. Kod nie został wypchnięty; pliki projektu są nadal lokalne.

## Zakres i odbiór

| Kryterium E2 | Realizacja / dowód |
| --- | --- |
| Pierwszy administrator bez domyślnego PIN-u | Operator generuje jednorazowy link CLI, administrator wybiera PIN w `/setup#token`; 30 minut, zamknięcie po pierwszym koncie admina; test wygaśnięcia i równoczesnego użycia |
| Rejestracja wyłącznie z aktywnego zaproszenia | Wielokrotny losowy link, unieważnienie; nowy profil zawsze guest/player; dodatkowe pola statusu/roli są odrzucane; integracja PostgreSQL i UI |
| Profil chooser i prywatność | Backend zwraca tylko ID, imię, maskowane nazwisko i przydomek; zawsze pięć gwiazdek, także krótkie/polskie nazwiska; pełne nazwiska nie trafiają do anonimowego JSON i DOM |
| Zapamiętane urządzenie i nowe urządzenie | Cookie sesji HttpOnly, losowy token, hash w DB; 30 dni bezczynności / maks. 180 dni; refresh zachowuje sesję, nowe urządzenie wymaga PIN-u |
| Zmiana i reset PIN-u | Obecny PIN wymagany przy zmianie; reset jednorazowy 30 minut; nowszy grant unieważnia starszy; wszystkie stare sesje tracą ważność; bieżące urządzenie dostaje nową |
| Trwałe ograniczenie prób | 5 błędnych PIN-ów/profil/15 min, następnie 429 z Retry-After do końca okna; osobno 30/źródło; test restartu API i ponowienia po oknie; bez trwałej blokady |
| Autoryzacja / blokada | Każdy endpoint administracyjny sprawdza rolę; blokada unieważnia sesje i granty, ukrywa profil w katalogu i uniemożliwia login; odblokowanie nie przywraca starych sesji; dane konta i audyt zostają |
| CSRF i brak sekretów w odczycie | Origin + podpisany token związany z sesją + cookie/header; wszystkie mutacje, także anonimowe; hashe tokenów i Argon2id, no-store; testy złego Origin, braku tokenu, tokenu innej sesji i flag cookie |
| UI A na telefonie | Rejestracja, logowanie, profil/PIN i ustawienia administratora; dostęp do ustawień także z mobilnego profilu; loading/error/retry, potwierdzenie blokady, kopiowanie linków |

Migracja `0002_auth` tworzy players, auth_sessions, invites, pin_reset_grants, bootstrap_grants, auth_throttles i audit_events. Mutacje tożsamości są serializowane transakcyjną blokadą advisory PostgreSQL. To świadomy prosty wybór dla jednej małej grupy, ograniczający też równoległe hashowanie na Pi. Nie opiera się na pamięci procesu. Pole statusu i uprawnienia administratora pozostają rozdzielone.

## Weryfikacja lokalna

Środowisko: macOS arm64, Python 3.13.18, PostgreSQL 14.24 na izolowanym porcie 55432. Wyłącznie dedykowana baza `volleycrew_test`; dev pozostaje oddzielna. Chromium 158 (Playwright, desktop 1440×1000 i emulacja Pixel 7 390×844). Emulacja nie oznacza testu na fizycznym telefonie ani Safari.

- `npm run lint` — poprawnie (Ruff, ESLint, Prettier).
- `npm run typecheck` — poprawnie.
- `npm run api:check` — poprawnie, kontrakt OpenAPI i typy zgodne.
- `VOLLEYCREW_TEST_DATABASE_URL=<oddzielna baza *_test> npm run test:backend` — 20 testów zaliczonych, w tym rzeczywista PostgreSQL, kontrolowany zegar i równoczesne użycie bootstrapu/resetu. Jedno ostrzeżenie biblioteki Starlette o przyszłej zmianie transportu TestClient; bez błędu testów.
- `npm run test:frontend` — 1 test Vitest zaliczony; główne ścieżki E2 sprawdza przeglądarka.
- `npm run build` — poprawny build produkcyjny React/Vite.
- `VOLLEYCREW_E2E_DATABASE_URL=<oddzielna baza *_test> npm run test:e2e` — 4 testy desktop/mobile: pełna rejestracja, pamiętanie sesji, prywatność logowania, profil, reset, blokada, odrzucone zaproszenie oraz nawigacja i reload. Testowe serwery 8202/5175, bez użycia dev.

Screenshoty w ignorowanym `volleycrew/frontend/test-results/`: `profile.png`, `login.png`, `admin.png`, `meeting.png` w katalogach danego projektu testowego. Sprawdzono wizualnie ekran logowania, profilu i ustawień organizatora; automatyczna kontrola poziomego overflow obejmuje również ustawienia organizatora. Testy wykryły błąd odświeżania UI po wylogowaniu; poprawiono unieważnianie pamięci zapytań, a ścieżka jest objęta E2E.

## Pozostałe zależności

- E4 musi dołączyć zwalnianie przyszłych zapisów, rezerwacji i ofert do blokady profilu w tej samej transakcji, przy wspólnym porządku blokad. Modele spotkań jeszcze nie istnieją, więc E2 nie deklaruje odbioru całego D6 w zakresie zapisów. Dodać test wyścigu blokada/zgłoszenie/przyjęcie oferty.
- Administracyjna zmiana statusu priorytetu czeka na E4: musi przeliczać miejsca według D3, bez obchodzenia ich reguł. E2 daje odczyt prywatnego statusu i bezpieczny domyślny guest.
- PostgreSQL 17 w CI/Compose, obrazy obu CPU i instalacja HA nadal niewykonane. Zmodyfikowano konfigurację CI, lecz uruchomienie lokalne nie jest dowodem zielonego workflow.
- E10: konfiguracja origin/proxy, dynamiczny prefiks Ingress i cookie w iframe, trwały klucz w `/data`, pomiar Argon2/RAM/czasu na Pi 4, backup i odtworzenie. Tunnel użytkownik konfiguruje samodzielnie.
- Pierwsze realne konto tworzy użytkownik przez `npm run auth:bootstrap`. Seeder E2E odmawia pracy na bazie bez sufiksu `_test`.

Następne gotowe zadanie po zleceniu: **E3 — modele spotkań i kalendarz**.
