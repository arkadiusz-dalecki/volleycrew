# E3/E9 — wybór osobistego kalendarza

Data: 2026-11-08. Zlecenie użytkownika: przycisk dodania terminu z wyborem aplikacji. Implementacja lokalna, bez zapisu do podłączonego kalendarza i bez wdrożenia HA.

## Spełnione kryteria

- „Dodaj do kalendarza” na karcie najbliższego/wybranego spotkania, po głównej deklaracji. Dostępny zarówno zawodnikowi, jak i administratorowi. Odwołane/usunięte/zakończone/minione terminy nie są eksportowane z UI.
- Dostępny dialog z wyborem Google Calendar, Outlook.com, Outlook Microsoft 365, Apple Calendar i innej aplikacji. Google/Outlook otwierają formularz z tytułem, datą początku i końca oraz miejscem. Apple/inne pobierają `.ics`; UI opisuje import i brak automatycznej synchronizacji. Użytkownik sam zatwierdza wydarzenie w aplikacji.
- Dane czasu eksportowane jako bezwzględne UTC, również przy czasie letnim/zimowym. Parametry URL kodowane przez URLSearchParams. ICS ma UID, DTSTAMP, DTSTART, DTEND, SEQUENCE, CRLF, escapowanie tekstu oraz składanie linii do 75 oktetów bez rozcinania UTF-8.
- Brak uczestników, PIN-ów, sesji, linków zaproszenia lub prefiksu Ingress w eksporcie. Brak nowych zależności i migracji dla tej funkcji. Eksport nie zmienia deklaracji ani harmonogramu.

## Weryfikacja

- `npm --prefix volleycrew/frontend run test`: **4 zaliczone**, w tym nowe przypadki zimowego/letniego czasu, UTC, polskich znaków, delimiterów i prób wstrzyknięcia wiersza do ICS.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm --prefix volleycrew/frontend run test:e2e -- calendar-export.spec.ts`: **3 zaliczone**, Chromium desktop/mobile i WebKit. Wybór providerów, parametry linków, rzeczywiste pobranie ICS i jego daty, menu bez overflow, audyt dostępności, powrót fokusu oraz brak przycisku dla odwołanego terminu.
- Lint, TypeScript/build i `git diff --check`: zaliczone. Obejrzano mobilny zrzut `test-results/calendar-export-*/calendar-choice.png` (generowany, poza repozytorium).
- Nie wykonano zapisu na rzeczywistym koncie Google/Microsoft/Apple; to eksport do formularza/importu, a końcowy odbiór w natywnych aplikacjach na urządzeniach pozostaje po stronie użytkownika.

## Referencje i ograniczenia

[Google Developer Forum](https://discuss.google.dev/t/add-event-to-google-calendar-not-from-ical-files-but-from-urls/73879/3) opisuje formularz z parametrami dat w UTC. [Microsoft](https://learn.microsoft.com/en-us/answers/questions/1008125/is-it-possible-to-launch-the-outlook-app-calendar) opisuje deeplink formularza Outlook. Format ICS jest zgodny z [RFC 5545](https://www.rfc-editor.org/info/rfc5545/). Apple opisuje [import ICS na Macu](https://support.apple.com/guide/calendar/import-or-export-calendars-icl1023/mac) i [import z Mail na iPhonie](https://support.apple.com/en-mt/guide/iphone/ipha0d932e96/ios). Nie obiecujemy bezpośredniego zapisu w Apple Calendar przez stronę ani automatycznej aktualizacji już zaimportowanego wydarzenia.

Dev: `http://localhost:5173`. Bez publikacji, instalacji HA i zmian produkcyjnych. Następny krok: odbiór menu i importu na urządzeniach, potem wydanie/PR na zlecenie użytkownika.

## Uzupełnienie: kafelki i wycofanie eksportu zbiorczego (2026-11-09)

„Dodaj do kalendarza” jest również na kafelkach kalendarza, w widoku zawodnika i administratora. Na najnowsze polecenie użytkownika usunięto eksport zbiorczy, jego dialog, pobieranie zakresu i generator wielu VEVENT. Pozostał eksport pojedynczego spotkania, zarówno z listy, jak i ze szczegółów. Weryfikacja po wycofaniu: lint i TypeScript/build zaliczone; 4 testy unit oraz 6 E2E `calendar-export.spec.ts` zaliczone w Chromium desktop/mobile i WebKit. Potwierdzono działanie pojedynczego eksportu i brak przycisku zbiorczego.
