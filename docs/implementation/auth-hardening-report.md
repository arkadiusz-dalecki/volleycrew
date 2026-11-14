# E2/E9 — linki, monitoring i odporność na nadużycia

Data: 2026-11-14. Zakres zlecony po recenzji logowania: punkt 5 końcowych priorytetów. Gałąź `feat/auth-link-hardening`, baza PR `e060c47` (main po scaleniu #9). Raport wyników lokalnych; bieżący wynik CI jest w PR. Bez wdrożenia.

## Zachowanie

- Linki zaproszenia, bootstrapu i resetu odczytują fragment do pamięci strony i zastępują bieżący wpis historii adresem bez sekretu/query. Zachowany jest prefiks Ingress i stan techniczny routera. Brak tokenu w localStorage/sessionStorage. Odświeżenie wymaga ponownego otwarcia oryginalnego linku; UI wyjaśnia to zachowanie. Usuwanie adresu korzysta z History API, aby nie konkurować z przejściem po zalogowaniu.
- Dawne tokeny w ścieżce nie służą już do uwierzytelnienia; trasy przekierowują do czystego formularza z informacją o pełnym linku. Aktualne linki `#…` nadal działają, samo otwarcie nie zużywa grantów.
- HTTP 429 wyświetla `Retry-After` jako czas oczekiwania w sekundach. Mutacje nie są automatycznie ponawiane.
- Dodatkowy limiter ASGI działa przed odczytem body, DB i Argon2 dla czterech operacji wejścia. Budżet na źródło: seria 10, odnawianie 30/min; globalny: seria 20, odnawianie 4/s. Stan źródeł jest ograniczony do 1024 wpisów. Pozostałe operacje, w tym deklaracje i health, nie korzystają z tej bramki. Trwałe limity PostgreSQL pozostają bez zmian.
- Ograniczone logi `volleycrew.security` zapisują czas UTC, rodzaj wyniku, operację i odcisk HMAC źródła. Nie odczytują/nie logują body, PIN-u, tokenu, cookies, pełnego URL, profilu ani nazwiska. Maksymalnie 60 zdarzeń/min/proces i jeden marker pomijania dalszych wpisów.
- Instrukcja HA wyjaśnia interpretację zdarzeń, ograniczenia telemetrii, wspólne źródło proxy/Ingress i konieczność ochrony tunelu przed zalaniem połączeń.

Nie zmieniano DTO ani schematu bazy; brak migracji. PIN, rola administratora, lista logowania, ważność sesji i wielokrotność zaproszeń są poza tym zakresem. Nie podnoszono wersji pakietu.

## Weryfikacja

Środowisko: macOS arm64, Python 3.13.18, osobny tymczasowy PostgreSQL 17.11 na porcie 59583, baza `volleycrew_hardening_test`. Backend i E2E wykonywane sekwencyjnie. Node 26.8.1, przeglądarki Playwright Chromium 158.0.8127.18 i WebKit 27.2, projekty desktop/mobile/webkit. Nie używano bazy development ani produkcji.

- Backend: `.venv/bin/python -m pytest -q` z `VOLLEYCREW_TEST_DATABASE_URL` wskazującym wyłącznie powyższą bazę, z katalogu backendu — **155 zaliczonych**. Obejmuje rzeczywiste PostgreSQL, dotychczasowe sesje i limity, konkurencyjne resety/bootstrap oraz nowe przypadki limitera i telemetrii.
- Po końcowej zmianie czasu UTC w logach: `pytest tests/test_auth.py tests/test_auth_protection.py tests/test_security.py -q` z katalogu backendu — **18 zaliczonych**.
- Nowe testy z kontrolowanym zegarem sprawdzają odnawianie budżetów, wspólny limit wielu źródeł, ograniczenie pamięci, brak odczytu body/wywołania dalszego API po odrzuceniu, prefiks Ingress i ograniczenie logów. Integracja sprawdza wyniki operacji oraz brak sekretów w telemetrii.
- `npm run lint`, `npm run typecheck`, `npm run api:check` — zaliczone.
- `npm run test:frontend` — **6 zaliczonych**, w tym poprawny/brakujący/nieprawidłowy Retry-After.
- `npm run build` — zaliczony również po końcowej poprawce History API.
- `npm run test:e2e -- auth.spec.ts auth-links.spec.ts` z izolowanym `VOLLEYCREW_E2E_DATABASE_URL` — **9 zaliczonych**: pełna rejestracja, login, profil, reset, blokada, odrzucone zaproszenie, czysty adres, brak sekretu w storage, reload i ponowne otwarcie, odrzucenie tokenów w ścieżce w Chromium/WebKit. Pierwszy przebieg ujawnił konflikt nawigacji routera podczas zmiany sesji; poprawiono go użyciem History API i potwierdzono pełną ścieżką.

- Pełne `npm run test:e2e` na tej samej izolowanej bazie, po zakończeniu testów backendu — **83 zaliczone, 1 celowo pominięty** (klawiatura mobilna na projekcie desktop), 4,2 min. Wszystkie projekty desktop/mobile/webkit, w tym wyścigi sesji, zapisy, rezerwa, obecność, wynik, harmonogram, PDF i dostępność.
- `git diff --check` — zaliczony.

Wymagany lokalny zakres E2/E9 spełniony. Następne zadanie: osobny odbiór E11 na fizycznym telefonie/HA; pozostałe zalecenia z recenzji wymagają odrębnego zlecenia i decyzji.

## Granice odbioru

Bez testu produkcyjnego obrazu: lokalny daemon Docker jest niedostępny. Konfiguracja Nginx, s6 i Dockerfile nie była zmieniana. Test middleware obejmuje oba prefiksy, ale nie zastępuje odbioru obrazu ani produkcyjnego proxy/HA. Na etapie weryfikacji lokalnej nie wykonywano testów na fizycznym telefonie, instalacji HA ani publikacji. Zlecony później PR uruchamia również testy obrazów amd64/aarch64 w GitHub Actions; ich bieżący wynik jest w PR. Logi nie wysyłają automatycznych alertów i są próbkowane przy dużym ruchu. Limiter dodatkowy zakłada obecny pojedynczy worker; restart zeruje tylko jego pamięć, nie ochronę trwałą. Silniejszy login administratora, procedura ratunkowa i zmiana polityki zaproszeń pozostają osobnymi zaleceniami z recenzji.
