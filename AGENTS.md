# Volleycrew — instrukcje dla Codexa

## Projekt i źródła ustaleń

Volleycrew organizuje grę jednej prywatnej grupy siatkarskiej: profile i logowanie PIN-em, kalendarz i serie spotkań, deklaracje udziału, rezerwa/oferty miejsc, faktyczna obecność, drużyny, lista podpisów PDF, wyniki i ranking ELO. Administrator zarządza ekipą i spotkaniami; zawodnik deklaruje udział i ogląda dostępne mu dane. Deklaracja udziału, sprawdzona obecność i zatwierdzony skład to osobne stany.

Przed implementacją, zmianą modelu danych lub planowaniem zadania:

1. Przeczytaj [plan budowy](docs/implementation/README.md), wybierz etap lub uzupełnienie z [backlogu](docs/implementation/tasks.md) i załaduj wskazane specyfikacje.
2. Sprawdź [rejestr decyzji](docs/implementation/decisions.md). Zależną regułę wdrażaj po zapisaniu rozstrzygnięcia użytkownika. Polecenia użytkownika mają pierwszeństwo przed wcześniejszymi ustaleniami.
3. Dla backendu i API przeczytaj [reguły domeny](docs/implementation/domain-api.md), dla UI [specyfikację interfejsu](docs/implementation/frontend.md), dla zmian infrastruktury [architekturę](docs/implementation/architecture.md).

Wybrany projekt UI to **wariant A** w `prototype/`. Prototyp jest referencją wizualną i interakcyjną; jego fikcyjne dane i uproszczone reguły nie są specyfikacją backendu. Postęp i aktualny zakres są w indeksie planu. Raport z etapu wskazuje spełnione kryteria odbioru, rzeczywiście wykonane testy i pozostałe zależności.

## Kod i środowiska

- `volleycrew/frontend/`: React, TypeScript, Vite; interfejs polski, wygodny na telefonie. OpenAPI backendu jest źródłem wygenerowanych typów klienta.
- `volleycrew/backend/`: FastAPI, SQLAlchemy, Alembic i PostgreSQL. Endpointy korzystają z serwisów domenowych; zmiany schematu wymagają migracji.
- `volleycrew/rootfs/`, `volleycrew/Dockerfile`, `volleycrew/config.yaml`: pakiet Home Assistant z Nginx, API i własnym PostgreSQL; obsługuje też bazę zewnętrzną. Instalacja i aktualizacja: [DOCS.md](volleycrew/DOCS.md).
- `scripts/`: uruchamianie developmentu oraz testy rzeczywistych obrazów, Ingress i backup/restore. Komendy i wymagane wersje sprawdzaj w [README](README.md), `package.json` i plikach konfiguracji.

Docelowe wdrożenie to aplikacja Home Assistant na amd64 i aarch64. Przegląd kodu, push i zielone CI nie oznaczają wdrożenia ani odbioru na fizycznym telefonie lub HA.

Development i testy korzystają z oddzielnych baz. Testy backendu i E2E resetują dane: kieruj je wyłącznie na izolowaną bazę testową, nigdy developerską ani produkcyjną. Gdy oba zestawy używają tej samej bazy, uruchamiaj je kolejno. Dane demo zasiewaj wyłącznie w jawnie sprawdzonym środowisku developerskim. Sekrety, PIN-y, tokeny, `.env` i dane produkcyjne pozostają poza repozytorium i logami.

Zachowuj transakcyjne reguły miejsc, prywatność statusów i historii, kontrolę wersji oraz idempotencję. Przy zmianie DTO aktualizuj backend, kontrakt i frontend razem przez `npm run api:generate`; sprawdzaj `npm run api:check`.

## Git, GitHub i PR

Pracuj przez `git` i GitHub CLI `gh` w repozytorium wskazanym przez `git remote -v`. Na początku sprawdź gałąź, stan drzewa, istniejący PR i różnicę względem aktualnej gałęzi bazowej. Zachowuj zastane zmiany użytkownika.

Gdy użytkownik zleca PR:

1. Przygotuj kompletną zmianę na gałęzi roboczej, uruchom odpowiednie [kontrole lokalne](docs/implementation/verification.md) i sprawdź `git diff --check`. Dostosuj testy do skutków zmiany; same mocki nie zastępują PostgreSQL ani testu obrazu HA.
2. Jeśli zlecono lekkie podbicie wersji, zwiększ patch w `volleycrew/config.yaml` i uzupełnij `volleycrew/CHANGELOG.md`. Aktualną wersję odczytaj z pliku. Opisz migracje i wymagania aktualizacji.
3. Zapisz commit, wypchnij gałąź i utwórz albo uaktualnij PR do właściwej bazy. Tytuł i opis PR pisz po angielsku. Opis przedstawia finalny problem, zachowanie po zmianie, dowody testów i istotne ryzyka. Wieloliniowy opis przekazuj przez plik i `--body-file`.
4. **Po utworzeniu PR oraz po każdym kolejnym pushu poczekaj na zakończenie kontroli GitHub Actions dla aktualnego commitu.** Sprawdź wszystkie kontrole PR, w tym aplikację i oba warianty pakietu HA; zielony backend lub lokalny build nie wystarcza.
5. Gdy kontrola zawiedzie, odczytaj logi, ustal przyczynę, popraw kod albo test i wykonaj adekwatną regresję. Commit i push kieruj do tej samej gałęzi/PR, następnie ponownie czekaj na CI. **Powtarzaj do zielonego wyniku.** Ponowne uruchomienie bez zmiany ma sens tylko przy rozpoznanym błędzie przejściowym infrastruktury; nie wyłączaj kontroli ani nie osłabiaj asercji, aby ukryć błąd.
6. Przed zakończeniem porównaj HEAD PR z wypchniętym commitem i upewnij się, że wyniki dotyczą właśnie jego. `queued`, `pending`, `in_progress` i anulowany przebieg nie są zaliczeniem; celowe pominięcia muszą mieć uzasadnienie. Przy rzeczywistej przeszkodzie zewnętrznej podaj konkretny blokujący warunek i link do przebiegu, bez deklarowania gotowości.
7. Podaj użytkownikowi link do PR, wersję (jeśli zmieniona), wynik CI i pozostałe ograniczenia. Utworzenie PR nie upoważnia do merge ani wdrożenia; wykonuj je dopiero na zlecenie użytkownika.

Przydatne komendy (wstaw numer PR i ID przebiegu odczytane z GitHuba):

```sh
gh pr view <PR> --json url,headRefName,headRefOid,statusCheckRollup
gh pr checks <PR> --watch --interval 30
gh run view <RUN_ID> --log-failed
gh pr create --base main --head <BRANCH> --title '<TITLE>' --body-file /tmp/pr-body.md
gh pr edit <PR> --body-file /tmp/pr-body.md
```

Źródłem aktualnej macierzy CI jest [.github/workflows/checks.yml](.github/workflows/checks.yml). Obrazy ARM64 i testy odtworzenia mogą trwać kilkanaście minut: kontynuuj monitorowanie i informuj krótko o istotnych zmianach stanu. Po poprawce sprawdzaj najnowsze przebiegi, a nie wcześniejsze zielone wyniki lub błędy starego commitu.

## Testy zależne od czasu

Strefa kalendarza to Europe/Warsaw. Testuj granice rozpoczęcia, zmianę daty i DST z kontrolowanym zegarem. `/meetings/next` może poprawnie zwrócić trwające spotkanie; fixture zapisów musi wybrać termin przyszły. W testach pakietu służy do tego `signup_occurrence` w `scripts/test_container.py`. Regresja testu nie uzasadnia zmiany prawidłowej reguły produkcyjnej.
