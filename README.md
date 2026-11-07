# Volleycrew

Aplikacja do organizacji spotkań siatkarskich. Docelowo instalowana jako aplikacja Home Assistant, z budowaniem lokalnie w HA, tak jak maybe-finance.

## Aktualny stan

E1 dostarcza uruchamialny szkielet: React/TypeScript/Vite w zaakceptowanym układzie A, API FastAPI, PostgreSQL, migracje, kontrakt OpenAPI i testy. E2 dodaje rejestrację z zaproszenia, maskowany katalog profili, PIN, trwałe sesje, reset i blokowanie dostępu. E3 dodaje kalendarz z harmonogramem, najbliższy termin i trwałe szczegóły spotkania. E4 dodaje zapisy, prywatne priorytety, rezerwę i propozycje miejsc. E5 dodaje harmonogram od wybranej daty, pojedyncze przesunięcia, odwołania i nowe potwierdzenia udziału. E6 dodaje obecność, prywatną historię i korekty oraz drużyny na boisku wariantu A. E7 dodaje administracyjny podgląd i pobranie listy podpisów PDF. E8 dodaje wyniki, ranking ELO, historię punktów i pełne korekty z przeliczeniem późniejszych spotkań. E9 dopracowuje dostępność i obsługę telefonu, dialogi, utratę sieci/sesji oraz dodaje manifest. Lokalna kontrola Chromium/WebKit jest wykonana; fizyczne telefony i akceptacja porównania UI pozostają do odbioru.

[Plan implementacji](docs/implementation/README.md) · [Raport i ograniczenia E1](docs/implementation/e1-report.md) · [Decyzje produktu](docs/implementation/decisions.md) · [Raport E2](docs/implementation/e2-report.md) · [Raport E3](docs/implementation/e3-report.md) · [Raport E4](docs/implementation/e4-report.md) · [Raport E5](docs/implementation/e5-report.md) · [Raport E6](docs/implementation/e6-report.md) · [Raport E7](docs/implementation/e7-report.md) · [Raport E8](docs/implementation/e8-report.md) · [Raport E9 i porównanie UI](docs/implementation/e9-report.md) · [Pakiet HA — E10](docs/implementation/e10-report.md)

## Uruchomienie developerskie

Wymagania: Node 24 LTS (dopuszczone również 26), npm, Python 3.9+ do uruchomienia skryptu oraz Docker Compose do lokalnej PostgreSQL 17. Backend działa na Pythonie 3.13, pobieranym przez uv. Jeśli uv nie jest dostępne, setup instaluje je do ignorowanego `.tools/`. Pierwsza instalacja wymaga internetu.

```sh
npm run setup
npm run db:up
npm run dev
```

Setup instaluje zależności z lockfile i tworzy `.env` z `.env.example`, jeżeli plik jeszcze nie istnieje. Dev stosuje migracje przed startem API, potem uruchamia oba serwery. Ctrl+C zatrzymuje frontend i API; bazę zatrzymuje osobne `npm run db:stop` (bez kasowania wolumenu).

- Aplikacja: http://localhost:5173
- API / OpenAPI: http://127.0.0.1:8201/docs
- Liveness: http://127.0.0.1:8201/api/v1/health/live
- Readiness: http://127.0.0.1:8201/api/v1/health/ready

Readiness wymaga dostępnej bazy i aktualnego schematu Alembic. Odpowiedź 503 jest poprawna, gdy baza lub migracja nie są gotowe; liveness nadal może odpowiadać 200.

Lokalna baza ma port 55432 i nazwę `volleycrew_dev`. Dane w `.env.example` i Compose są wyłącznie developerskie. Istniejący własny PostgreSQL można podłączyć przez `VOLLEYCREW_DATABASE_URL` w `.env`; użyj oddzielnej bazy, niezwiązanej z produkcją ani maybe-finance. Format: `postgresql+asyncpg://user:password@host:port/database`. Lokalny development sprawdzono również na odizolowanej PostgreSQL 14.24; pełną regresję na PostgreSQL 17 i produkcyjne obrazy obu architektur zweryfikowano w E10.

## Pierwszy organizator i dostęp

Po uruchomieniu lokalnych serwerów wygeneruj link inicjalizacji:

```sh
npm run auth:bootstrap
```

Otwórz wypisany adres `/setup#…` w przeglądarce i sam ustaw sześciocyfrowy PIN. Link działa raz przez 30 minut. Gdy wygaśnie, `npm run auth:bootstrap -- --rotate` unieważni stary i wygeneruje nowy. Po utworzeniu administratora komenda odmawia ponownej inicjalizacji. Nie ma domyślnego PIN-u ani konta produkcyjnego zasianego testowymi danymi.

W „Mój profil” → „Ustawienia ekipy” organizator tworzy link zaproszenia, unieważnia go, wydaje jednorazowe linki resetu PIN-u, zmienia prywatny status priorytetu i blokuje dostęp. Nowy profil zawsze jest gościem; inne urządzenie wymaga wyboru maskowanego profilu i PIN-u. Link pokazujemy w całości tylko po utworzeniu — skopiuj go przed opuszczeniem widoku. Przy zmianie/resetowaniu PIN-u pozostałe urządzenia tracą sesje.

Ustawienia lokalne: `VOLLEYCREW_PUBLIC_URL=http://localhost:5173`, `VOLLEYCREW_COOKIE_SECURE=false`. Poza localhost wymagane HTTPS i domyślne Secure=true. Sekret podpisujący CSRF jest generowany w `.runtime/auth.key` z prawami 0600; zachowaj go między restartami albo podaj `VOLLEYCREW_SESSION_SECRET` (min. 32 znaki) przez środowisko. Nie dodawaj go do repozytorium. Ruch proxy jest domyślnie niezaufany; `VOLLEYCREW_TRUSTED_PROXY_CIDRS` i `VOLLEYCREW_ADDITIONAL_ORIGINS` to jawne listy JSON, do konfiguracji i sprawdzenia w E10. Uvicorn działa z `--no-proxy-headers`, weryfikację wykonuje aplikacja.

## Kalendarz i terminy

Po zalogowaniu najbliższy termin jest pobierany z harmonogramu. W kalendarzu wybierz miesiąc strzałkami lub polem „Miesiąc”, następnie otwórz spotkanie. Adres szczegółów działa po odświeżeniu. Samo otwarcie nie zapisuje na grę; udział deklarujesz osobnym przyciskiem „Będę”/„Nie będę”. Organizator zmienia harmonogram w ustawieniach albo pojedynczy termin w szczegółach spotkania. Domyślna reguła to wtorek 18:00–20:00, I LO w Gdańsku, Europe/Warsaw. Miniona historia zawiera tylko utrwalone spotkania.

Zmiana stałej reguły ma podgląd i osobne zatwierdzenie. Przesuwa istniejące terminy w tym samym tygodniu, zachowuje indywidualne wyjątki i odwołania, obejmuje także przyszłe niewytworzone spotkania. Po zmianie terminu potwierdź udział od nowa — dotychczasowe miejsce czeka bez automatycznego timeoutu. Organizator może je ręcznie zwolnić. Stare oferty z rezerwy nie obowiązują; nową propozycję trzeba jawnie przyjąć.

Przy pełnej liście trafiasz na rezerwę. Zwolnione miejsce jest rezerwowane dla pierwszej osoby z kolejki, a organizator aktywuje propozycję i ręcznie powiadamia na Messengerze. Dopiero „Przyjmuję miejsce” potwierdza udział. Organizator może przekazać miejsce dalej z potwierdzeniem; nie ma automatycznego timeoutu. Rezygnacja pokazuje informację o granicy 24 godzin i ewentualnym wyjątku późnej oferty. Blokada profilu zwalnia przyszłe miejsca oraz rezerwacje, pozostawiając historię.

## Obsługa spotkania na sali (E6)

W szczegółach spotkania organizator oznacza obecność i zapisuje szkic, następnie osobno zatwierdza sprawdzoną listę. Zatwierdzenie jest dostępne od rozpoczęcia gry. Nieobecni otrzymują prywatny wpis historii, a ich miejsca przechodzą do obsługi rezerwy. Fizycznie obecnego adresata rezerwacji można potwierdzić na sali. Dopisanie innego istniejącego profilu wymaga wolnego, niezarezerwowanego miejsca; powrót wcześniej oznaczonego nieobecnego wymaga korekty z powodem.

Po obecności wybierz losowanie lub wyrównanie drużyn. Na boisku dotknij zawodnika, potem osoby z drugiej drużyny, aby je zamienić — także przy 7:7. Siódma osoba jest w rotacji pod boiskiem. Zapisz ręczne poprawki i zatwierdź składy; dopiero wtedy zobaczy je ekipa. Otwarcie do poprawy wymaga powodu. Podział działa dla 2–14 obecnych, najwyżej po 7 na stronę i z różnicą liczebności najwyżej 1. Podział korzysta z aktualnych punktów ELO; lista PDF jest dostępna po zatwierdzeniu obecności, a zapis wyniku w kolejnym kroku panelu.

Własna prywatna historia jest w profilu, a organizator otwiera cudzą historię z ustawień ekipy lub listy obecności. Korekty zachowują źródłowy wpis, autora, datę i powód. Konflikt wersji nie nadpisuje zmian z innej karty. Przy utracie odpowiedzi użyj „Ponów tę operację” — powtórzenie nie tworzy kolejnego zatwierdzenia ani losowania.

## Lista podpisów PDF (E7)

Po zatwierdzeniu obecności wybierz „Lista podpisów” w panelu organizatora. Zobaczysz podgląd PDF dla szkoły i przycisk „Pobierz aktualny PDF”. Pobranie zawsze odczytuje aktualną obecność, także po korekcie w innej karcie. Na liście są wyłącznie faktycznie obecne osoby; nie ma rezerwy, przydomków, statusów ani historii. Drukuj na papierze A4 w skali 100%. Zwykła lista 14 osób mieści się na stronie; skrajnie długie nazwiska przechodzą na kolejną stronę bez ucinania.

PDF powstaje lokalnie przez ReportLab z dołączonymi fontami Noto Sans i licencją w `backend/app/assets/fonts/`. PDF.js renderuje podgląd na telefonie bez zewnętrznego serwisu/CDN. Poppler służy wyłącznie do wizualnej kontroli podczas developmentu i nie jest zależnością runtime aplikacji. Nie jest potrzebna nowa migracja bazy.

## Wynik i ranking ELO (E8)

Po zatwierdzeniu drużyn przejdź do „03 Wynik”, wpisz sety A/B, pokaż podgląd punktów i osobno zatwierdź zapis. Wynik 0:0 zamyka spotkanie bez rozegranych setów i bez punktów za ten mecz. Każda osoba drużyny, również rotująca, otrzymuje tę samą deltę. K=32, skala oczekiwań 400; znaczenie ma proporcja setów i siła drużyn, więc w szczególnym przypadku wygrana poniżej oczekiwań może obniżyć punkty.

„Ranking” pokazuje wszystkich zawodników, punkty i historię spotkań. Kliknięcie nazwiska otwiera historię przed → zmiana → po. Wartości są pokazywane do jednego miejsca po przecinku, ale obliczenia i baza nie są tak zaokrąglane.

„Skoryguj wynik lub składy” wymaga powodu i nowego podglądu. Można poprawić również historyczną faktyczną obecność: każda dodana/usunięta osoba wymaga osobnej, prywatnej korekty z powodem. Dawne wyniki/składy pozostają zachowane, a ranking jest przeliczany według rozpoczęcia meczu i stałego ID, również dla późniejszych spotkań. Powody i historia obecności nie są publiczne dla grupy. Nie trzeba zapisywać kolejnych wyników w kolejności dat.

Migracja `0007_results` dodaje wersje wyników i materializację rankingu; snapshoty ELO używają Numeric. Wykonaj `npm run db:migrate` przed uruchomieniem nowego API. Downgrade po zapisaniu wyników jest blokowany, aby nie usuwać historii; backup/restore i aktualizację opisuje instrukcja HA oraz raport E10.

## Sprawdzenia

```sh
npm run lint
npm run typecheck
npm run api:check
npm run test:backend
npm run test:frontend
npm run build
```

Testy backendu bez `VOLLEYCREW_TEST_DATABASE_URL` pomijają integrację PostgreSQL. Żeby wykonać ją lokalnie z Compose, jednorazowo utwórz testową bazę:

```sh
docker compose -f compose.dev.yaml exec db createdb -U volleycrew volleycrew_test
VOLLEYCREW_TEST_DATABASE_URL=postgresql+asyncpg://volleycrew:volleycrew_dev@127.0.0.1:55432/volleycrew_test npm run test:backend
```

Testy integracyjne wymagają nazwy bazy zakończonej `_test`, wykonują migrację, usuwają testowe dane tożsamości i sprawdzają aktualność schematu. Korzystaj wyłącznie z dedykowanej testowej bazy. Nigdy nie podawaj produkcyjnego connection stringa.

Testy przeglądarkowe z działającą lokalną bazą (domyślnie na porcie 55432):

```sh
npm --prefix volleycrew/frontend exec -- playwright install chromium webkit
VOLLEYCREW_E2E_DATABASE_URL=postgresql+asyncpg://volleycrew:volleycrew_dev@127.0.0.1:55432/volleycrew_test npm run test:e2e
```

Playwright uruchamia osobne API na 8202 i Vite na 5175, bez ponownego używania serwerów developerskich. Wymaga jawnego `VOLLEYCREW_E2E_DATABASE_URL` zakończonego `_test`. Seeder kasuje dane tożsamości i kalendarza WYŁĄCZNIE tej bazy i tworzy fikcyjnego administratora, zaproszenie, domyślną regułę, odwołany termin i pełne listy testowe do sprawdzenia rezerwy oraz osobne trwające spotkania do obecności i pełnych drużyn. Nie uruchamiaj testów backendu i E2E równocześnie na tej samej bazie. Testy przechodzą rejestrację, pamiętanie sesji, maskowane logowanie, edycję profilu, reset, blokadę, nawigację i kalendarz desktop/mobile oraz przebieg rezerwy, podgląd harmonogramu, ponowne potwierdzenia, zachowanie wyjątków i konflikt starej karty organizatora, zatwierdzenie obecności, podział 7:7 z zamianą w rotacji, ponowienie po utracie odpowiedzi, publikację boiska oraz prywatną historię i korektę, a także podgląd PDF, pobranie listy dla 14 osób, ponowne pobranie dla 13 po korekcie i odtworzenie po błędzie sieci, a także zapis/retry wyniku, ranking, historię punktów, pełną korektę historyczną i zamknięcie 0:0. E9 dodaje kontrolę axe-core, celów dotykowych i szerokości, utraty sieci/sesji, zachowania niezapisanych pól oraz mobilnej geometrii klawiatury. Projekty `desktop` i `mobile` używają Chromium, `webkit` silnika WebKit; nie zastępuje to testów fizycznego Androida/iOS. Scenariusze rejestracji mają izolowane liczniki ograniczeń w testowej bazie, bez zmiany limitów aplikacji. Wyniki i screenshoty: `volleycrew/frontend/test-results/` (ignorowane w git). `PLAYWRIGHT_BROWSERS_PATH` może wskazywać własną lokalizację przeglądarek; używaj tego samego ustawienia przy instalacji i testach.

## Kontrakt API i formatowanie

Po zmianie endpointów lub DTO:

```sh
npm run api:generate
npm run api:check
```

Eksporter importuje aplikację bez uruchamiania bazy. Źródłem kontraktu jest FastAPI; commit obejmuje `frontend/openapi.json` i wygenerowane `src/lib/api/schema.d.ts`. Frontend używa klienta openapi-fetch i tych typów. Wygenerowanych plików nie edytuj ręcznie.

`npm run format` formatuje kod Python i frontend. Node używany jest do budowania, docelowy runtime będzie serwował statyczny `frontend/dist` przez Nginx. `npm --prefix volleycrew/frontend run preview` pokazuje sam build statyczny; produkcyjne proxy API i pakiet HA dostarcza E10.

## CI i Home Assistant

`.github/workflows/checks.yml` definiuje instalację z lockfile, lint, typy, kontrakt API, testy backendu z PostgreSQL 17, testy frontendu, build i E2E Chromium/WebKit. Nie publikuje obrazu ani nie wdraża aplikacji. Workflow trzeba rzeczywiście uruchomić po wypchnięciu kodu; lokalne testy nie oznaczają zielonego CI.

E10 dostarcza instalowalny manifest HA, Dockerfile/s6/Nginx, Ingress, migracje przy starcie kontenera i lokalne sprawdzenie obu architektur. Końcowy odbiór wymaga samodzielnej instalacji na HA, sprawdzenia fizycznych telefonów i kopii poza hostem. Nie przechowuj sekretów w repozytorium; produkcja wymaga osobnej PostgreSQL i właściwej konfiguracji HTTPS/proxy.

## Prototyp wizualny

Prototyp pozostaje osobną referencją z fikcyjnymi danymi. Nie realizuje pełnych reguł produkcyjnych; źródłem ustaleń są dokumenty planu. Wariant A został zaakceptowany, B/C zachowano do porównań.

```sh
npm run prototype
```

- http://localhost:4173/prototype/?variant=A
- http://localhost:4173/prototype/phone.html — interaktywny podgląd w ramce telefonu

W prototypie zmiany znikają po odświeżeniu. Nie używaj prawdziwego PIN-u. Przełącznik zawodnik/organizator to demonstracja, nie mechanizm uprawnień.


## Instalacja Home Assistant (E10)

Pakiet jest w `volleycrew/`, manifest repozytorium w `repository.yaml`. Home Assistant buduje aplikację lokalnie z Dockerfile, tak jak maybe-finance; nie potrzebuje gotowego obrazu Volleycrew w GHCR. [Instrukcja instalacji, opcji, tokenu administratora i backup/restore](volleycrew/DOCS.md). Użytkownik sam publikuje/dodaje repozytorium i instaluje aplikację; kod znajdujący się tylko lokalnie nie jest dostępny w sklepie HA.

Lokalny build produkcyjny na ARM64:

```sh
docker build --platform linux/arm64 --build-arg BUILD_ARCH=aarch64 -t volleycrew:e10-arm64 volleycrew
```

Dla `amd64` wybierz `--platform linux/amd64 --build-arg BUILD_ARCH=amd64`. Domyślna baza Dockerfile jest multiarch; `build.yaml` zawiera przypięte bazy per architektura dla zgodności z instalacją HA. Nowe HA oznacza `build.yaml` jako przestarzały, ale nadal go odczytuje; Dockerfile działa również bez przekazania `BUILD_FROM`.

Test produkcyjnego obrazu (wymaga Dockera, `openssl`, Node i przeglądarek Playwright; tworzy/usuwa wyłącznie własne testowe kontenery, sieć i wolumeny):

```sh
python3 scripts/test_container.py --image volleycrew:e10-arm64 --platform linux/arm64
```

Test rezerwuje lokalne porty 18200, 18099, 18443 i 18543 oraz osobną sieć testową. Sprawdza start od pustego PostgreSQL 17, błędną konfigurację/DB/migrację, HTTPS, dwa prefiksy Ingress, cookies/CSRF, restart, kopię przed zmianą wersji, pełny cykl spotkania, PDF w Chromium/WebKit i restore na drugim serwerze. `--backend-tests` dodaje całą regresję backendu na odrębnej bazie PostgreSQL 17 w tym środowisku; wymaga także lokalnego `npm run setup`. Nie uruchamiaj dwóch tych testów jednocześnie. Nie jest to test fizycznego HA/Pi ani kopii poza hostem.

Produkcyjne zależności Python są dodatkowo eksportowane do hashowanego `backend/requirements.lock`, używanego przez Dockerfile:

```sh
uv export --project volleycrew/backend --frozen --no-dev --format requirements-txt --no-header --no-annotate --output-file volleycrew/backend/requirements.lock
```

CI weryfikuje zgodność tego pliku z `uv.lock`, buduje i testuje oba CPU bez publikacji obrazu. Samo dodanie workflow nie oznacza wykonanego zdalnego CI.
