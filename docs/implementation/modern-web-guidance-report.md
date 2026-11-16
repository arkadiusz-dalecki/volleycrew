# E9 — pakiet poprawek Modern Web Guidance

2026-11-15–16. Gałąź `fix/modern-web-guidance`, baza `origin/main` (`4560ef8`). Zakres: sześć poprawek zatwierdzonych po lokalnym przeglądzie. Wariant A, backend, kontrakt i reguły miejsc pozostają zgodne ze specyfikacją. Na uzupełniające polecenie użytkownika wersja pakietu została podniesiona z 0.3.5 do 0.3.6; brak nowych migracji i zależności. Changelog wydania obejmuje też wcześniejsze, już scalone poprawki haseł i zaproszeń Messenger. Aktualizacja z 0.3.5 jest zwykłą aktualizacją HA po kopii; starsze wersje nadal wymagają procedury migracji logowania z opisu 0.3.5.

## Zachowanie i akceptacja

| Problem z przeglądu | Zmiana | Dowód lokalny |
| --- | --- | --- |
| Strona przewija się pod dialogiem | `overscroll-behavior: contain` na modalu i backdrop, backdrop jest kontenerem przewijania. Bez zmiany overflow/position html/body. | Koło myszy nad tłem w Chromium zachowuje pozycję strony; Escape/fokus i przewijanie niskiego dialogu sprawdzane osobno w Chromium/WebKit. |
| Błąd powtórzenia hasła nie identyfikuje pola | Wspólny `PasswordField` ma zgodność z pierwszym polem przez Constraint Validation API, opis błędu i aria-invalid po próbie wysyłki. Dotyczy rejestracji/bootstrapu, resetu, profilu i Google. | Różne hasła blokują wysyłkę i ustawiają fokus w powtórzeniu. Poprawienie usuwa komunikat; dotychczasowe testy Unicode/długości i spacji nadal działają. |
| Skok stopki podczas pobierania danych | Obszar trasy rezerwuje pierwszy viewport; statyczne szkielety zamiast krótkiego tekstu. | Test wstrzymuje odpowiedź API spotkania/rankingu, sprawdza stopkę przed/po odpowiedzi. Dodatkowy pomiar produkcyjny poniżej. |
| Tekst nie reaguje na większy rozmiar domyślny | Rozmiary fontów, także skróty `font`, przeliczone na rem; breakpointy tekstowe na em/rem. Meta text-scale bez nadpisania rozmiaru korzenia. Nagłówek może rosnąć, sidebar przewijać się, a kontrolki zawijać treść. | Pięć ekranów przy preferencji 200% i szerokościach 320/390/768/1440 px. Nagłówki rosną dwukrotnie, brak poziomego przewijania; wizualna kontrola screenshotów. |
| Wszystkie widoki w początkowym JS | Oddzielna prywatna powłoka i lazy routes, także finalizacja Google. Granice Suspense/error mają komunikat, ponowne wczytanie i zachowanie nawigacji przy błędzie podstrony. | Przerwane pobranie modułu administratora pokazuje błąd; przejście do rankingu nadal działa. Zmierzono pliki rzeczywiście pobierane na loginie, a nie tylko wielkość jednego chunka. |
| Brak podglądu hasła | Natywny przycisk type=button, aria-pressed i niezmienna nazwa z kontekstem pola. Przełącza tylko typ kontrolki, zachowując wartość, spacje i autocomplete. Jawne powiązania etykiet przez for/id; wskazówka nad nowym hasłem. | Test włącza/wyłącza podgląd, sprawdza wartość, semantykę oraz brak wysłania formularza. |

Komunikat zgodności pojawia się dopiero przy próbie wysłania, aby nie przesuwać przycisku w trakcie kliknięcia po opuszczeniu pola. Podczas wpisywania usuwamy widoczny błąd; natywna walidacja nadal blokuje nieprawidłowe dane. Sprawdzanie backendowe pozostaje niezależne.

## Pomiar builda produkcyjnego

Lokalny Chromium 158.0.8127.18, viewport 390×844, localhost, Vite preview, prawdziwe API i osobna baza testowa PostgreSQL 17. To próby laboratoryjne, bez symulacji słabego telefonu i bez statystyk rzeczywistych użytkowników. Zdarzenia layout-shift pomijają `hadRecentInput`; pomiar obejmuje początkowe ładowanie i krótki okres po nim.

| Miara | Przed | Po |
| --- | --- | --- |
| Łączny JS początkowego logowania | 460 056 B | 329 394 B (3 pliki; około 28% mniej) |
| Gzip początkowego JS | około 135 kB | około 105 kB łącznie |
| CLS spotkania/rankingu, 3 powtórzenia na trasę | około 0,15–0,17 | poniżej 0,003 w każdym z 6 pomiarów |

PDF.js i worker pozostają ładowane przy podglądzie PDF. Nie dodano service workera, kolejkowania zapisów offline, cache prywatnego API ani zewnętrznych fontów/skryptów.

## Wykonane sprawdzenia

- Pełne Playwright E2E: **104 zaliczone, 1 celowo pominięty** (symulacja klawiatury mobilnej w projekcie desktop). Polecenie: `VOLLEYCREW_E2E_DATABASE_URL=<izolowana_baza_test> node node_modules/playwright/cli.js test` z katalogu frontendu. Projekty desktop/mobile używają Chromium, projekt webkit emuluje iPhone. W tym **18 nowych przypadków** MWG (6 scenariuszy × 3 projekty). Scenariusze starej sesji, utraty sieci, miejsc, kalendarza, obecności, drużyn, PDF, wyników i korekt również przeszły.
- Google E2E: **12 zaliczonych**, `node node_modules/playwright/cli.js test --config=playwright.google.config.ts`, z tą samą jawną bazą testową, sekwencyjnie po zwykłym E2E. Lokalny dostawca testowy, bez prawdziwego konta Google. Po dodaniu przycisku widoczności hasła doprecyzowano trzy selektory do dokładnej etykiety pola; zachowano wszystkie asercje i przepływy.
- Vitest: **15 zaliczonych**, `npm --prefix volleycrew/frontend run test`; długości Unicode, spacje, autocomplete oraz dotychczasowe testy auth/Google/tokenów.
- Konfiguracja HA: **12 zaliczonych**, `VOLLEYCREW_ENV_FILE=/dev/null .venv/bin/python -m pytest tests/test_deployment.py -q` z katalogu backendu. Ta grupa nie korzysta z bazy i nie resetuje danych.
- `npm --prefix volleycrew/frontend run lint`, `npm --prefix volleycrew/frontend run typecheck`, `npm run api:check`, `npm run build` oraz `git diff --check`: **zaliczone**. Manifest/changelog odczytane i porównane: **0.3.6**.
- UI/axe/cele dotykowe: pełna grupa `ui.spec.ts` w trzech projektach. Preferencja tekstu 200% jest dodatkowo sprawdzana na pięciu ekranach w `modern-web.spec.ts`. Osobna próba builda produkcyjnego z rzeczywistym ustawieniem Chromium `--blink-settings=defaultFontSize=32` również nie wykazała poziomego przewijania na pięciu trasach przy 320/390/768/1440 px. Wizualnie sprawdzono logowanie i profil przy większym tekście.
- Środowisko bazy: lokalna PostgreSQL **17.11**, własny tymczasowy klaster na loopback i osobna baza `volleycrew_mwg_test`. Nie używano developmentu ani produkcji. Zwykłe i Google E2E uruchamiano kolejno. Tymczasowe API/preview/klaster zatrzymano po zakończeniu.
- Pomocnicze dowody lokalne: `/tmp/volleycrew-mwg-audit/performance-fixed.json`, wcześniejsze `cls-repeat.json` i `performance-login.json`, screenshoty logowania/profilu oraz kopia wyników pełnego E2E w `/tmp/volleycrew-mwg-audit/full-e2e-results`. Wyniki ostatnich Google E2E są w ignorowanym `volleycrew/frontend/test-results/`. To pliki lokalne, nie trwałe artefakty wydania.

## Granice odbioru

- Safari nie egzekwuje jeszcze containment na nieprzewijalnym backdrop/krótkim modalu. Zgodnie z MWG jest to progressive enhancement; pozostają natywne odizolowanie strony/fokusu i containment tam, gdzie treść modalu się przewija. Nie maskujemy tej granicy przez globalne blokady scrolla.
- Meta text-scale jest ignorowane w niewspierających przeglądarkach. Zwykły zoom pozostaje dostępny. Próba 200% symuluje preferencję bazowego tekstu CSS; fizyczne ustawienia OS wymagają osobnego odbioru.
- Menedżery haseł i rzeczywista klawiatura ekranowa, VoiceOver/TalkBack, Android/iOS oraz docelowy Home Assistant wymagają fizycznych prób E9/E11.
- Lokalnie nie wykonywano obrazów HA (Docker niedostępny) ani wdrożenia. Na kolejne zlecenie użytkownika paczka jest publikowana jako PR; wyniki zdalnego CI aplikacji oraz obu obrazów HA należy sprawdzać dla aktualnego HEAD w tym PR. Utworzenie PR nie jest instalacją ani zgodą na scalanie.

## Modern Web Guidance

Zastosowane poradniki: `prevent-page-scroll-under-modal-dialog`, `forms`, `typography`, `respect-os-text-scale`, `performance`. Przyjęto wymagane stopniowe ulepszanie funkcji z ograniczonym wsparciem. Istotne reguły: backdrop wymaga kontenera przewijania; nie blokować overflow html/body; nie nadpisywać rozmiaru fontu korzenia; nowe/aktualne hasło zachowuje autocomplete; dynamiczne importy oddzielają niepotrzebne początkowo widoki. Ogólne zalecenia dotyczące pracy offline nie zastępują decyzji o niekolejkowaniu deklaracji i ochronie prywatnego API.
