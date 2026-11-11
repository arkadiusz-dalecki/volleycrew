# E3/E9 — nawigacja gestem między spotkaniami

Zlecone i zaimplementowane 2026-11-11. Gałąź `feat/meeting-swipe-navigation`.

Na głównym ekranie i w szczegółach gest w lewo przechodzi do następnego spotkania, w prawo do poprzedniego. Przyciski „Poprzednie” / „Następne” zapewniają tę samą akcję dla myszy, klawiatury i czytnika ekranu. Gest wymaga pojedynczego palca, ruchu co najmniej 60 px, przewagi osi poziomej i czasu poniżej sekundy. Pionowe przewijanie, kontrolki/formularze, dialogi, anulowanie i gesty wielopalcowe nie uruchamiają przejścia.

Nowy odczyt `/api/v1/meetings/adjacent` zwraca najbliższych sąsiadów według aktualnego startu i ID, bez ograniczenia miesiąca/roku. Uwzględnia trwałą historię, odwołania, przesunięcia, znaczniki usunięcia i wyliczane niezakończone terminy aktywnych serii. Nie tworzy spotkań; przejście do wirtualnego terminu korzysta z dotychczasowego `resolve`, bez deklaracji udziału. Kontrakt OpenAPI i klient TypeScript wygenerowane razem. Bez nowych migracji. Na zlecenie użytkownika wersja pakietu podniesiona z 0.3.2 do 0.3.3; aktualizacja standardowa po kopii zapasowej.

## Weryfikacja lokalna

- PostgreSQL 17: osobna tymczasowa instancja na porcie 55439, wyłącznie `volleycrew_swipe_test`. `pytest volleycrew/backend/tests/test_meetings.py -q`: 9 zaliczonych. Nowe przypadki: obie strony, brak sąsiada, granica roku, DST (167 h między wtorkami), wieloletnia przerwa, koniec serii, jednakowy start i kolejność ID, odwołanie/usunięcie/przesunięcie, odczyt bez utrwalania, autoryzacja i walidacja strefy czasu.
- `npm run test:e2e -- e2e/meeting-navigation.spec.ts e2e/calendar.spec.ts e2e/ui.spec.ts`: 20 zaliczonych, 1 celowo pominięty (klawiatura mobilna na desktopie). Chromium desktop/mobile i WebKit: nawigacja, gesty ignorowane, brak mutacji deklaracji, odświeżenie adresu, błąd odczytu i ponowienie, geometria, kontrast i cele dotykowe. Kontrola szerokości 360/390/430/768/1440 px w istniejącej macierzy UI.
- Końcowe powtórzenie `meeting-navigation.spec.ts`: 3 zaliczone, w tym natywne zdarzenia dotykowe Chromium przez CDP na projekcie mobile; pozostałe przypadki używają zdarzeń TouchEvent w przeglądarce.
- `npm run lint`, `npm run typecheck`, `npm run api:check`, `npm run test:frontend` (4 testy), `npm run build`, `git diff --check`: zaliczone.
- Screenshoty Playwright w ignorowanym `volleycrew/frontend/test-results/`; widok mobilny sprawdzony wizualnie.

## Pozostałe zależności

Stan przed publikacją PR: lokalne kontrole zaliczone; wyniki zdalnego CI będą dostępne w PR. Nie wykonano instalacji Home Assistant ani odbioru gestów na fizycznym iPhonie/Androidzie. Nie uruchamiano testów obrazów HA (zmiana API/UI bez infrastruktury). Kolejny odbiór: gesty na fizycznych telefonach, szczególnie przy krawędziach ekranu, gdzie przeglądarka/system może obsługiwać własną nawigację.
