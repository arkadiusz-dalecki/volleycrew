# E2/E9 — opcjonalne logowanie Google

Aktualizacja: rejestracja przez Google z zaproszenia i konta bez hasła rozszerzają opisany zakres. Końcowy stan i wyniki: [raport rejestracji Google](google-registration-report.md).

Data: 2026-11-15. Gałąź `feat/google-login`, baza `1962d88` (main po #10). Zakres: dodatkowe Google dla istniejących profili, bez otwierania rejestracji. Wyniki lokalne poniżej; bieżący status obrazów i GitHub Actions w PR. Bez wdrożenia HA ani użycia rzeczywistych kont Google.

Aktualizacja: bieżący PR zastępuje PIN loginem i hasłem; dawne dowody poniżej opisują pierwszą wersję integracji. Aktualne potwierdzenia Google wymagają hasła. Końcowa weryfikacja i procedura organizatora: [raport loginu i hasła](password-login-report.md).

## Zachowanie i kryteria

| Kryterium | Realizacja i dowód |
| --- | --- |
| Połączenie własnego profilu | Aktywna sesja i świeży PIN; jednorazowy flow wiąże dokładną sesję, przeglądarkę i nonce. Po zewnętrznym I/O sesja i blokada profilu są ponownie sprawdzane. PostgreSQL i podpisane tokeny w testach. |
| Logowanie bez duplikowania profili | Wyłącznie unikalny Google `sub` z poprawnego ID tokenu wskazuje już istniejącego gracza. Niepowiązane konto nie rejestruje profilu. Rola i priorytet pozostają w DB. |
| OIDC i odporność | Authlib authorization code + PKCE S256; PyJWT RS256/JWKS, issuer, aud, exp/iat, azp i nonce. Cache JWKS respektuje krótszy Cache-Control i jest ograniczony do 300 s. Stan jednorazowy, 10 minut, związany z cookie Secure/HttpOnly/Lax z prefiksem __Host. Testy podpisu, claimów, replay, wygaśnięcia, innych przeglądarek i konkurencji. |
| Brak blokady DB podczas Google | Krótkie zużycie flow w transakcji przed wymianą kodu; po commit połączenie i wspólna blokada są zwolnione na zewnętrzne I/O. Ponowne serializowane sprawdzenie przed powiązaniem/sesją. |
| Odłączenie i odzyskiwanie | Odłączenie wymaga PIN-u, usuwa połączenie, unieważnia sesje/oczekujące łączenia i wydaje świeżą sesję bieżącemu urządzeniu. Reset PIN-u od organizatora usuwa Google; samodzielna zmiana PIN-u zachowuje je. Testy prawdziwych sesji i resetów. |
| Interfejs i HA | Przycisk Google na wejściu i własna sekcja profilu; jasne błędy, anulowanie, status połączenia, powrót na żądaną wewnętrzną trasę. Ingress otwiera PUBLIC_URL w nowej karcie bez przenoszenia sesji. Testy izolacji Ingress w API i komponentach. |
| Konfiguracja i prywatność | Opcjonalna para GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET; brak pary wyłącza Google, niepełna para odrzucana. Prywatne pliki s6 z prawami 0600. Zakres openid; bez przechowywania e-maila i tokenów dostępu/odświeżania/ID. Nie pokazujemy Google sub w API. |
| Monitoring i nadużycia | Limit startu 60/źródło/15 min w PG, dotychczasowa bramka POST i osobna bramka callbacków. Odrzucony callback wraca do czystego ekranu. Logi wyników mają odcisk źródła i stałe kody, bez sekretów. Nginx pomija URI/query, access log Uvicorn jest wyłączony także w dev; HTTPX/httpcore mają WARNING. |

Google działa pod stałym PUBLIC_URL. Ingress nie jest alternatywnym callbackiem; użytkownik może korzystać z osobnej sesji pod główną domeną. PIN i zaproszenia pozostają dostępne, więc samo dodanie Google nie usuwa słabości PIN-u administratora ani nie zastępuje pozostałych zaleceń z recenzji.

## Migracja i aktualizacja

Migracja `0011_google_login` dodaje `google_identities` (unikalne powiązanie profilu i sub) i `google_flows` (hashe, sesja łącząca, wewnętrzny cel powrotu, daty). Nie zmienia istniejących profili/PIN-ów. Wymagana zwykła kopia przed aktualizacją. Test świeżej migracji oraz downgrade/upgrade potwierdza zachowanie profili i logowania PIN-em; downgrade usuwa powiązania Google i flow. Przy cofnięciu obrazu obowiązuje dotychczasowa procedura zgodnego schematu i backupu, nie samo uruchomienie starego obrazu na nowym head migracji. Nie zmieniano wersji pakietu.

Backend używa przypiętych w lockach Authlib 1.9.6, HTTPX 0.28.1 i PyJWT 2.15.1 z cryptography 50.0.2. Produkcyjny requirements.lock sprawdzony względem uv export. Frontend używa lokalnej oficjalnej ikony G i Google Sans (podzbiór 2240 bajtów, SIL OFL); źródła i licencja w public/. Brak zewnętrznego skryptu GIS ani fontów pobieranych w runtime.

## Weryfikacja lokalna

macOS arm64, Python 3.13.18, PostgreSQL 17.11, Node 26.8.1; osobna tymczasowa baza `volleycrew_google_test` na 127.0.0.1:59643. Backend i zestawy E2E uruchamiane sekwencyjnie, bez bazy development/produkcji.

- `.venv/bin/python -m pytest -q --tb=short` z katalogu backendu i izolowanym VOLLEYCREW_TEST_DATABASE_URL — **181 zaliczonych**. Obejmuje prawdziwe PostgreSQL, świeże i powrotne migracje, sesje i konkurencję oraz podpisane RSA tokeny przez rzeczywisty kod Authlib/PyJWT; zastąpiony jest wyłącznie transport HTTPS Google.
- `npm run lint`, `npm run typecheck`, `npm run api:generate`, `npm run api:check`, `npm run test:frontend`, `npm run build` — zaliczone; **8 testów jednostkowych frontendu**, w tym osobne linki Ingress i brak kopiowania sesji.
- Dedykowane `npm --prefix volleycrew/frontend run test:google` — końcowy przebieg **6 zaliczonych** (22,3 s) w desktop/mobile/WebKit. Zrzuty ekranu logowania i profilu sprawdzono wizualnie; nie są dodawane do repozytorium. Testowy wystawca podpisuje RSA, sprawdza PKCE i prowadzi przeglądarkę przez faktyczny callback/sesje. Testowy moduł backendu odmawia działania poza odizolowaną bazą *_test i lokalnym URL; nie trafia do obrazu produkcyjnego i nie ma flagi aktywującej go w aplikacji.
- Pełne `npm run test:e2e` przy domyślnie wyłączonym Google — **83 zaliczone, 1 celowo pominięty na desktopie**; końcowy zapis Playwright ma status passed i pustą listę failedTests.
- Pierwszy build CI ujawnił brak wykluczenia nowych plików Playwright w `.dockerignore` (brakujące wspólne fixtures/config w kontekście obrazu). Dodano wykluczenia Google analogiczne do istniejących E2E; lokalny build z odfiltrowanym kontekstem potwierdza poprawkę.
- Dodano dedykowany test Google do CI oraz smoke RS256 z odrzuceniem złego audience w prawdziwych obrazach obu CPU. Lokalny Docker jest niedostępny; wynik obrazów będzie w PR.

W repozytorium są dwa ostrzeżenia o przyszłej migracji HTTPX → HTTPX2 (Starlette TestClient i integracja Authlib). Nie wyłączano ostrzeżeń ani asercji. Parametry dotychczasowej ochrony PIN nie zostały poluzowane.

## Źródła i odbiór operatora

- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [Google discovery](https://accounts.google.com/.well-known/openid-configuration) — odczyt 2026-11-15 potwierdził endpointy, S256 i client_secret_post.
- [Authlib HTTP clients](https://docs.authlib.org/en/stable/oauth2/client/http/index.html), [PyJWT](https://pyjwt.readthedocs.io/en/stable/usage.html), [Google branding](https://developers.google.com/identity/branding-guidelines).
- [Instrukcja Google dla operatora](../../volleycrew/DOCS.md#opcjonalne-logowanie-google).

Pozostaje konfiguracja własnego klienta Google (ID i sekret wpisane w HA, zarejestrowany callback), próba z rzeczywistym kontem oraz fizyczny telefon/HA, w tym zachowanie zainstalowanej PWA. Testy lokalne z własnym wystawcą nie stanowią odbioru Google Console ani publikacji consent screen. Następny krok: przegląd PR/CI, następnie samodzielna konfiguracja i odbiór operatora.
