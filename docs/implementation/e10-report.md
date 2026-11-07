# E10 — pakiet Home Assistant do samodzielnej instalacji

Data: 2026-11-07. Zakres zgodnie z ostatnim poleceniem: pakiet i instrukcja w repozytorium oraz lokalna weryfikacja. Użytkownik sam publikuje/dodaje repozytorium, generuje token i instaluje aplikację. Nie wykonano instalacji, aktualizacji ani zmian w docelowym HA, tunelu lub produkcyjnym PostgreSQL. Kod pozostaje lokalny, bez commita/push i wydania.

## Dostarczone elementy

- `repository.yaml`, `volleycrew/config.yaml`, `build.yaml`, Dockerfile i `.dockerignore`. Wersja pakietu **0.1.0**, `aarch64`/`amd64`, lokalny build przez Supervisor, bez `image` z gotowym obrazem Volleycrew. Brak `host_network`, mapowania konfiguracji HA i uprawnień do API HA/Supervisora/Dockera. `/data` jest trwały.
- Wieloetapowy build: Node 24 tylko do kompilacji, statyczny frontend, Python/FastAPI i Nginx z s6 w runtime. Runtime Debian base **9.3.0**, obrazy obu architektur i domyślny indeks multiarch przypięte do zweryfikowanych digestów; Node 24 również po digest. Backend instaluje hashowany `requirements.lock`, eksportowany z `uv.lock` bez zależności developerskich. CI sprawdza zgodność eksportu.
- Walidowane opcje `/data/options.json` → prywatne pliki środowiska s6 (600), bez `eval` i wypisywania połączenia DB. Hasła ze znakami specjalnymi są kodowane przez SQLAlchemy URL. Publiczny URL HTTPS jest originem bez ścieżki. Zaufane adresy proxy są walidowane, `0.0.0.0/0`/`::/0` odrzucane.
- Start: konfiguracja i sprawdzenie Nginx → ograniczone oczekiwanie na DB → kopia przed zmianą wersji/schematu → migracje → bootstrap → API i Nginx. Nieprawidłowa konfiguracja nie uruchamia migracji. Awaria inicjalizacji lub procesu zatrzymuje kontener; nie ma kasowania bazy jako naprawy. Zablokowana migracja pozostawia API zatrzymane.
- `BOOTSTRAP_TOKEN` w opcjach umożliwia pierwszy profil administratora bez SSH. Losowy token URL-safe, co najmniej 32 znaki; grant ważny 30 minut. Restart nie przedłuża ważności, nowy token może zastąpić stary wyłącznie przed założeniem administratora. Istniejący administrator trwale zamyka bootstrap. PIN ustawia sam użytkownik na `/setup#token`; token nie trafia do logów.
- [Instrukcja instalacji, opcji, aktualizacji, backupu i restore](../../volleycrew/DOCS.md), README aplikacji i changelog. Root README opisuje build i odtwarzalne testy pakietu.

## Wejścia HTTP i prywatność

| Element | Realizacja |
| --- | --- |
| Wejście do własnego tunelu/proxy | Nginx `8200`, konfigurowalne mapowanie hosta HA |
| Ingress | Nginx `8099`, **bez mapowania hosta**, ACL wyłącznie `172.30.32.2` |
| Backend | `127.0.0.1:8000` wewnątrz kontenera |
| Prefiks | Walidowany `X-Ingress-Path` tylko na wejściu Supervisora; wstrzyknięty HTML `<base>`, basename routera, klient API, manifest i assety działają pod zmiennym prefiksem |
| Tożsamość | Własne profile/PIN i role Volleycrew; nagłówki tożsamości HA nie nadają uprawnień |
| Cookies | Oddzielne nazwy i ścieżki direct/Ingress; `Secure`, sesja `HttpOnly`, `SameSite=Lax`. Wymagany HTTPS także dla HA |
| CSRF | Token i jawne originy; origin HA w `ADDITIONAL_ORIGINS`; brak szerokiego CORS |
| Proxy | Publiczne nagłówki Ingress są ignorowane; zaufanie XFF/proto tylko od skonfigurowanych peerów. Kontekst backendu przyjmowany wyłącznie z lokalnego Nginx |
| Logi | Access log Nginx bez URI/query/body/cookies, Uvicorn bez access logu, wyjątki produkcyjne bez tracebacków/parametrów kierowcy; init/backup logują etapy i typy błędów |
| Health | liveness procesu i readiness z DB oraz aktualną rewizją; utrata DB po starcie daje 503 readiness, po powrocie odzyskuje gotowość |

Pakiet dodaje CSP, no-referrer i nosniff. Moduły `.mjs` mają jawny typ JavaScript — test produkcyjnego PDF wykrył brak tego mapowania w domyślnych typach Nginx. PDF.js i worker działają lokalnie także w Ingress. Fonty PDF mogą być ładowane z lokalnych blob/data, bez CDN.

Bazowe skrypty obrazu dotyczące bannera/log level/timezone nie wymagają wywołania Supervisora: zastąpiono pomocnicze akcje s6 neutralnymi skryptami. Konfigurację aplikacji czytamy samodzielnie z `/data/options.json`. Dzięki temu rzeczywisty pakiet działa również poza HA; harmonogram domenowy i kopie używają jawnie `Europe/Warsaw`. Usunięto zbędne zagnieżdżenie `with-contenv` w inicjalizacji DB. Emulację amd64 odnotowujemy osobno od natywnego uruchomienia.

## Backup i odtworzenie

`app.backup` i komenda operatora `volleycrew-backup` tworzą prywatne archiwum: custom `pg_dump`, metadane wersji/schematu i SHA-256, efektywny klucz oraz opcje. Zapis przez plik tymczasowy i atomową zmianę nazwy; staging/partial wyłączone z kopii HA. Brak automatycznego usuwania starych kopii. Archiwum nie jest samodzielnie szyfrowane.

- Lokalnie codziennie o wskazanej godzinie Warszawy; błąd daje jedną ponowną próbę po godzinie i jawny log.
- Przed aktualizacją wersji lub schematu: wymagana kopia, potem migracja; brak kopii blokuje start nowej wersji.
- `backup_pre` HA tworzy aktualny zrzut zewnętrznej DB przed kopią plików aplikacji. Użytkownik musi włączyć kopie HA i **szyfrowany cel poza hostem** oraz zachować klucz odzyskiwania. Agent nie skonfigurował takiego miejsca.
- Restore wymaga jawnego `VOLLEYCREW_RESTORE_DATABASE_URL` i `--confirm-empty-target`; odmawia nadpisania niepustej bazy, sprawdza archiwum i sumy, odrzuca ścieżki/symlinki/duplikaty. `pg_restore` działa w jednej transakcji. Opcje źródła zapisuje osobno jako `restored-options.json`, bez przekierowania połączenia z powrotem na stary serwer.
- Domyślnie sesje są unieważniane; opcjonalne zachowanie wymaga zgodnego klucza. Konta i PIN-y, historia, miejsca, obecność, składy, wyniki i punkty pozostają. Cofnięcie kodu wymaga zgodności schematu albo odtworzenia całego zgodnego zestawu, bez automatycznego downgrade.

Test odtworzył kopię **na drugim kontenerze/instancji PostgreSQL**, porównując liczebność i odciski pełnych wierszy 13 tabel domenowych: profile, harmonogram, spotkania, zgłoszenia i zdarzenia, obecność i historia, składy, wyniki, punkty oraz audyt. Źródłowa baza i sesja nadal działają; sesje w celu są odwołane. Jest to lokalny restore, nie test pobrania z docelowego magazynu poza hostem ani odzyskania całego hosta HA.

## Naprawa pierwszej migracji

Nowa, całkowicie pusta PostgreSQL 17 wykazała błąd backfillu w `0006_room`: `ORDER BY sequence` odwoływał się do kolumny nieistniejącej w `enrollment_events`. Poprawiono kolejność na `enrollment_events.created_at, enrollment_events.id`. Dodano test usuwający wyłącznie schemat jawnej jednorazowej bazy `_test` i przechodzący cały łańcuch od zera. Nie dodano nowej rewizji; bazy już będące na `0007_results` nie zmieniają danych przez tę poprawkę. Nie było wcześniejszego wydania HA tej migracji.

## Weryfikacja lokalna

Mac arm64, dedykowany profil Colima `volleycrew` (Linux ARM64, 2 CPU/4 GiB), oddzielne testowe sieci, kontenery i wolumeny. Obrazy produkcyjne budowane dla `linux/arm64` i `linux/amd64`; amd64 uruchamiany pod emulacją QEMU, nie na fizycznym komputerze x86 ani Pi. Python runtime **3.13.5**, Nginx **1.26.3**, klient PostgreSQL **17.11**. Kod developerski/testy: Python 3.13.18. Żadnej produkcyjnej bazy ani maybe-finance nie użyto.

Przeglądarki: Chromium **158.0.8127.18** i WebKit **27.2**; emulacja iPhone nie jest testem fizycznego Safari iOS. Certyfikat HTTPS fixture jest lokalny, samopodpisany i pomijany wyłącznie w testach. Produkcja nadal wymaga prawidłowego HTTPS i bezpiecznych cookies.

| Sprawdzenie | Wynik |
| --- | --- |
| `npm run lint`, `npm run typecheck`, `npm run api:check`, `npm run test:frontend`, `npm run build` | Poprawnie; Vitest 1 test |
| Pełna regresja backendu na osobnej PostgreSQL 17 przez `test_container.py --backend-tests` | **115 zaliczonych**, 52,69 s; wcześniejsze ostrzeżenie Starlette/TestClient |
| Dodatkowo `tests/test_deployment.py` po ostatnim doprecyzowaniu alfabetu tokenu | **7 zaliczonych** |
| Zwykłe E2E Chromium desktop/mobile i WebKit | **32 zaliczone, 1 celowo pominięty** (mobilna geometria klawiatury na desktopie), 2,5 min |
| Build `linux/arm64` i `linux/amd64` | Oba zakończone poprawnie, obrazy lokalne `volleycrew:e10-arm64` i `volleycrew:e10-amd64` |
| Produkcyjny obraz ARM64: start, błędy, prefiksy/HTTPS, restart, kopia przed wersją, pełny mecz, DB loss/recovery, restore i logi | **Wszystkie zaliczone** |
| Produkcyjny obraz amd64 pod QEMU: ten sam zestaw | **Wszystkie zaliczone**, nie jest to próba na fizycznym x86 |
| Playwright na prawdziwych obrazach: direct + dwa prefiksy, profil/reload/nawigacja i rzeczywiście wyrenderowany PDF | **6/6 ARM64 + 6/6 amd64**, Chromium/WebKit; ostatnie przebiegi 8,2 s i 13,8 s |
| Restore na drugim PostgreSQL | **Zaliczony na obu CPU**, zgodne odciski 13 tabel po meczu 5:3, osobne unieważnienie sesji, źródło nienaruszone |
| Alembic `check` na developerskiej DB i zgodność produkcyjnego eksportu lockfile | `No new upgrade operations detected`; eksport bez różnic |

Wbudowany w początkowy profil Colima emulator sporadycznie kończył proste skrypty bazowe s6 sygnałem 11, także po udanym starcie. Aktualizacja **wyłącznie lokalnego środowiska testowego** do oficjalnego `tonistiigi/binfmt`/QEMU **10.2.3** pozwoliła przejść pełen zestaw amd64 bez takich awarii. Nie uznano wcześniejszych przerwanych prób za sukces i nie zmieniano domeny aplikacji, aby je omijać. CI przypina sprawdzony obraz emulatora po digest. Nie jest to nadal dowód działania na fizycznym x86/Pi.

Logi: `.runtime/e10-container-{arm,amd}.log`, `.runtime/e10/{browser-arm,browser-amd,backend-pg17}.log`. Archiwum testowe jest prywatne i ignorowane przez Git. Kontenery, sieci i przypisane wolumeny z zakończonych przebiegów zostały usunięte; środowisko nie jest wdrożeniem produkcyjnym.

Do odtworzenia: `scripts/test_container.py --image <lokalny obraz> --platform linux/arm64|linux/amd64`. Test tworzy i usuwa wyłącznie własne zasoby. `--backend-tests` uruchamia dodatkowo całą regresję na osobnej `regression_test` w PostgreSQL 17, bez naruszenia źródłowej bazy sprawdzanej aplikacji. Wyniki i screenshoty są w ignorowanych `.runtime/e10*` i `volleycrew/frontend/test-results-container/`.

Workflow CI buduje/testuje oba CPU bez publikacji obrazu; zdalnego CI nie uruchamiano. `build.yaml` zachowano dla zgodności z wybranym sposobem wdrożenia; nowe HA nadal go czyta z ostrzeżeniem. Dockerfile ma też poprawny domyślny multiarch `BUILD_FROM`, więc nie zależy od wstrzyknięcia tego argumentu.

## Odbiór użytkownika po publikacji kodu

- [ ] Kod wysłany do repozytorium, które dodaje użytkownik; zdalne CI sprawdzone.
- [ ] Instalacja i ponowna aktualizacja/restart na Pi 4 aarch64, z pomiarem czasu/RAM builda.
- [ ] Osobny produkcyjny PostgreSQL, poprawne opcje, token i własny PIN administratora.
- [ ] Domena HTTPS i Ingress z własną sesją Volleycrew, właściwe originy/proxy.
- [ ] Wejście zawodnika z telefonu poza LAN, bez konta HA; pełny cykl spotkania i PDF.
- [ ] Codzienna kopia poza hostem i odtworzenie z tego miejsca, z kluczem odzyskiwania HA.
- [ ] Fizyczne Chrome Android/Safari iOS i akceptacja porównania A z E9.

To są świadomie delegowane czynności, nie wykonany odbiór produkcyjny. Kolejny etap **E11** obejmuje końcowy odbiór i wydanie po tych próbach. Nie ogłaszamy instalacji na HA ani ukończenia całego projektu na podstawie samego lokalnego buildu.

## Źródła sprawdzone w E10

- Lokalny `../maybe-finance`: manifest repozytorium, config/build.yaml, Dockerfile, init, Nginx i usługi. Zachowano sposób lokalnego builda; nie przeniesiono host network, procesu Node ani integracji finansowych.
- [HA — konfiguracja aplikacji](https://contributors.home-assistant.io/apps/reference/configuration/): brak `image` oznacza lokalny build, `/data` jest trwały, oddzielny port Ingress i hook kopii.
- [HA — Ingress](https://contributors.home-assistant.io/apps/guides/ingress/): zaufany peer `172.30.32.2`, zmienny prefiks i `X-Ingress-Path`. Własny PIN pozostaje celowym wymaganiem Volleycrew, bez nadawania ról na podstawie HA.
- [HA — Dockerfile/build](https://contributors.home-assistant.io/apps/guides/dockerfile/): domyślny `BUILD_FROM`, zgodność ze starszym build.yaml i s6.
- [Debian base 9.3.0](https://raw.githubusercontent.com/hassio-addons/app-debian-base/v9.3.0/base/Dockerfile): Debian Trixie/s6. Istnienie obu manifestów i digesty sprawdzono w GHCR; nie wnioskowano o ich dostępności ze starego maybe-finance.

- [Docker — multiarch i emulacja](https://docs.docker.com/build/building/multi-platform/): oddzielenie budowania od uruchamiania i użycie oficjalnego binfmt w lokalnej VM.
