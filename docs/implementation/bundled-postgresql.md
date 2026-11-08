# Własny PostgreSQL — Volleycrew 0.2.0

Decyzja użytkownika 2026-11-08 zastępuje wcześniejsze wymaganie osobnego serwera. Użytkownik nie ma PostgreSQL i chce instalować kompletną aplikację w HA. Agent zmienia pakiet i testuje kontenery; nie modyfikuje działającego HA ani tunelu.

## Implementacja

PostgreSQL 17 jest częścią obrazu Debian/s6. Stan klastra w /data/postgresql, hasło generowane raz w /data/postgres-password (0600), osobna rola aplikacji bez superusera, listener tylko 127.0.0.1:5432. Brak mapowania portu bazy. Parametry pamięci: shared_buffers 32 MB, max_connections 30, work_mem 2 MB; pomiar na fizycznym Pi pozostaje do odbioru.

DATABASE_MODE=auto i pusty host wybierają własną bazę; istniejący host zachowuje external. Zmiana utrwalonego trybu lub brak istniejącego hasła blokują start, nie tworzą pustej alternatywy. Główna wersja PG nie jest automatycznie podnoszona. Etapy s6: konfiguracja → inicjalizacja/start bazy → backup/migracje/bootstrap → przekazanie PostgreSQL do nadzorowanej usługi. Awaria bazy kończy kontener.

HA używa backup cold: zatrzymuje aplikację i zapisuje spójny klaster, również gdy aplikacja była już zatrzymana. To dodaje krótką przerwę na czas kopii. Codzienny pg_dump i obowiązkowy backup przed aktualizacją pozostają online. External wymaga świeżej kopii logicznej przed kopią HA lub niezależnej kopii serwera — sam katalog aplikacji nie zawiera zewnętrznej bazy.

Dodatkowe atomowo zapisywane archiwum postgres-recovery.tar.gz umożliwia odtworzenie logiczne na pustym klastrze przed migracjami, jeśli plików klastra nie ma w przenoszonym zestawie. Przy braku archiwum albo jego uszkodzeniu start jest blokowany. Standardowa kopia HA zawiera cały klaster i nie wymaga tego mechanizmu. Próba migracji istniejącej bazy do innego trybu jest osobną operacją, poza automatyczną aktualizacją.

## Weryfikacja

Lokalnie na produkcyjnym ARM64 sprawdzono własny start, migracje i prawdziwe utworzenie administratora, restart oraz SIGKILL, odtworzenie logiczne na osobnym wolumenie i blokadę brakującego archiwum. Końcowa rozszerzona próba obejmuje także kopię zatrzymanego klastra i backup przy aktualizacji; jej wynik oraz oba CPU są w Checks PR.

Regresja zewnętrznej bazy na PostgreSQL 17: 118 testów backendu zaliczonych; następnie dodano test bezpiecznej diagnostyki walidacji. 11 testów konfiguracji zaliczonych, lint zaliczony. Pełny scenariusz obrazu zewnętrznego: start, błędne opcje/DB/migracja, HTTPS, dwa prefiksy Ingress, cookies/CSRF, restart, backup przed aktualizacją, zapisy/obecność/drużyny/PDF/wynik/ELO, utrata DB i restore na osobnej instancji — zaliczone lokalnie. Obejmuje 6 prób UI Chromium/WebKit.

CI buduje oba CPU z awaryjnym BUILD_FROM, wykonuje dotychczasową regresję external oraz nowy scripts/test_bundled_database.py. Zdalny wynik wymaga potwierdzenia w PR. Kopie i hasła testowe nie trafiają do artefaktów CI; wyłącznie logi i materiały testów UI.

## Odbiór użytkownika

Po scaleniu i odświeżeniu sklepu zainstalować 0.2.0. Zachować PUBLIC_URL/token; pozostawić DATABASE_MODE=auto i pusty POSTGRES_HOST. Nie trzeba zakładać bazy ani hasła. Sprawdzić administratora, restart HA, kopię i odtworzenie na docelowym Pi oraz magazyn kopii poza hostem. Instalacja i pomiar zasobów Pi nie są deklarowane jako wykonane przez agenta.

Źródła: [PostgreSQL initdb](https://www.postgresql.org/docs/17/app-initdb.html), [wymagania spójnej kopii plików](https://www.postgresql.org/docs/17/backup-file.html), [backup cold w HA](https://contributors.home-assistant.io/apps/reference/configuration/).
