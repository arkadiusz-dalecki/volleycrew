# E9 — integracja wariantu A i odporność interfejsu

Data: 2026-11-07. Stan: lokalna implementacja i weryfikacja; pełny odbiór E9 pozostaje otwarty do prób na fizycznych telefonach i akceptacji porównania wizualnego. Bez commita, publikacji ani wdrożenia HA.

## Zmiany

- Zachowany wariant A: jasne tło, zielony nagłówek, karty, cztery zakładki na telefonie i boczna nawigacja na desktopie. Poprawiony kontrast opisów, nawigacji, boiska i odwołanego spotkania. Wspólne tokeny tekstu, powierzchni, fokusu i bezpiecznego dolnego odstępu; lokalne fonty DM Sans/Manrope z polskimi znakami.
- Mobilny nagłówek ma więcej miejsca na tekst. Kalendarz przy 360 px mieści cele dotykowe 44 px. Kontrolki wyboru mają prawidłową wysokość także w WebKit, przy zachowaniu natywnego selektora opcji.
- Wspólny natywny `ConfirmDialog` dla rezygnacji, przekazania oferty, blokady profilu i zmiany/odwołania terminu. Nazwany dialog, nieaktywne tło, Escape/anulowanie, powrót fokusu, przewijanie w niskim widoku. Otwarcie przyciskiem ustawia fokus również w WebKit; po usunięciu przycisku fokus wraca do głównej treści. Anulowanie podglądu zmiany terminu zachowuje formularz.
- Boisko zachowuje pełne nazwiska i rotację. Nazwa dostępna przycisku jest wyprowadzana z zawartości wraz z przydomkiem; dekoracyjne inicjały i strzałki nie są czytane. Przejścia między trasami ustawiają tytuł dokumentu i fokus treści; zagnieżdżona historia punktów zachowuje aktywną zakładkę rankingu.
- Chwilowy błąd sprawdzenia sesji zachowuje otwarty ekran i dane formularzy zamiast demontować aplikację. Panel obecności, edytor wyniku, historia z korektami i harmonogram zachowują formularze przy nieudanym odświeżeniu już pobranych danych, z komunikatem o nieaktualnym odczycie.
- Brak sieci ma jawny komunikat; nieudany zapis zachowuje pola i wymaga ręcznego ponowienia. Sieciowy `TypeError` ma komunikat po polsku. Błąd odświeżenia sesji ma przycisk ponowienia. Potwierdzone wygaśnięcie sesji usuwa prywatne dane; ponowne logowanie wraca do żądanej wewnętrznej trasy. Po wylogowaniu z profilu ponowne logowanie również wraca do profilu; wejście bez zapamiętanej trasy prowadzi do spotkania.
- Dolna nawigacja korzysta z safe area. `visualViewport` i aktywne pole sterują jej ukryciem przy wykryciu klawiatury; pola mają 16 px na telefonie i odstęp przewijania. Test geometrii nie zastępuje próby z klawiaturą systemową.
- Manifest i lokalna ikona SVG do instalacji strony, bez service workera, kolejki offline ani cache prywatnych odpowiedzi. Licencja ikony dołączona. Zachowanie instalacji i ikony na konkretnym iOS pozostaje do sprawdzenia. Prototyp, przełącznik wariantów i dane demonstracyjne nie są częścią `dist/`.

## Odbiór

| Kryterium | Wynik / dowód |
| --- | --- |
| Integracja wszystkich etapów | Rzeczywiste API/PostgreSQL: rejestracja, sesje, kalendarz, deklaracje/rezerwa, zmiana terminu, obecność, drużyny, PDF, wyniki i korekty ELO |
| Rozmiary i brak przewijania poziomego | Główne ekrany 360/390/430/768/1440 px; boisko, ranking i PDF dodatkowo w pełnej ścieżce sali. Pomiar szerokości dokumentu, geometrii kontrolek i screenshoty |
| Dostępność | axe-core: główne trasy, logowanie/rejestracja/reset, dialog, boisko, PDF i podgląd wyniku. Kontrola klawiatury/fokusu, celów 44 × 44 px i krótkiego widoku dialogu. Wynik automatu dotyczy sprawdzonych stanów; nie jest certyfikacją WCAG ani testem czytnika ekranu |
| Sieć / sesja | Offline podczas zapisu profilu: pola pozostają, po powrocie sieci brak samoczynnego zapisu. Błąd odświeżenia sesji i wyniku zachowuje szkic. Rzeczywiste 401 po usunięciu cookie → logowanie → powrót do profilu. Utrata odpowiedzi po zapisie składów/wyniku sprawdzana z rzeczywistym API |
| Porównanie z A | Przygotowane poniżej; akceptacja użytkownika **oczekuje** |
| Fizyczny Chrome Android i Safari iOS | **Niewykonane**. Brak dostępnego w tej sesji środowiska prób na fizycznych telefonach. Emulacja poniżej nie zamyka tego kryterium |
| HA / Ingress / backup | E10; bez deklaracji gotowości produkcyjnej |

## Środowisko i odtwarzanie

macOS arm64; Python 3.13.18; PostgreSQL 14.24 na porcie 55432, wyłącznie jednorazowa baza `volleycrew_test`. Bez produkcji i maybe-finance. Playwright: Chromium **158.0.8127.18**, desktop oraz profil Pixel 7; WebKit **27.2**, profil iPhone 13. Profile emulacji nie oznaczają fizycznych urządzeń ani testu Safari z konkretną wersją iOS.

Playwright ma trzy projekty: `desktop`, `mobile`, `webkit`. CI instaluje Chromium i WebKit; uruchomienie zdalnego CI nadal nie zostało wykonane. Seeder zapewnia osobne mecze dla projektów, a zmiany harmonogramu mają rozłączne lata. Scenariusze rejestracji resetują wyłącznie `auth_throttles` w bazie z końcówką `_test`, aby wspólny adres IP proxy nie łączył niezależnych prób. Limity produkcyjne nie zostały poluzowane; ich zachowanie pozostaje objęte testami backendu.

- `npm run lint` — Ruff/format Python, ESLint i Prettier: poprawnie.
- `npm run typecheck`, `npm run api:check`, `npm run build` — poprawnie. Build zawiera manifest/ikonę i lokalne fonty, bez `prototype/`.
- `npm run test:frontend` — **1 test Vitest zaliczony**.
- `VOLLEYCREW_TEST_DATABASE_URL=<jednorazowa baza *_test> npm run test:backend -- -x --tb=short` — **107 zaliczonych**, 36,58 s. Jedno wcześniejsze ostrzeżenie zależności Starlette/TestClient.
- `VOLLEYCREW_E2E_DATABASE_URL=<jednorazowa baza *_test> npm --prefix volleycrew/frontend run test:e2e -- --reporter=line` — **32 zaliczone, 1 celowo pominięty**, 2,4 min. Pominięty jest wyłącznie mobilny scenariusz geometrii klawiatury w projekcie desktopowym; ten sam scenariusz przechodzi w obu projektach mobilnych. Brak niezaliczonych testów w końcowym przebiegu.
- `e2e-reset-limits` z URL developerskiej bazy bez końcówki `_test` — oczekiwana odmowa przed połączeniem i zmianą danych (exit 1). Ochrona nowej operacji testowej sprawdzona.

Testy backendu i E2E wykonywano kolejno, bez równoczesnego korzystania z tej samej bazy. Logi bieżącej sesji: ignorowane `.runtime/e9/{e2e-final,backend,build}.log`. Nie uruchamiano zdalnego CI ani obrazu HA. Żadne otwarte rozstrzygnięcie produktu nie było potrzebne do zmian E9.

## Porównanie do przeglądu

Zachowano paletę, typografię, układ nawigacji i boisko z wariantu A. Różnice wynikają z rzeczywistych funkcji: osobny szkic i zatwierdzenie obecności, rotacja siódmej osoby, pełne korekty, prywatność priorytetów, stany błędów i rzeczywiste dane rankingu. Prototyp nie służy jako definicja reguł backendu. Obrazy pochodzą wyłącznie z fikcyjnych danych.

| Widok | Prototyp A | Działająca aplikacja |
| --- | --- | --- |
| Telefon, 390 px | [Referencja](assets/e9/reference-phone.png) | [Spotkanie](assets/e9/app-phone.png) |
| Boisko, 390 px | [Referencja](assets/e9/reference-court.png) | [14 osób z rotacją i długim nazwiskiem](assets/e9/app-court-phone.png) |
| Desktop, 1440 px | `prototype/index.html?variant=A` | [Spotkanie](assets/e9/app-desktop.png) |

Zrzuty aplikacji: Chromium/Pixel 7 i desktop. Liczba osób, terminy, przydomki i punkty są fikcyjnymi danymi testowymi, innymi niż w prototypie. Pełne screenshoty mobilne obejmują także treść poniżej pierwszego ekranu; dolna nawigacja jest utrwalona w pozycji bieżącego widoku. Pozostałe zrzuty (360/430 px, kalendarz, ranking, PDF, WebKit) są odtwarzane przez E2E w ignorowanym `volleycrew/frontend/test-results/`.

**Akceptacja tego porównania przez użytkownika: oczekuje.**

## Próba na telefonie — do uzupełnienia

| Urządzenie / system / wersja przeglądarki | Wynik |
| --- | --- |
| Android + Chrome (wpisać model i wersje) | Oczekuje |
| iPhone + Safari (wpisać model i wersję iOS/Safari) | Oczekuje |

Na obu urządzeniach przejść: zaproszenie → rejestracja → zapisy i rezerwa → ponowne wejście z sesją; jako organizator obecność → podział/zmiana na boisku z długim nazwiskiem → PDF → wynik i ranking. Otworzyć PIN/przydomek/wynik przy klawiaturze ekranowej, przewinąć do akcji, sprawdzić dolną nawigację i safe area w pionie/poziomie. Sprawdzić niski dialog, anulowanie, utratę sieci, powrót do aplikacji, wygaśnięcie sesji, pobranie PDF oraz dodanie do ekranu głównego. Zapisać wersje i zauważone problemy, bez PIN-ów, linków zaproszeń i prywatnych historii w raporcie.

Następny zakres implementacyjny: **E10 — pakiet Home Assistant**, obrazy, Ingress, migracje/start, Pi 4 aarch64 i backup/restore. Otwarte punkty odbioru E9 pozostają jawne przy przekazaniu do E10.
