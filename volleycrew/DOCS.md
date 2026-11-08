> Poprawka 0.1.1: usuwa błąd instalacji `apt-get: not found`. Po udostępnieniu poprawki na `main` odśwież repozytoria w sklepie HA, sprawdź wersję 0.1.1 i ponów instalację. Nie usuwaj bazy ani konfiguracji. Pakiet nie korzysta już z `build.yaml`; baza Debian jest przypięta w Dockerfile i nie zależy od `BUILD_FROM` przekazywanego przez Supervisor.

# Instalacja i obsługa Volleycrew w Home Assistant

## Instalacja bez SSH

1. Od wersji **0.2.0 Volleycrew zawiera własny PostgreSQL 17**. Nie instaluj osobnego serwera: pozostaw `DATABASE_MODE: auto` oraz puste `POSTGRES_HOST` i `POSTGRES_PASSWORD`. Baza, użytkownik i losowe hasło powstaną automatycznie w trwałym `/data`. Istniejący host zachowuje tryb zewnętrzny.
2. Dodaj `https://github.com/arkadiusz-dalecki/volleycrew` w ustawieniach repozytoriów sklepu aplikacji HA. Kod pakietu musi najpierw znajdować się w tym repozytorium; lokalne pliki na Macu nie są automatycznie dostępne w HA. Dostęp do prywatnego repo konfigurujesz po swojej stronie.
3. Odśwież sklep, wybierz **Volleycrew** i zainstaluj. HA buduje obraz na urządzeniu. Na Pi 4 pierwsza instalacja może potrwać; dokładny RAM i czas trzeba zmierzyć na Twoim urządzeniu. Nie ma pola `image` wskazującego gotowy obraz Volleycrew ani potrzeby publikacji własnego obrazu GHCR.
4. Wypełnij opcje poniżej. Przygotuj własny adres HTTPS aplikacji i skieruj istniejący tunel/proxy na port **8200**. Konfiguracja Cloudflare pozostaje po Twojej stronie. Nie kieruj publicznego tunelu na port Ingress **8099**.
5. Wygeneruj losowy token co najmniej 32 znaków z liter, cyfr, `-` i `_`, np. w menedżerze haseł, i wpisz go jako `BOOTSTRAP_TOKEN`. To token pierwszego administratora **Volleycrew**. Wygeneruj osobny ciąg — nie używaj tokenu GitHub ani API Home Assistant. Nie wysyłaj go na czat ani nie umieszczaj w repozytorium.
6. Zapisz opcje i uruchom aplikację. Kolejność startu: walidacja → maksymalnie około 60 s oczekiwania na DB → wymagana kopia przed aktualizacją → migracje → API/Nginx. Błąd konfiguracji lub migracji zatrzymuje start. Logi nie wypisują tokenu ani hasła DB.
7. Otwórz `https://twoja-domena-aplikacji/setup#TWÓJ_TOKEN`, podaj imię, nazwisko i własny sześciocyfrowy PIN. Token jest ważny przez 30 minut od utworzenia grantu. Restart nie przedłuża ważności. Gdy wygaśnie, wpisz nowy token w opcjach i uruchom ponownie.
8. Po utworzeniu administratora usuń wartość `BOOTSTRAP_TOKEN` z opcji. Bootstrap pozostaje zamknięty w bazie, również po restarcie i zmianie tokenu. Dalszych zawodników zapraszasz z ustawień ekipy w Volleycrew.
9. Włącz uruchamianie przy starcie HA i opcjonalnie pozycję w panelu bocznym. Sprawdź normalny adres domeny oraz **Otwórz interfejs WWW** przez Ingress. W obu wejściach obowiązuje PIN Volleycrew; uprawnienia HA nie nadają administratora aplikacji.

Aplikacja nie prosi o dostęp do API HA, Dockera ani plików konfiguracji domu. Prywatny `/data` jest trwały; backend słucha tylko na `127.0.0.1:8000` wewnątrz kontenera. Ingress przyjmuje wyłącznie ruch z adresu Supervisora `172.30.32.2`.

## Opcje

| Opcja | Wartość |
| --- | --- |
| `DATABASE_MODE` | `auto`: pusty host → własna baza, podany host → zewnętrzna. Także `embedded` i `external`. Zmiana utrwalonego trybu wymaga jawnej migracji danych |
| `POSTGRES_HOST` | Puste dla własnej bazy. Dla zewnętrznej: adres serwera osiągalnego z HA |
| `POSTGRES_PORT` | Tylko zewnętrzna baza, zwykle `5432`; własna używa prywatnego 5432 |
| `POSTGRES_DB`, `POSTGRES_USER` | Opcje zewnętrzne. Własna baza używa `volleycrew` i roli bez superusera |
| `POSTGRES_PASSWORD` | Puste dla własnej bazy: trwałe hasło jest generowane automatycznie. W trybie zewnętrznym hasło użytkownika |
| `POSTGRES_SSL` | `prefer` domyślnie; `require` wymaga szyfrowania, `verify-full` dodatkowo weryfikuje certyfikat i nazwę hosta. `disable` tylko dla świadomie wybranego połączenia lokalnego |
| `PUBLIC_URL` | Adres HTTPS Volleycrew, bez ścieżki, query i fragmentu, np. `https://volleycrew.example.pl` |
| `ADDITIONAL_ORIGINS` | Lista dodatkowych **originów**, np. `["https://ha.example.pl"]`. Wpisz adres HA, jeśli używasz Ingress. Bez ścieżki i końcowego `/` |
| `TRUSTED_PROXY_CIDRS` | Tylko adres/CIDR faktycznego tunelu/proxy dochodzącego do portu 8200, np. jego pojedynczy adres `/32`. Domyślnie brak zaufanych proxy. Nie wpisuj całego Internetu ani wszystkich sieci prywatnych |
| `SESSION_SECRET` | Możesz zostawić puste: powstanie trwały losowy klucz `/data/auth.key`. Własna wartość musi mieć co najmniej 32 znaki ASCII bez spacji; zachowaj ją w backupie |
| `BOOTSTRAP_TOKEN` | Losowy token pierwszego administratora: co najmniej 32 litery/cyfry/znaki `-` i `_`; po rejestracji usuń z opcji |
| `BACKUP_HOUR` | Godzina codziennej lokalnej kopii, domyślnie `3`, według `Europe/Warsaw` |

Przy `verify-full` zapewnij klientowi zaufany certyfikat CA serwera DB zgodnie z konfiguracją PostgreSQL. W pakiecie nie ma dostępu do folderu `/ssl` HA ani automatycznego kopiowania certyfikatów z innych aplikacji.

HTTPS jest wymagany także dla strony HA otwierającej Ingress: cookies są `Secure`. Publiczny adres i adres HA mogą być różnymi originami; oba muszą być jawnie dozwolone. Ich sesje mają różne nazwy i ścieżki cookies, dzięki czemu wejścia na tym samym originie również nie kolidują.

Jeśli nie znasz adresu swojego proxy, początkowo pozostaw listę zaufania pustą, otwórz stronę przez tunel i sprawdź adres źródła w logu Nginx aplikacji. Potem dodaj wyłącznie właściwy adres/CIDR. Dopiero zaufany peer może dostarczać `X-Forwarded-For` i informację o HTTPS. Nagłówki `X-Ingress-Path` z publicznego wejścia są ignorowane. Log dostępu zawiera metodę, status i adres; pomija ścieżki, query, cookies i treść formularzy.

## Backup

Pakiet zapisuje spójny `pg_dump` w formacie custom, metadane, klucz oraz opcje w prywatnym archiwum `/data/backups/volleycrew-….tar.gz` z uprawnieniami 600. Klucz i konfiguracja są wrażliwe — archiwum nie jest samodzielnie szyfrowane.

W trybie własnej bazy PostgreSQL słucha tylko na `127.0.0.1:5432` w kontenerze; port nie jest publikowany. `/data/postgresql` zawiera trwały klaster. `/data/postgres-password` zawiera losowe hasło z prawami 0600. Nie kasuj tych plików w celu naprawy startu.

Każdy poprawny backup zapisuje atomowo także `/data/postgres-recovery.tar.gz`: kompletne logiczne archiwum do odtworzenia przez HA. HA zatrzymuje aplikację na czas swojej kopii (backup cold) i zapisuje pełne, spójne pliki klastra. Standardowe przywrócenie HA odtwarza ten klaster. Jeśli odtwarzany zestaw zawiera wyłącznie logiczne archiwum odzyskiwania, klaster jest tworzony ponownie i dane odtwarzane przed migracjami i API. Profile, PIN-y i sesje pozostają zachowane. Niekompletne archiwum blokuje start zamiast zastąpienia danych pustą bazą. Główna wersja PostgreSQL pozostaje 17; jej zmiana wymaga jawnej migracji.

Kopie powstają:

- codziennie o `BACKUP_HOUR`; po błędzie jest jedna ponowna próba godzinę później;
- przed zmianą wersji aplikacji lub schematu, zanim wystartuje API; nieudana kopia blokuje aktualizację;
- HA tworzy osobno kopię aplikacji po jej zatrzymaniu: obejmuje spójny klaster własnego PostgreSQL i konfigurację. Zewnętrzna baza nie znajduje się w katalogu aplikacji — dla external dodatkowo wykonaj świeży backup logiczny przed kopią HA albo użyj backupu serwera zewnętrznego.

Włącz automatyczne kopie HA obejmujące Volleycrew i skonfiguruj w HA **szyfrowane miejsce poza tym hostem**. Zachowaj klucz odzyskiwania kopii HA. Ten krok wykonujesz samodzielnie; samo istnienie `/data/backups` nie jest kopią poza hostem. Nie kasuj jedynej poprawnej kopii. W trybie zewnętrznym sama kopia HA nie zastępuje kopii serwera bazy.

Retencja jest ręczna: pakiet nie kasuje kopii automatycznie. Sprawdzaj log wykonania i ilość miejsca. Dla aktualizacji wykonaj również ręczną kopię HA przed naciśnięciem **Aktualizuj**, tak aby mieć poprzednią wersję opcji i kompletny zestaw do odzyskania. Przed aktualizacją brak poprawnej kopii logicznej blokuje start nowej wersji.

Dodatkowa komenda operatora wewnątrz działającego kontenera:

```sh
volleycrew-backup create
```

Ta komenda nie jest potrzebna do zwykłej instalacji ani kopii przez interfejs HA.

## Aktualizacja i cofnięcie

Nowe wydanie zmienia `version` w `config.yaml`. Po opublikowaniu kodu odśwież sklep HA, wykonaj kopię i wybierz aktualizację ręcznie. Build odbywa się podczas instalacji/aktualizacji, nie przy każdym restarcie. Po aktualizacji sprawdź start, logowanie, zapisy, ranking i PDF. Jeśli start zatrzymał się na konfiguracji, połączeniu, kopii lub migracji, popraw przyczynę; nie kasuj danych.

Cofnięcie obrazu jest bezpieczne tylko wtedy, gdy poprzedni kod wspiera bieżący schemat. W przeciwnym razie zatrzymaj aplikację i odtwórz **zgodny zestaw: poprzedni obraz/kod, poprzednia baza i konfiguracja**. Nie wykonuj automatycznego `alembic downgrade` na produkcyjnych danych.

## Odtwarzanie HA z własną bazą

Przywróć pełną kopię aplikacji w HA i uruchom zgodną wersję. Pakiet odtworzy bazę z archiwum odzyskiwania bez ręcznej konfiguracji serwera. Kopia musi zawierać cały stan aplikacji poza plikami klastra wykluczonymi przez manifest. Próba na rzeczywistym HA pozostaje obowiązkowym odbiorem po instalacji; kontenery sprawdzają niezależny pusty wolumen.

## Przenośne odtwarzanie do nowego serwera

1. Zatrzymaj aplikację, odzyskaj archiwum `.tar.gz` z kopii HA i przygotuj pustą docelową bazę na wybranym serwerze, należącą do własnego użytkownika Volleycrew. Nie nadpisuj działającej bazy ani maybe-finance.
2. Użyj obrazu odpowiadającego wersji/schematowi z `manifest.json` archiwum. Operator może zbudować go z odpowiedniej wersji repozytorium na maszynie z Dockerem. Binariów `pg_dump`/`pg_restore` nie trzeba instalować osobno w tym obrazie.
3. Przygotuj prywatny plik `.env.restore` z `VOLLEYCREW_RESTORE_DATABASE_URL=postgresql+asyncpg://…` wskazującym **wyłącznie pusty cel**. Nie przekazuj hasła jako argumentu programu ani w logu; uprawnienia pliku ustaw na 600. Hasło w URL musi być poprawnie zakodowane.
4. Przykład na maszynie operatora z Dockerem, dla wcześniej zbudowanego obrazu `volleycrew:0.2.0`:

```sh
mkdir -p restore-data
chmod 700 restore-data
chmod 600 .env.restore
docker run --rm --env-file .env.restore \
  -e VOLLEYCREW_STATE_DIR=/data \
  -v "$PWD/restore-data:/data" -v "$PWD/backup:/restore:ro" \
  --entrypoint python volleycrew:0.2.0 \
  -m app.backup restore /restore/volleycrew-KOPIA.tar.gz --confirm-empty-target
```

Polecenie odmawia odtworzenia do niepustej bazy, sprawdza format i sumy kontrolne archiwum i nie wykonuje `DROP` istniejących danych. `pg_restore` działa w jednej transakcji. Domyślnie sesje są unieważniane — zawodnicy logują się ponownie PIN-em. Wyjściowa baza nie jest modyfikowana.

`options.json` z archiwum trafia do `restored-options.json` do wglądu operatora; połączenie DB nie jest automatycznie cofane na stary serwer. Ustaw w HA poprawne opcje nowego celu i uruchom zgodny obraz. Historia, deklaracje, obecność, składy, korekty i ELO pozostają w odtworzonej DB.

Zaawansowane `--retain-sessions` odtwarza również klucz; jeśli używasz `SESSION_SECRET`, musi on odpowiadać kopii. Standardowa procedura zakłada ponowne logowanie. Nie publikuj `restored-options.json`, `.env.restore`, klucza ani archiwum w Git.

Po odzyskaniu sprawdź liczbę kont, spotkania i zapisy, prywatną historię, wynik oraz ranking, a potem PDF. Dopiero po tej kontroli wróć do zwykłego korzystania i wykonaj nową kopię poza hostem.

## Najczęstsze problemy

- **Nie startuje:** uzupełnij opcje; sprawdź osiągalność osobnego DB, hasło, TLS i prawa właściciela do własnej bazy. Nie używaj `localhost` jako adresu innego serwera/aplikacji.
- **403 po PIN-ie w Ingress:** sprawdź HTTPS i origin HA w `ADDITIONAL_ORIGINS`, odśwież stronę. Nie wyłączaj CSRF ani bezpiecznych cookies.
- **Token bootstrapu wygasł:** wpisz nowy losowy `BOOTSTRAP_TOKEN` i uruchom ponownie. Z istniejącym administratorem bootstrap jest zamknięty — użyj jego profilu i normalnego resetu PIN-u.
- **404 assetów lub przekierowanie poza Ingress:** sprawdź, czy korzystasz z przycisku WWW w HA; publiczny tunel kieruj na 8200. Nie ustawiaj stałego tokenu/prefiksu Ingress w `PUBLIC_URL`.
- **Błąd kopii/migracji:** nie kontynuuj aktualizacji bez poprawnej kopii. Readiness sprawdza DB i schemat, liveness sam proces. Chwilowy brak DB po uruchomieniu daje niegotowość bez kasowania danych.

Testy w repozytorium symulują Supervisor i HTTPS; nie oznaczają wykonanej instalacji na Twoim HA, pomiaru RAM Pi 4 ani testu telefonu spoza LAN. Raport E10 oddziela te próby od weryfikacji lokalnej.
