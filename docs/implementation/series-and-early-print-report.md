# E3/E5/E7/E9 — usuwanie, istniejące serie i wcześniejsza lista podpisów

Data: 2026-11-08. Zakres zlecony przez użytkownika: usuwanie wydarzeń z widoku, edycja/usuwanie istniejących serii, wydruk listy przed wyjściem z domu. Implementacja lokalna, bez zmian produkcyjnej bazy i bez instalacji HA.

## Kryteria i zmiany

- „Usuń spotkanie” na kafelkach i w szczegółach, także odwołanych. Przed usunięciem dialog ze skutkami. Usunięty termin znika z kalendarza, najbliższego spotkania, bezpośredniego wejścia i mutacji; nie odradza się z tygodniowej reguły ani po jej zmianie. Rezerwacje i oferty zamykają się bez nowych wpisów nieobecności. Migracja `0009_deleted_meetings` dodaje znacznik usunięcia, zachowując historię i powiązania.
- Stała lista istniejących serii w kalendarzu, również domyślnej wtorkowej. „Edytuj serię” ładuje parametry, pokazuje podgląd skutków i zmienia przyszłą część tej reguły. Zachowane ID i kolejność; zmienione terminy wymagają nowego potwierdzenia. Skrócenie zakresu usuwa wypadające terminy. Indywidualne wyjątki w zakresie pozostają, konflikty dat/godzin są odrzucane.
- „Usuń serię” usuwa wszystkie jej przyszłe terminy, także nieutrwalone i indywidualnie przesunięte, pozostawiając przeszłą/rozegraną historię, inne reguły i niezależne dodatkowe spotkania. W usuniętym zakresie nie przywracamy domyślnej reguły.
- Podgląd i zapis serii chroni globalna wersja i token zawierający wersje dotkniętych spotkań. Zmiany są atomowe, ze wspólnym porządkiem blokad. Zwykły zawodnik nie ma uprawnień do tych operacji.
- D7 zmienione zgodnie z nowym poleceniem: „Lista podpisów” aktywna przed spotkaniem. PDF zawiera potwierdzone miejsca aktualnego terminu, bez rezerwy/ofert/oczekujących; po zatwierdzeniu obecności przechodzi na faktycznie obecnych. UI podaje źródło, wykrywa zmianę danych i zawsze pobiera aktualny PDF. Szkic obecności nie zmienia listy z zapisów; eksport pozostaje operacją odczytu.

## Weryfikacja

Środowisko macOS arm64, PostgreSQL na 127.0.0.1:55432, wyłącznie izolowana baza `volleycrew_test`.

- `VOLLEYCREW_TEST_DATABASE_URL=…/volleycrew_test npm run test:backend`: **133 zaliczone** w końcowym pełnym uruchomieniu. Pierwsze uruchomienie nowego testu wykazało niepoprawne oczekiwanie zerowej liczby zdarzeń po wcześniejszej rezygnacji; sprawdzamy zachowanie liczby zdarzeń przed/po usunięciu serii, a istniejący wpis rezygnacji pozostaje.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm --prefix volleycrew/frontend run test:e2e`: pełny przebieg — **59 zaliczonych, 3 niepowodzenia starego selektora kalendarza, 1 celowo pominięty**. Stary test zakładał jeden przycisk na odwołanym kafelku; po dodaniu „Usuń spotkanie” wskazuje jawnie przycisk otwarcia. Nowy test edycji doprecyzowano do selektora formularza zamiast zbyt ścisłej etykiety select.
- Po korektach i wymuszeniu świeżego odczytu obecności w podglądzie PDF: `npm --prefix volleycrew/frontend run test:e2e -- calendar.spec.ts series-management.spec.ts`: **9 zaliczonych**. Łącznie wszystkie **62 aktywne scenariusze** mają wynik pozytywny z pełnego przebiegu lub końcowego powtórzenia; brak kolejnego pełnego przebiegu po zmianie selektora. Chromium desktop/mobile i WebKit; szerokości 360/390/430/768/1440, kontrola dostępności i celów dotykowych zaliczona w pełnym przebiegu.
- `npm run lint`, `npm --prefix volleycrew/frontend run build`, `npm --prefix volleycrew/frontend run test` (1 test), `npm run api:check`, `git diff --check`: zaliczone. Build obejmuje TypeScript.
- Testy API: usunięcie i niedopuszczenie ponownego resolve, ukrycie z odczytów, zamknięcie ofert, brak nowych zdarzeń obecności, prywatność, przyszła część serii, wyjątki, utrzymanie historii i niezależnych spotkań, skracanie zakresu, zmiana reguły po pojedynczym usunięciu, równoczesne zmiany administratorów, konflikty i nieaktualne podglądy.
- PDF: wczesny wydruk, brak skutków ubocznych, szkic/aktualizacja obecności, wykluczenie rezerwy/ofert/ponownych potwierdzeń, aktualne korekty, kontrola uprawnień i zablokowany eksport usuniętego/odwołanego terminu.
- Przejrzano render przykładowego wydruku: 14 polskich nazwisk, jedna strona A4, tabela i pola na podpis bez obcięć. Przykład QA w `output/pdf/early-signatures-qa.pdf`, poza repozytorium; generator i fonty pozostają lokalne.
- Testy przeglądarkowe obejmują usunięcie odwołanego spotkania i trwałość po odświeżeniu, edycję wybranej serii oraz jej usunięcie, podgląd i pobranie PDF przed spotkaniem, a także wcześniejsze scenariusze sali/harmonogramu.

## Pozostałe zależności

Dev jest dostępny pod `http://localhost:5173` z lokalną migracją 0009 i API 8201. Produkcyjna aktualizacja wymaga kopii przed migracją oraz osobnego sprawdzenia CI/obu obrazów i odbioru na telefonie/HA. Nie uruchamiano zmian na produkcji. Nowe zależności npm/Python nie są potrzebne. Brak otwartej decyzji blokującej ten zakres. Następny krok: odbiór w devie, potem przygotowanie wydania/PR zgodnie ze zleceniem użytkownika.
