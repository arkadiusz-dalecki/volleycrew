# E2/E9 — poprawki mobilne, logowanie i instalacja

Data: 2026-11-08. Wersja pakietu HA: **0.3.1** (poprawkowa po 0.3.0). Zakres: cztery uwagi ze zrzutów i przełącznik widoku administratora, bez wdrożenia na HA.

## Spełnione kryteria

- Formularz pojedynczego spotkania: usunięto domyślną ramkę fieldset, ograniczono szerokości kontrolek i skorygowano natywne pola daty/godziny Safari; jedna kolumna na telefonie.
- Usunięto wskazany podpis pod nagłówkiem najbliższego spotkania.
- Logowanie: natywny select z „Wybierz użytkownika” na nowym urządzeniu. Maskowanie nazwisk i przydomki zachowane. Zapamiętane ID pochodzi z udanego uwierzytelnienia lub aktywnej sesji; zniknięcie profilu przywraca pustą opcję. PIN nie trafia do pamięci trwałej.
- Przełącznik „Administrator / Użytkownik” widoczny także na telefonie. Podgląd pozostaje na własnym koncie, pokazuje zwykłe drużyny/wynik i ukrywa zarządzanie kalendarzem, salą, ofertami oraz ustawienia. Administracyjne trasy są osłonięte także w podglądzie. Powrót do administratora jest zawsze dostępny. Wybór jest zapamiętany dla konta w obrębie sesji przeglądarki.
- Przycisk „Dodaj aplikację do telefonu” na ekranach dostępu i w stopce po zalogowaniu. Używa `beforeinstallprompt`, gdy dostępny; pozostałym użytkownikom pokazuje instrukcję platformy w dostępnym dialogu. Ukrywa się po `appinstalled` i w trybie standalone. Manifest ma PNG 192/512 oraz lokalną ikonę Apple 180. Instalacja nie dodaje cache danych ani zapisów offline.

## Weryfikacja

Środowisko lokalne macOS arm64; izolowana baza `volleycrew_test` na 127.0.0.1:55432. Node 26.8.1, Playwright 1.65.0, Chromium desktop/mobile i mobilny WebKit.

- `npm --prefix volleycrew/frontend run lint`: zaliczone bez ostrzeżeń.
- `npm --prefix volleycrew/frontend run build`: zaliczone (TypeScript i Vite).
- `npm --prefix volleycrew/frontend run test`: 1 test zaliczony.
- `git diff --check`: zaliczone.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm --prefix volleycrew/frontend run test:e2e`: pełny przebieg kontrolny — 49 zaliczonych, 4 niepowodzenia i 1 celowo pominięty (klawiatura mobilna na desktopie). Trzy niepowodzenia wynikały ze starego selektora radio w teście wygaśnięcia sesji; czwarte wykryło brak powrotu fokusu po instrukcji instalacji w Safari. Selektor dostosowano do select; przycisk instalacji jawnie otrzymuje fokus przed otwarciem dialogu.
- Po poprawkach `npm --prefix volleycrew/frontend run test:e2e -- mobile-improvements.spec.ts ui.spec.ts`: **26 zaliczonych, 1 celowo pominięty**, bez błędów we wszystkich trzech projektach. Łącznie wszystkie 53 aktywne scenariusze mają pozytywny wynik w pełnym przebiegu lub końcowym powtórzeniu; nie wykonywano kolejnego pełnego przebiegu.
- Obejrzano zrzuty formularza Chromium/WebKit, logowania i instrukcji instalacji. Formularz sprawdzono geometrycznie w 360/390/430 px; kontrola dostępności i szerokości pozostałych tras także w 768/1440 px. Zrzuty: `volleycrew/frontend/test-results/mobile-improvements-*/{calendar-fixed,install-help}.png` (generowane, poza repozytorium).
- Nowe testy E2E: pusty/ostatni/usunięty profil, nieudane logowanie bez zapamiętania, przełączanie widoków i osłona tras, geometria formularza 360/390/430, prompt instalacji i ukrycie przycisku oraz instrukcje platform i fokus dialogu.
- Pierwsze uruchomienie testu podglądu miało niepoprawną nazwę przycisku w selektorze; poprawiono selektor na istniejące „Dodaj spotkanie” i uruchomiono pełny zestaw od początku.

## Zależności i odbiór

Brak nowych zależności npm, migracji i otwartych decyzji dla tego zakresu. Faktyczne dodanie ikony i uruchomienie z niej na iPhonie/Androidzie wymaga odbioru na urządzeniach pod docelowym HTTPS; emulacja nie zastępuje fizycznej próby. iOS nie udostępnia stronie automatycznej instalacji: użytkownik musi wybrać Udostępnij → Do ekranu początkowego. Zachowanie wynika z [instrukcji Apple](https://support.apple.com/guide/iphone/open-as-web-app-iphea86e5236/27/ios/27); dostępność promptu opisuje [MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeinstallprompt_event).

Następny krok: odbiór wyglądu i instalacji przez użytkownika; pozostałe kryteria E9/E10/E11 nadal według indeksu planu. Nie przeprowadzano publikacji ani instalacji na HA.
