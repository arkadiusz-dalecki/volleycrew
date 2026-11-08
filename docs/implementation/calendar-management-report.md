# Kalendarz administratora — raport E3/E5/E9

Zakres zlecony 2026-11-08; implementacja lokalna, bez publikacji ani instalacji w HA.

## Spełnione kryteria

- Data zastępuje hasło jako główny nagłówek karty; godzina i miejsce pozostają poniżej. Kontrola zrzutów desktop/mobile.
- Boczne menu pobiera rzeczywisty najbliższy termin z API, niezależnie od otwartego spotkania; odświeżanie i obsługa błędów/braku terminu.
- Zarządzanie harmonogramem przeniesione z ustawień do kalendarza i widoczne tylko administratorowi. Formularze pojedynczego spotkania i cotygodniowej serii z podglądem przed zapisem.
- Można wybrać pusty dzień kalendarza i dodać termin. Backend chroni dostęp, wersję, przyszłą datę, DST i kolizje z trwałymi oraz wyliczanymi spotkaniami.
- Seria od–do zastępuje harmonogram w podanym zakresie, przy opcjonalnym końcu. UI traktuje ostatni dzień włącznie; API używa daty wyłącznej. Po końcu wracają wcześniejsze reguły, a późniejsze utrwalone spotkania zachowują ID, daty i zapisy.
- Przesunięcie pojedynczego spotkania pozostaje w szczegółach, dostępnych z kalendarza. Dotychczasowe ponowne potwierdzenia, kolejność, odwołania i wyjątki zachowane. Nowe pojedyncze spotkanie nie przesuwa się przy zmianie serii.
- Migracja 0008 dodaje `Meeting.is_additional`, domyślnie false dla istniejących danych. Nowy dodatkowy termin ma trwały rekord i nieaktywną regułę źródłową; bez nieskończonego generowania rekordów.

## Weryfikacja

Środowisko lokalne macOS arm64, Python 3.13.18, PostgreSQL 14.24 (Homebrew) na 127.0.0.1:55432, wyłącznie baza `volleycrew_test`.

- `VOLLEYCREW_TEST_DATABASE_URL=…/volleycrew_test npm run test:backend`: **122 zaliczone**. Po dodaniu kontroli nocnych kolizji na granicy serii: `python3 scripts/dev.py test tests/test_schedule_changes.py`: **15 zaliczonych**.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm run test:e2e -- schedule.spec.ts calendar.spec.ts`: **9 zaliczonych** — desktop Chromium 1440, mobilny Chromium 390 (kalendarz także 360/430), mobilny WebKit 390. Dodawanie pojedynczego terminu, seria z końcem, powrót wcześniejszej reguły, przesunięcia, ponowne potwierdzenia, konflikt drugiej karty i odwołanie.
- `npm run lint`, `npm run build`, `npm run test:frontend`, `npm run api:check`, `git diff --check`: zaliczone.
- Zrzuty Playwright: `volleycrew/frontend/test-results/schedule-calendar-organize-4bce4-and-a-bounded-weekly-series-{desktop,mobile,webkit}/{calendar-admin,meeting-date}.png`. Pliki generowane, poza repozytorium; przejrzano widoki desktop/mobile.

## Zależności i dalszy odbiór

Brak blokującej decyzji dla zaimplementowanego zakresu. Zachowanie przyjęte dla serii: zastąpienie dotychczasowego harmonogramu w wybranym okresie, z powrotem poprzedniej reguły po końcu. Nie dodano wielu równoległych cotygodniowych serii; dodatkowe pojedyncze terminy są niezależne. Przed aktualizacją HA potrzebna standardowa kopia i migracja; instalację wykonuje użytkownik. Pozostają akceptacja wyglądu i test na fizycznym telefonie zgodnie z E9; nie zastępujemy ich emulacją. Następny krok: odbiór tych zmian przez użytkownika, później E11 według indeksu planu.

## Uzupełnienie — dwa profile podglądu

Na prośbę użytkownika dodano `npm run dev:preview`: idempotentny seed Admin Demo/User Demo w lokalnej bazie `*_dev`, bez usuwania istniejących danych. Ekran logowania i treść aplikacji pokazują dwa przyciski przełączające prawdziwą sesję przez API. Funkcja wymaga Vite DEV oraz jawnego VITE_LOCAL_PREVIEW; build produkcyjny usuwa przyciski i ID kont demo. Sprawdzono w Chromium przejście Admin → User → Admin, właściwe uprawnienia kalendarza, szerokość 390 px bez overflow, typecheck, lint i build. Uruchomiono lokalny podgląd na porcie 5173.

## Uzupełnienie — akcje na kafelku kalendarza

Użytkownik zlecił dwa przyciski bezpośrednio na kafelku: „Zmień termin” oraz „Odwołaj”. Wykorzystano wspólny komponent MeetingActions i istniejące API, bez zmian reguł domenowych. Formularz rozwija się na kafelku; odwołanie oraz zapis nowego terminu wymagają dotychczasowych potwierdzeń. Wyliczany termin utrwalany jest dopiero po wybraniu akcji; nie ma przekierowania do szczegółów. Przy zmianie daty aktualizowany jest filtr/miesiąc, a po zapisie odświeżane są kalendarz i najbliższe spotkanie. Akcje nie są widoczne dla zawodnika, zakończonych i odwołanych spotkań.

Weryfikacja: typecheck, lint, build oraz 12 E2E kalendarza/harmonogramu w desktopowym Chromium, mobilnym Chromium i WebKit. Nowa ścieżka sprawdza zmianę wygenerowanego terminu z aktywnym filtrem daty, pozostanie w kalendarzu, anulowanie i zatwierdzenie odwołania, trwałość po odświeżeniu, ukrycie akcji dla zawodnika i brak overflow. Zrzuty `calendar-card-actions.png` w wynikach Playwright.

### Czternaście profili lokalnych

Na prośbę użytkownika rozszerzono seed lokalnego podglądu o 12 zawodników z imionami i nazwiskami oraz przydomkiem „Podgląd lokalny”. Razem z Admin Demo i User Demo jest 14 profili. Wszystkie nowe konta mają rolę zawodnika i PIN 123456. Deterministyczne ID zapobiegają duplikatom po kolejnym uruchomieniu seeda. Istniejące profile, PIN-y i deklaracje pozostają zachowane. Sprawdzono ponowne uruchomienie seeda i liczbę 14 profili w DB/API.

### Wyrównanie kolumn kalendarza

Dodano nagłówek „Wybierz dzień” nad kartą miesiąca i wyrównano wysokość oraz odstępy obu nagłówków kolumn. Karta miesiąca i pierwszy kafelek spotkania zaczynają się na tej samej wysokości. Przeniesiono pozycjonowanie sticky na całą kolumnę miesiąca, z wyłączeniem na wąskich ekranach. Sprawdzono geometrię w Chromium 1440 px (różnica pozycji górnych krawędzi ≤1 px), wizualny zrzut oraz brak overflow przy 360/390/430 px. Typecheck i lint zaliczone.

### Neutralny przycisk deklaracji

Przed zapisaniem deklaracji przycisk „Będę” ma neutralny wygląd, taki jak „Nie będę”, bez znacznika wyboru. Potwierdzony stan pozostaje w nagłówku karty („Masz miejsce na boisku”) i ikonie po odpowiedzi serwera. Usunięto wizualną sugestię wcześniejszego zaznaczenia; reguły zapisu i potwierdzania nie zmieniły się.

Na kolejną prośbę użytkownika przyciski pierwszej deklaracji otrzymały pastelowe tła: jasnozielone „Będę” i jasnoczerwone „Nie będę”, bez znacznika wyboru. Zmiana wyłącznie wizualna; potwierdzony udział nadal wynika z odpowiedzi API i nagłówka karty.

### Osiem osób na spotkaniu i ikony deklaracji

Na prośbę użytkownika zapisano ośmiu zawodników demo na lokalne spotkanie 24.11.2026 (ID 0361387e-3365-556c-ad62-890b36ecd99e), korzystając z serwisu deklaracji i lokalnej bazy `*_dev`. Spotkanie ma 8 uczestników i 6 wolnych miejsc; wcześniejsze zapisy zachowane. Na kolejną prośbę dodano ✓ przy „Będę” oraz × przy „Nie będę”, z zachowaniem pastelowych kolorów. Typecheck i lint zaliczone; przeglądarka potwierdziła 8 nazwisk oraz obie ikony.

### Odblokowanie zatwierdzenia w teście obecności

Po zmianie czasu lokalnego meczu API zwracało `can_confirm=true`, lecz wszystkie 9 osób miało `draft_state=unknown`; UI poprawnie blokował zatwierdzenie, ale nie wskazywał brakującego kroku. Dodano komunikaty wyjaśniające konieczność oznaczenia osób i zapisania szkicu. Na zlecenie użytkownika przygotowano wyłącznie lokalny szkic testowego spotkania: nieoznaczone osoby ustawiono jako obecne przez serwis save_attendance, zachowując istniejące oznaczenia i bez zatwierdzania obecności. Przeglądarka potwierdziła aktywny przycisk oraz otwarcie podsumowania zatwierdzenia. Typecheck, lint i diff-check zaliczone.

### Boisko dopasowane do liczby graczy

Usunięto stałe sześć komórek i puste kropki. Drużyny 1–6 osób mają własne rozmieszczenie; trzy osoby są ustawione 1 przy siatce + 2 z tyłu, cztery w 2×2, pięć w 2+3. Połowy są lustrzane względem siatki, także w pionowym układzie mobilnym. Siódma osoba nadal trafia do rotacji, a zamiana zawodników i zapis składu działają na tych samych ID. Zmiany obejmują wspólny Court używany przez organizatora i zawodników, bez zmian backendu.

Weryfikacja: typecheck i lint; przeglądarkowa kontrola 1–7 osób na każdej połowie przy 1440/390 px, dokładna liczba graczy bez pustych komórek, geometria 1+2 oraz 2×2 względem siatki, rotacja siódmej osoby i brak poziomego overflow. Warianty wizualne kontrolowane na podmienionej odpowiedzi odczytu, bez zapisu fikcyjnych składów do lokalnej bazy.

Wynik E2E sali: **3/3 zaliczone**. Próby pełnej ścieżki sali: zamiana przy 7:7, zapis i publikacja składów, PDF oraz korekty obecności w Chromium desktop/mobile i WebKit. Audyt desktopu ujawnił przy okazji zbyt jasny tekst daty/godziny w bocznym panelu najbliższego spotkania; przyciemniono go dla kontrastu AA.

### Wyśrodkowanie nierównych liczebnie drużyn

Poprawiono geometrię przy 4:5: zewnętrzne połowy boiska miały wspólną wysokość, ale wewnętrzny układ czterech osób zachowywał własną, mniejszą wysokość i pozostawał przy górnej krawędzi. Połowa jest teraz kontenerem grid rozciągającym formację na całą dostępną wysokość, z równymi rzędami. Kontrola przeglądarkowa 4:5, 5:4, 4:6 i 6:4 na 1440/390 px sprawdza środki obu formacji oraz średnie środki czterech graczy względem połowy (tolerancja 1 px), bez zapisu składów do bazy. Lint i diff-check zaliczone.

## Weryfikacja końcowa PR / wersja 0.3.0

Gałąź `feat/calendar-management-and-court-layouts`, bazująca na `origin/main` po PR #3. Wersja aplikacji HA podniesiona do 0.3.0, changelog uzupełniony po angielsku.

- `npm run lint`, `npm run typecheck`, `npm run api:check`, `npm run test:frontend` (1 test), `npm run build`, `git diff --check`: zaliczone.
- `VOLLEYCREW_TEST_DATABASE_URL=…/volleycrew_test npm run test:backend`: **123 zaliczone**, lokalny PostgreSQL 14.24.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm run test:e2e`: **41 zaliczonych, 1 celowo pominięty** (klawiatura mobilna na desktopie), Chromium desktop/mobile i WebKit.
- Nowy trwały test `e2e/court.spec.ts` sprawdza układy 1–7, kierunek względem siatki, rotację i centrowanie 4:5, 5:4, 4:6, 6:4 w trzech projektach przeglądarek.
- Sprawdzono brak przycisków podglądu, ID kont demo i trasy `/preview/login` w produkcyjnym JavaScript. Konta i testowe operacje na obecności/terminie były wyłącznie lokalne; migracja nie tworzy danych demo ani nie omija reguł czasu.
- Zrzuty do przeglądu: [akcje kalendarza](images/calendar-meeting-actions.png), [boisko przed poprawką](images/court-unequal-before.png), [boisko po poprawce](images/court-unequal-after.png).

CI GitHub ma dodatkowo sprawdzić PostgreSQL 17 oraz produkcyjne obrazy obu CPU; wyniki lokalne nie zastępują tych prób. Fizyczna instalacja HA i odbiór telefonu pozostają po stronie użytkownika.
