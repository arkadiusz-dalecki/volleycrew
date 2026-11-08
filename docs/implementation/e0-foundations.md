> Aktualizacja 2026-11-08: użytkownik zlecił własny PostgreSQL w pakiecie. Od 0.2.0 nowe instalacje nie wymagają osobnego serwera. Wcześniejsze ustalenia poniżej są historyczne; aktualne zachowanie opisują architecture.md i bundled-postgresql.md.

# E0 — ustalenia fundamentów

Data: 2026-11-06. Stan: część techniczna przygotowana do E1; D2 zatwierdzone, D3 zatwierdzone wraz z prywatnością statusu; D4 zatwierdzone (każda zmiana wymaga potwierdzenia, zachowuje kolejność i rezerwacje, obejmuje oferty); D5 zatwierdzone (korekty, usprawiedliwienia, późne przyjście, dopisanie bez deklaracji); D6 zatwierdzone (blokada, zwolnienie przyszłych miejsc, zachowanie historii, przydomek i maskowana lista logowania). Nie wykonano instalacji, połączenia z HA ani produkcyjną bazą. Wyniki poniżej to ustalenia projektowe i weryfikacja dokumentacji, nie testy kontenera.

## Ustalenia użytkownika

| Obszar | Potwierdzone |
| --- | --- |
| Host | Raspberry Pi 4, Home Assistant 64-bit, `aarch64` |
| Dostęp spoza domu | Cloudflare Tunnel; użytkownik skonfiguruje jak w maybe-finance. Konfiguracja tunelu poza aktualnym zakresem |
| Baza | Osobny serwer PostgreSQL, a nie serwer używany przez maybe-finance |
| Wydanie pierwsze | Pełny cykl opisany w indeksie planu, wraz z listą PDF, wynikami i ELO |
| Backup | Obecnie brak. Docelowo codziennie i przed aktualizacją, z kopią poza hostem |
| Wdrożenia | Uruchamiane ręcznie |

Nie ustalono jeszcze lokalizacji osobnego serwera PostgreSQL, jego wersji, adresu, pojemności ani miejsca docelowego backupów. Nie prosić o hasła w rozmowie. Domena i konkretna konfiguracja Cloudflare nie są warunkiem rozpoczęcia E1.

## Wybory techniczne na start E1

- Frontend: zaakceptowany UI A, React 19, TypeScript, Vite, React Router, TanStack Query. Dokładny zestaw stabilnych wersji przypiąć w lockfile E1, bez canary.
- Node.js 24 LTS do budowania i CI; brak Node w runtime aplikacji. Wersji 20 z referencyjnego Dockerfile nie przenosimy.
- Python 3.13 z aktualnym patchem bezpieczeństwa, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, asyncpg. Python 3.13 odpowiada kandydatowi runtime Debian 13; zgodność zestawu potwierdzi instalacja i testy E1.
- PostgreSQL 17 jako docelowa gałąź dla nowego serwera i lokalnych testów. Nie zakładać, że serwer już istnieje. Dokładny patch z aktualnej wspieranej gałęzi w chwili instalacji. Inna istniejąca wersja wymaga jawnego sprawdzenia zgodności.
- Obraz runtime: kandydat `hassio-addons` Debian base 9.3.0 / Debian 13 z s6. Wydanie widoczne w oficjalnym repozytorium; ścieżkę obrazu, digest i manifesty obu CPU trzeba sprawdzić w E1 przed przypięciem. Nie deklarujemy jeszcze zweryfikowanego obrazu multiarch.
- Produkcja priorytetowo `aarch64`; `amd64` pozostaje drugim celem build/test. Ograniczyć RAM: statyczny frontend, jeden proces API, brak Redis/Celery. Budowanie frontendowych assetów nie należy do startu kontenera.
- Slug aplikacji: `volleycrew`; folder aplikacji: `volleycrew/`; nazwa bazy i użytkownika: `volleycrew`. Oddzielne hasło i uprawnienia tylko do własnej bazy, bez superusera.
- Proponowane porty: Nginx bezpośredni `8200/tcp` z mapowaniem hosta konfigurowalnym w HA; Ingress `8099` wyłącznie wewnętrzny, bez mapowania; Uvicorn `127.0.0.1:8000`. Port 8199 należy do referencyjnego maybe-finance. Dostępności hostowego 8200 jeszcze nie sprawdzono; przed instalacją dopuszczalna zmiana mapowania.

Te wybory są bazą implementacyjną, nie twierdzeniem o najnowszych wersjach wszystkich bibliotek. Dokładne wersje i dowody zgodności przechodzą do lockfile oraz raportu E1.

## Dostęp i konfiguracja

Docelowa droga: telefon → domena HTTPS w Cloudflare → skonfigurowany przez użytkownika Tunnel → listener Nginx Volleycrew → statyczny frontend lub `/api/v1` → FastAPI → osobny PostgreSQL.

Cloudflare nie zastępuje logowania aplikacji. Użytkownicy nie potrzebują kont Home Assistant. Nagłówki od proxy mogą wpływać na rozpoznawanie HTTPS tylko przy połączeniu od wskazanego zaufanego peera. Adres/CIDR tunelu trzeba podać przy wdrożeniu; nie wpisywać na ślepo wszystkich sieci prywatnych. Usuwanie/maskowanie tokenów zaproszenia i resetu w logach oraz polityka Referrer mają ograniczać wycieki z URL.

Ingress jest dodatkową ścieżką. Dokumentacja HA zaleca zaufane tożsamości HA i brak drugiego logowania; nasz plan zakłada oddzielne profile Volleycrew. Dlatego nie włączać automatycznego mapowania konta HA na Arkadiusza. Przed zakończeniem E10 sprawdzić cookies i dodatkowe logowanie pod prefiksem Ingress; gdy nie da się uzyskać poprawnego działania, przedstawić użytkownikowi wariant otwierania samodzielnej aplikacji z panelu HA. Działający publiczny dostęp przez Tunnel jest główną ścieżką zawodnika.

Ustawienia do zaimplementowania w E1/E10: `DATABASE_URL` lokalnie; opcje HA `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; `PUBLIC_URL`, `TRUSTED_PROXY_CIDRS`, `SESSION_SECRET`. Sekrety poza repozytorium. Frontend i API mają wspólny origin. Ustawienia, które nie są jeszcze znane, mają jawne wymagania walidacyjne zamiast zgadywanych produkcyjnych wartości.

## Sesje i ochrona PIN — zatwierdzone w E2

Sześciocyfrowy PIN i samodzielna rejestracja z zaproszenia pozostają wymaganiami produktu. Bazą techniczną jest Argon2id, losowa sesja z hashem tokenu w bazie i cookie HttpOnly/Secure. Parametry Argon2 dobrać pomiarem na Raspberry Pi; ograniczyć liczbę jednoczesnych kosztownych prób.

Zatwierdzone przez użytkownika 2026-11-06: 30 dni bezczynności sesji, twarde wygaśnięcie po 180 dniach; reset PIN-u ważny 30 minut, jednorazowy. Po 5 błędnych próbach na profil w 15 minut kolejne próby są czasowo odrzucane do końca okna. Bez trwałej blokady konta. Techniczna ochrona źródła: 30 nieudanych PIN-ów/15 minut. Liczniki w DB działają po restarcie; implementacja i dowody w raporcie E2.

## Backup i odtworzenie

Polityka częstotliwości zatwierdzona; realizacja jeszcze nie istnieje. Przed E10 ustalić cel kopii poza hostem, retencję, harmonogram, właściciela i sygnalizację nieudanego backupu. Proponowana retencja do uzgodnienia: 14 dziennych kopii. Codzienny backup oznacza możliwość utraty zmian od ostatniej udanej kopii; czas odtwarzania do uzgodnienia, nie jest obecnie SLA.

Przed aktualizacją wykonać spójny `pg_dump` narzędziem zgodnym z serwerem oraz kopię potrzebnej konfiguracji/sekretów, następnie przekazać kopię poza host. Dane zaszyfrować w miejscu przechowania i ograniczyć dostęp. Kopia katalogu plików działającej PostgreSQL nie zastępuje logicznego backupu.

Odtworzenie: nowa pusta baza → odtworzenie dumpa i potrzebnej konfiguracji → uruchomienie zgodnego obrazu → kontrola użytkowników, terminów, historii i ELO → ewentualne unieważnienie sesji. Test wykonać na osobnym środowisku. Backup samej aplikacji HA nie obejmuje automatycznie osobnego serwera DB.

## Otwarte zależności i gotowość

- E1: można przygotować szkielet z lokalną testową PostgreSQL, po zleceniu tego etapu. W E1 wykonać resolver zależności oraz próbny build runtime na obu CPU; brak takiej próby nie jest dowodem zgodności.
- E2: blokada i jej wpływ na przyszłe miejsca zatwierdzone; przydomek rozróżniający identyczne nazwiska zatwierdzony, samodzielna edycja przydomka w profilu zatwierdzona; katalog logowania zatwierdzony: lista imion i maskowanych nazwisk, wybór profilu, sześciocyfrowy PIN. Parametry sesji i limitów zatwierdzone w E2.
- E4: D2 i D3 zatwierdzone. Rezerwa obejmuje ręczne propozycje bez timeoutu, wycofanie po odmowie/pominięciu, nowy czas ponownego zgłoszenia i osobne rezerwacje dla wielu wolnych miejsc; reguły w domain-api.md.
- E5: D4 zatwierdzone — każda zmiana wymaga potwierdzenia nowego terminu, także przy propozycjach z rezerwy; pierwotna kolejność i rezerwacje zachowane. Miejsca czekają bez timeoutu, zwalnia je ręcznie administrator.
- E6: D5 zatwierdzone — korekty/usprawiedliwienia z powodem i audytem, spóźniony jako obecny bez osobnej kary, dopisanie istniejącego niezablokowanego profilu przy wolnym niezarezerwowanym miejscu i limicie 14.
- E7: D7 zatwierdzone — PDF z faktycznie obecnych po kontroli, możliwość ponownego generowania po poprawkach.
- E8: K=32 zatwierdzone wraz z przykładami 5:0 (+16/−16), 3:2 (+3,2/−3,2) i 3:3 (0/0) dla równych drużyn. Zatwierdzone również: dokładne wartości i prezentacja do 1 miejsca, 0:0 bez ELO z zachowaniem obecności, korekty wyników z powodem i przeliczeniem późniejszych meczów. Parametry oczekiwań, historyczne korekty składów i porządek spotkań o tej samej dacie pozostają w D8.
- E10: lokalizacja/wersja DB, cel backupu, zaufane proxy i wolny port pozostają szczegółami wdrożeniowymi. D10 zatwierdzone: jak w maybe-finance, lokalne budowanie przez Supervisor z repozytorium aplikacji i ręczna aktualizacja po zmianie wersji manifestu. Własny gotowy obraz w GHCR nie jest wymagany. Budowanie zachodzi podczas instalacji/aktualizacji, nie podczas każdego startu. Na Pi 4 sprawdzić RAM i czas budowania.

## Źródła sprawdzone 2026-11-06

- [HA: konfiguracja](https://contributors.home-assistant.io/apps/reference/configuration/) i [Ingress](https://contributors.home-assistant.io/apps/guides/ingress/): oddzielne wejście bezpośrednie, ochrona listenera Ingress, prefiks ścieżek.
- [Debian base — oficjalne wydania](https://github.com/hassio-addons/app-debian-base/releases): kandydat 9.3.0, Debian 13; wydanie nie jest dowodem pobrania manifestu obrazu.
- [Node — wersje](https://nodejs.org/en/about/previous-releases): gałąź 24 LTS, 20 EOL.
- [Vite — wymagania](https://vite.dev/guide/): Node co najmniej 20.19 / 22.12; wybrano wspieraną gałąź 24, dokładną zgodność sprawdzi E1.
- [React — wersje](https://react.dev/versions): gałąź 19.
- [Python — wsparcie](https://devguide.python.org/versions/): Python 3.13 w okresie poprawek bezpieczeństwa do 2029-10.
- [FastAPI — przypinanie wersji](https://fastapi.tiangolo.com/deployment/versions/) i [PostgreSQL — polityka wersji](https://www.postgresql.org/support/versioning/): przypinanie przetestowanych wydań i zgodność backupu/aktualizacji.

Aktualizacja wymagań 2026-11-06: statusy założyciel > zawodnik > gość, domyślnie gość. Statusy prywatne, niezależne od uprawnień administratora. Przydomek do rozróżniania profili zatwierdzony; szkolny PDF bez przydomka.


## Weryfikacja kandydata w E10 — 2026-11-07

[Raport E10](e10-report.md) potwierdza dostępność i digesty Debian base 9.3.0 dla obu CPU, lokalny build ARM64/amd64 oraz testy z PostgreSQL 17. Baza jest używana przez Dockerfile; od 0.1.1 jest przypięta bezpośrednio, bez build.yaml. Samodzielna instalacja użytkownika, właściwy serwer produkcyjny, docelowe proxy i magazyn kopii nadal nie są dowodem wdrożenia na Pi.
