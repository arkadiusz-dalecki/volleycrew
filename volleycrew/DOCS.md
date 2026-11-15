> Poprawka 0.1.1: usuwa błąd instalacji `apt-get: not found`. Po udostępnieniu poprawki na `main` odśwież repozytoria w sklepie HA, sprawdź wersję 0.1.1 i ponów instalację. Nie usuwaj bazy ani konfiguracji. Pakiet nie korzysta już z `build.yaml`; baza Debian jest przypięta w Dockerfile i nie zależy od `BUILD_FROM` przekazywanego przez Supervisor.

# Instalacja i obsługa Volleycrew w Home Assistant

## Instalacja bez SSH

1. Od wersji **0.2.0 Volleycrew zawiera własny PostgreSQL 17**. Nie instaluj osobnego serwera: pozostaw `DATABASE_MODE: auto` oraz puste `POSTGRES_HOST` i `POSTGRES_PASSWORD`. Baza, użytkownik i losowe hasło powstaną automatycznie w trwałym `/data`. Istniejący host zachowuje tryb zewnętrzny.
2. Dodaj `https://github.com/arkadiusz-dalecki/volleycrew` w ustawieniach repozytoriów sklepu aplikacji HA. Kod pakietu musi najpierw znajdować się w tym repozytorium; lokalne pliki na Macu nie są automatycznie dostępne w HA. Dostęp do prywatnego repo konfigurujesz po swojej stronie.
3. Odśwież sklep, wybierz **Volleycrew** i zainstaluj. HA buduje obraz na urządzeniu. Na Pi 4 pierwsza instalacja może potrwać; dokładny RAM i czas trzeba zmierzyć na Twoim urządzeniu. Nie ma pola `image` wskazującego gotowy obraz Volleycrew ani potrzeby publikacji własnego obrazu GHCR.
4. Wypełnij opcje poniżej. Przygotuj własny adres HTTPS aplikacji i skieruj istniejący tunel/proxy na port **8200**. Konfiguracja Cloudflare pozostaje po Twojej stronie. Nie kieruj publicznego tunelu na port Ingress **8099**.
5. Wygeneruj losowy token co najmniej 32 znaków z liter, cyfr, `-` i `_`, np. w menedżerze haseł, i wpisz go jako `BOOTSTRAP_TOKEN`. To token pierwszego administratora **Volleycrew**. Wygeneruj osobny ciąg — nie używaj tokenu GitHub ani API Home Assistant. Nie wysyłaj go na czat ani nie umieszczaj w repozytorium.
6. Zapisz opcje i uruchom aplikację. Kolejność startu: walidacja → maksymalnie około 60 s oczekiwania na DB → wymagana kopia przed aktualizacją → migracje → API/Nginx. Błąd konfiguracji lub migracji zatrzymuje start. Logi nie wypisują tokenu ani hasła DB.
7. Otwórz `https://twoja-domena-aplikacji/setup#TWÓJ_TOKEN`, podaj imię, nazwisko i login i własne hasło (15–128 znaków). Token jest ważny przez 30 minut od utworzenia grantu. Restart nie przedłuża ważności. Gdy wygaśnie, wpisz nowy token w opcjach i uruchom ponownie.
8. Po utworzeniu administratora usuń wartość `BOOTSTRAP_TOKEN` z opcji. Bootstrap pozostaje zamknięty w bazie, również po restarcie i zmianie tokenu. Dalszych zawodników zapraszasz z ustawień ekipy w Volleycrew.
9. Włącz uruchamianie przy starcie HA i opcjonalnie pozycję w panelu bocznym. Sprawdź normalny adres domeny oraz **Otwórz interfejs WWW** przez Ingress. W obu wejściach obowiązuje hasło Volleycrew; uprawnienia HA nie nadają administratora aplikacji.

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

Każdy poprawny backup zapisuje atomowo także `/data/postgres-recovery.tar.gz`: kompletne logiczne archiwum do odtworzenia przez HA. HA zatrzymuje aplikację na czas swojej kopii (backup cold) i zapisuje pełne, spójne pliki klastra. Standardowe przywrócenie HA odtwarza ten klaster. Jeśli odtwarzany zestaw zawiera wyłącznie logiczne archiwum odzyskiwania, klaster jest tworzony ponownie i dane odtwarzane przed migracjami i API. Profile, hasła i sesje pozostają zachowane. Niekompletne archiwum blokuje start zamiast zastąpienia danych pustą bazą. Główna wersja PostgreSQL pozostaje 17; jej zmiana wymaga jawnej migracji.

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

Polecenie odmawia odtworzenia do niepustej bazy, sprawdza format i sumy kontrolne archiwum i nie wykonuje `DROP` istniejących danych. `pg_restore` działa w jednej transakcji. Domyślnie sesje są unieważniane — zawodnicy logują się ponownie hasłem. Wyjściowa baza nie jest modyfikowana.

`options.json` z archiwum trafia do `restored-options.json` do wglądu operatora; połączenie DB nie jest automatycznie cofane na stary serwer. Ustaw w HA poprawne opcje nowego celu i uruchom zgodny obraz. Historia, deklaracje, obecność, składy, korekty i ELO pozostają w odtworzonej DB.

Zaawansowane `--retain-sessions` odtwarza również klucz; jeśli używasz `SESSION_SECRET`, musi on odpowiadać kopii. Standardowa procedura zakłada ponowne logowanie. Nie publikuj `restored-options.json`, `.env.restore`, klucza ani archiwum w Git.

Po odzyskaniu sprawdź liczbę kont, spotkania i zapisy, prywatną historię, wynik oraz ranking, a potem PDF. Dopiero po tej kontroli wróć do zwykłego korzystania i wykonaj nową kopię poza hostem.

## Najczęstsze problemy

- **Nie startuje:** uzupełnij opcje; sprawdź osiągalność osobnego DB, hasło, TLS i prawa właściciela do własnej bazy. Nie używaj `localhost` jako adresu innego serwera/aplikacji.
- **403 po logowaniu w Ingress:** sprawdź HTTPS i origin HA w `ADDITIONAL_ORIGINS`, odśwież stronę. Nie wyłączaj CSRF ani bezpiecznych cookies.
- **Token bootstrapu wygasł:** wpisz nowy losowy `BOOTSTRAP_TOKEN` i uruchom ponownie. Z istniejącym administratorem bootstrap jest zamknięty — użyj jego profilu i normalnego resetu hasła.
- **404 assetów lub przekierowanie poza Ingress:** sprawdź, czy korzystasz z przycisku WWW w HA; publiczny tunel kieruj na 8200. Nie ustawiaj stałego tokenu/prefiksu Ingress w `PUBLIC_URL`.
- **Błąd kopii/migracji:** nie kontynuuj aktualizacji bez poprawnej kopii. Readiness sprawdza DB i schemat, liveness sam proces. Chwilowy brak DB po uruchomieniu daje niegotowość bez kasowania danych.

Testy w repozytorium symulują Supervisor i HTTPS; nie oznaczają wykonanej instalacji na Twoim HA, pomiaru RAM Pi 4 ani testu telefonu spoza LAN. Raport E10 oddziela te próby od weryfikacji lokalnej.


## Kalendarz i lista do podpisów

W kalendarzu administrator ma „Twoje serie spotkań”. „Edytuj serię” otwiera aktualne parametry i podgląd przyszłych zmian; skrócenie zakresu usuwa wypadające terminy. „Usuń serię” usuwa jej przyszłe terminy, zachowując rozegraną historię, inne serie i pojedyncze dodatkowe spotkania. Na kafelku spotkania „Usuń spotkanie” usuwa także odwołany wpis z widoku i zapobiega odtworzeniu tego wystąpienia.

Aby wydrukować listę przed wyjściem z domu, otwórz spotkanie jako administrator i wybierz „Lista podpisów” w panelu organizatora. Przed sprawdzeniem obecności dokument zawiera osoby z potwierdzonym miejscem, bez rezerwy i oczekujących. Wybierz „Pobierz aktualny PDF” i wydrukuj A4 w skali 100%. Wydruk nie zatwierdza obecności. Po sprawdzeniu i zatwierdzeniu obecności na sali ten sam przycisk pobiera listę faktycznie obecnych.

## Wstępne drużyny

Przed sprawdzeniem obecności szczegóły spotkania pokazują boisko z osób z potwierdzonym miejscem, domyślnie wyrównane według ELO. Po własnym zapisie lub rezygnacji boisko odświeża się od razu; pozostali widzą zmiany najpóźniej przy kolejnym odświeżeniu co 30 sekund.

Administrator może losować, zamieniać osoby przez dotknięcie zawodników z przeciwnych stron lub wrócić do „Według ELO”. Podział widzi cała ekipa, a zmiana deklaracji resetuje go do aktualnego ELO. Na sali sprawdź i zatwierdź obecność, następnie w kroku „Drużyny” wybierz „Użyj wstępnego podziału”. Gdy obecni różnią się od zapisanych, aplikacja wyrówna faktyczny skład od nowa.

## Obserwowanie prób logowania

W logach aplikacji HA wyszukuj zdarzenia JSON z nazwami `auth_failed`, `auth_invalid_link`, `auth_csrf_rejected`, `auth_invalid_input`, `auth_rate_limited`, `auth_burst_limited` i `auth_succeeded`. Pole `operation` wskazuje login/rejestrację/bootstrap/reset, a `source` to odcisk HMAC źródła pozwalający porównać próby bez wypisywania adresu IP w tych zdarzeniach. Klucz instancji musi pozostać ten sam, aby odciski były porównywalne po restarcie. Osobny log dostępu Nginx nadal zawiera adres zgodnie z wcześniej opisaną konfiguracją.

Powtarzające się błędy jednego źródła lub limity z wielu źródeł wymagają sprawdzenia ruchu na tunelu/proxy. Błędy CSRF po zmianie adresu mogą wskazywać również błędny origin/proxy. `security_logs_suppressed` oznacza przekroczenie 60 wpisów bezpieczeństwa/minutę/proces; kolejne wpisy są pomijane do końca okna, aby ruch nie zapełniał logów. Liczba wpisów nie jest więc liczbą wszystkich prób. Logi nie stanowią automatycznych alertów ani zewnętrznego monitoringu.

Dodatkowe ograniczenie serii żądań działa przed bazą: na źródło seria 10 i odnawianie 30/min, globalnie seria 20 i odnawianie 4/s, dla czterech operacji wejścia. Poprawnie skonfiguruj zaufane proxy; bez tego wielu użytkowników może dzielić limit jednego adresu proxy, a Ingress dzieli źródło Supervisor. HTTP 429 zawiera czas ponowienia. Restart zeruje wyłącznie dodatkowy limiter w pamięci; właściwe liczniki błędnych haseł i operacji pozostają w PostgreSQL. Zmiana na wiele workerów wymaga ponownego doboru ochrony wspólnej dla procesów. Ochronę przed zalaniem łącza/połączeń konfiguruje się na proxy/tunelu.

Linki `#…` po otwarciu znikają z adresu. Po odświeżeniu strony otwórz ponownie oryginalny link z wiadomości. Dawny format z tokenem w ścieżce nie jest już obsługiwany; poproś o aktualny link. Samo otwarcie linku resetu nadal go nie zużywa. Nie udostępniaj linków ani plików diagnostycznych zawierających sekrety.

## Opcjonalne logowanie Google

Google może połączyć istniejący profil albo zarejestrować nowy z aktywnego zaproszenia. Na ekranie zaproszenia zawodnik wybiera Dołącz przez Google, sprawdza podpowiedziane imię/nazwisko, może je poprawić i zatwierdza dołączenie. Nie musi ustawiać loginu ani hasła. Zwykła rejestracja loginem i hasłem pozostaje dostępna. Pierwsze połączenie: login i hasło → Mój profil → Logowanie Google → ponowne potwierdzenie hasła → wybór konta Google. Później wystarcza „Zaloguj przez Google”. Odłączenie wymaga hasła i unieważnia pozostałe sesje. **Reset hasła wydany przez organizatora odłącza również Google** — po odzyskaniu konta trzeba je połączyć ponownie. Samodzielna zmiana hasła zachowuje połączenie.

Konfiguracja operatora:

1. W [Google Cloud Console](https://console.cloud.google.com/) wybierz własny projekt i otwórz **Google Auth Platform**. Uzupełnij Branding (nazwa, kontakt, wymagane domeny/strony) i Audience. Dla prywatnych kont Gmail aplikacja ma odbiorców External. Nasza integracja żąda tylko `openid profile`; Google przewiduje dla podstawowego logowania wyjątek od wymogu listy test users i siedmiodniowego wygaśnięcia autoryzacji. Sprawdź bieżące wymagania w Audience. Udostępnienie pozostałym zawodnikom wymaga odpowiedniego statusu publikacji; wykonaj wymagania pokazane przez Google dla Twojego projektu.
2. W Clients utwórz klienta OAuth typu **Web application**. Zarejestruj dokładny Authorized redirect URI: `https://TWOJA-DOMENA/api/v1/auth/google/callback`. Użyj domeny z PUBLIC_URL, bez dynamicznego prefiksu Ingress. Nie konfigurujemy tu klienta Android/iOS ani service account.
3. W opcjach aplikacji HA ustaw razem `GOOGLE_CLIENT_ID` i `GOOGLE_CLIENT_SECRET`, zapisane dla tego samego klienta. Sekret wpisz wyłącznie w opcjach HA, nie w repozytorium ani na czacie. Uruchom ponownie aplikację. Brak obu wartości wyłącza przycisk Google; niepełna para jest błędem konfiguracji. PUBLIC_URL musi wskazywać działającą własną domenę HTTPS, a proxy kierować do portu 8200.
4. Otwórz PUBLIC_URL na telefonie, zaloguj się hasłem i połącz Google w profilu. Wyloguj się, użyj Google i sprawdź, że otworzył się ten sam profil z tymi samymi zapisami i rolą. Przetestuj również anulowanie, odłączenie i ponowne wejście hasłem.

Żądany zakres to `openid profile`, bez dostępu do Gmaila, Drive czy Kalendarza. Backend weryfikuje token i wiąże profil po identyfikatorze Google. Imię/nazwisko są podpowiedzią do edytowalnego formularza dołączenia; nie aktualizują danych istniejącego profilu podczas logowania. Nie zapisujemy e-maila, zdjęcia ani tokenów dostępu. Przycisk działa jako pełne przekierowanie przeglądarki. Z panelu HA/Ingress otwiera główną domenę w nowej karcie; nie loguje automatycznie do sesji Ingress i nie nadaje uprawnień z konta HA.

Własny adres HTTPS i wychodzący HTTPS do `oauth2.googleapis.com` oraz `www.googleapis.com` muszą działać. Czas hosta musi być poprawny. Po zmianie domeny uaktualnij PUBLIC_URL, redirect URI klienta Google i konfigurację proxy. Błąd `redirect_uri_mismatch` oznacza różnicę adresu w Google; niepoprawny client/secret wymaga sprawdzenia pary danych. Konto „niepołączone” wymaga wejścia hasłem i połączenia na własnym profilu — aplikacja nie dopasowuje kont po nazwisku lub e-mailu.

Callback otrzymuje krótkotrwały kod w query. Nginx pakietu pomija adres/query w logu dostępu, backend i lokalny runner mają wyłączony access log, a logi HTTPX są ograniczone do WARNING. Zachowaj tę ochronę także na zewnętrznym proxy; nie loguj body ani query callbacku. W monitoringu pojawiają się `auth_google_succeeded` i `auth_google_failed`, bez kodów, nonce, Google sub i sekretów. Dane klienta są przekazywane w prywatnych plikach środowiska i objęte dotychczasową ochroną kopii konfiguracji.

Migracja `0011_google_login` dodaje dwie tabele i zachowuje dotychczasowe profile. Przed aktualizacją wykonaj zwykłą kopię. Wyłączenie opcji Google (wyczyszczenie **obu** wartości) zachowuje powiązania i logowanie hasłem; odłączenie powiązania jest osobną akcją. Lokalnie używa się `VOLLEYCREW_GOOGLE_CLIENT_ID` i `VOLLEYCREW_GOOGLE_CLIENT_SECRET`, z osobnym klientem/redirect URI dla localhost. Testy automatyczne używają wyłącznie odizolowanego dostawcy testowego; nie potwierdzają konfiguracji Twojego projektu Google.

## Przejście z PIN-u na login i hasło

Zmiana obejmuje migrację `0012_password_login`. Stare PIN-y nie działają jako hasła. Sesje i dawne linki resetu są unieważnione; profile, zapisy, historia i ELO pozostają w bazie. Zgodnie z decyzją użytkownika nie ma migracji graczy — obecnie zarejestrowany jest wyłącznie organizator.

Po aktualizacji wykonaj jednorazową konfigurację dostępu organizatora:

1. Przed aktualizacją zrób kopię aplikacji/bazy.
2. W HA wpisz **nowy**, losowy `BOOTSTRAP_TOKEN` (minimum 32 znaki) i uruchom ponownie Volleycrew. Stary użyty token nie jest reaktywowany przez restart.
3. Otwórz `PUBLIC_URL/setup#NOWY_TOKEN`, wybierz własny login i hasło (15–128 znaków). Istniejący profil administratora zachowa ID, dane i historię; pola imienia/nazwiska służą nowej instalacji. Nie powstaje drugi administrator.
4. Sprawdź logowanie loginem i hasłem; wyczyść BOOTSTRAP_TOKEN w opcjach. Bootstrap zamyka się ponownie po ustawieniu hasła. Jeżeli Google było połączone z tym kontem, połącz je ponownie w profilu, potwierdzając nowe hasło.

Poza HA alternatywą jest `npm run auth:bootstrap -- --rotate` w prawidłowym środowisku aplikacji. Link ma 30 minut i jest jednorazowy. Nie ma hasła domyślnego, automatycznego użycia starego PIN-u ani kasowania produkcyjnej bazy. Login jest osobną nazwą 3–32 znaków: litery ASCII, cyfry, kropka, myślnik i podkreślenie; wielkość liter nie rozróżnia kont. Hasła zachowują spacje i Unicode dokładnie.

Zawodnik rejestruje się z zaproszenia przez Google lub podając własny login i hasło. Organizator wydaje 30-minutowy link resetu, którym można ustawić hasło i odzyskać/zastąpić login. Zmiana/reset hasła wylogowuje inne urządzenia. Reset od organizatora odłącza również Google. Login nie pojawia się na listach uczestników ani wydruku. Publiczny katalog profili i dawne endpointy PIN-u usunięto.

Cofnięcie migracji nie odtwarza PIN-ów ani loginów. Do rollbacku dostępu przywróć zgodną kopię bazy i wcześniejszy obraz. Zmiany logowania są dostępne w pakiecie 0.3.5.

## Dołączanie przez Google

1. Organizator tworzy zwykły link zaproszenia i przekazuje go zawodnikowi.
2. Zawodnik otwiera link i wybiera **Dołącz przez Google**, bez wypełniania formularza hasła.
3. Po wyborze konta Google wraca do **Sprawdź dane i dołącz**. Imię i nazwisko są podpowiedziane, jeśli Google je udostępniło; można je dowolnie poprawić lub uzupełnić. Przydomek jest opcjonalny.
4. **Dołączam do gry** tworzy profil gościa i loguje do grupy. Wcześniejsze zamknięcie formularza nie zakłada konta.

Konto korzystające wyłącznie z Google nie ma lokalnego loginu/hasła. W profilu **Ustaw login i hasło** wymaga nowego potwierdzenia tego samego konta Google. Potem dostępne są obie metody. Odłączenie Google wymaga ustawionego hasła, aby nie odciąć ostatniej metody dostępu. Organizator może też wydać zwykły link resetu, aby odzyskać dostęp po utracie Google; ten reset odłącza poprzednie Google.

Ponowne dołączanie tym samym kontem Google otwiera istniejący profil, bez zmiany jego nazwiska/roli i bez duplikatu. Aplikacja nie dopasowuje kont po e-mailu ani nazwisku; osoba z wcześniejszym kontem lokalnym powinna zalogować się do niego i połączyć Google w profilu. Zaproszenie musi być aktywne przy starcie, po powrocie z Google i przy zatwierdzeniu. Cofnięty link nie zakłada nowego konta.

Formularz potwierdzenia wygasa po 10 minutach od rozpoczęcia Google i jest związany z tą przeglądarką. Odświeżenie wymaga ponownego otwarcia zaproszenia; sekret nie jest utrwalany w adresie/storage. Ingress otwiera zaproszenie pod głównym PUBLIC_URL w osobnej karcie, bez przenoszenia sesji. Przy limicie prób odczekaj czas pokazany przez aplikację i ponów kliknięcie; przy błędzie odczytu formularza jest przycisk ponowienia.

Migracja `0013_google_registration` dodaje jednorazowe potwierdzenia i kontekst zaproszenia/rodzaj przepływu Google. Nie zmienia zapisów, historii ani ELO. Usuwa dawne powiązania Google profili bez ustawionych danych po przejściu z PIN-u; nie nadaje im wstecznie dostępu Google-only. Podczas cofania kodu przywróć zgodny backup — wcześniejsze wersje nie obsługują kont bez hasła. Dane klienta Google i callback pozostają te same; w Google Auth Platform sprawdź deklarację podstawowego zakresu `profile`. Rzeczywiste konta i fizyczny HA/telefon/PWA wymagają osobnego odbioru po konfiguracji.
