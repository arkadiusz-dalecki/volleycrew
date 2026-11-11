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

## Synchronizacja testu po pierwszym CI

Ślad pierwszego CI wykazał, że URL zmieniał się przed zakończeniem renderowania nowego spotkania. Gdy poprzedni ekran również miał aktywny przycisk „Poprzednie”, test wysyłał gest powrotu do starego komponentu, zanim pobrano nowych sąsiadów. Dodano identyfikator wyświetlanego spotkania na kontenerze i oczekiwanie na ten konkretny ekran przed kolejnym gestem. Zachowano asercje dokładnych adresów oraz brak zmian deklaracji.

## Opóźnione 401 po wylogowaniu

Drugi przebieg CI ujawnił istniejący wyścig: odpowiedź administracyjnego odczytu 401 dotarła po wylogowaniu i montażu listy profili, a globalny handler usunął nowy publiczny query z cache. Lista pozostawała w stanie ładowania mimo odpowiedzi 200. Dodany kontrolowany test `auth-races.spec.ts` odtworzył błąd lokalnie (1 niezaliczony przed poprawką). Handler ignoruje teraz zdarzenie, jeżeli nie ma zalogowanej sesji; czyszczenie prywatnych danych aktywnej sesji pozostaje bez zmian.

Po poprawce: `auth-races.spec.ts`, `mobile-improvements.spec.ts` i `meeting-navigation.spec.ts` — 21 zaliczonych w Chromium desktop/mobile i WebKit. Lint, typy, build i diff-check ponownie zaliczone.


## Płynny kafelek — uzupełnienie 2026-11-11

Gałąź `feat/meeting-card-animation`, kontynuacja E3/E9 na zlecenie użytkownika. Cała karta spotkania (data, status, udział i osobisty kalendarz) podąża za palcem. Gest rozpoczyna się na karcie poza kontrolkami; pozostałe sekcje nie uruchamiają nawigacji. Krótki/anulowany gest wraca łagodnie do zera; brak sąsiada ogranicza przesunięcie i daje odczucie oporu. Pełny gest i przyciski uruchamiają wyjazd w kierunku nawigacji (220 ms), a nowy kafelek wjeżdża z przeciwnej strony (300 ms). Pionowe przewijanie i dotychczasowe zabezpieczenia gestów pozostają.

Szczegóły trwałego terminu pobieramy przed wyjazdem, także gdy są już w cache. Wirtualny termin nadal korzysta z resolve. Błąd zachowuje obecną kartę i cofa przesunięcie. Przy przejściu dane są w cache, więc nie ma pośredniego ekranu ładowania. `prefers-reduced-motion: reduce` wyłącza przesuwanie i animacje. Bez zmian API i migracji. Na zlecenie użytkownika wersja pakietu podniesiona z 0.3.3 do 0.3.4; standardowa aktualizacja HA po kopii zapasowej.

Weryfikacja lokalna:

- Osobna PostgreSQL 17 na 55439, baza `volleycrew_swipe_test`; testy nie korzystały z bazy developerskiej ani produkcyjnej.
- `npm run test:e2e -- e2e/meeting-navigation.spec.ts e2e/calendar.spec.ts`: 6 zaliczonych (Chromium desktop/mobile i WebKit). Kontrola pozycji kafelka podczas ruchu i po krótkim geście, natywny dotyk Chromium, oba kierunki, przyciski, przewijanie/gesty ignorowane, błędy szczegółów i sąsiadów, ponowienie, tryb ograniczonego ruchu, zachowanie deklaracji i brak poziomego przepełnienia.
- Lint, typecheck, build, 4 istniejące testy frontendowe i `git diff --check`: zaliczone.
- Screenshot mobilny w trakcie gestu sprawdzony wizualnie; pliki w ignorowanym `volleycrew/frontend/test-results/`.

Publikacja PR i pełne CI zlecone w kolejnym kroku; wyniki dla końcowego commita będą dostępne w PR. Nie wykonywano wdrożenia Home Assistant. Odczucie animacji i gestów na fizycznym iPhonie/Androidzie pozostaje do odbioru. Nie zmieniano backendu ani infrastruktury; nie uruchamiano ich pełnych zestawów testów.
