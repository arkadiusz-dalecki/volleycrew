# E8 — wyniki, ELO i pełne korekty

Data: 2026-11-07. Stan: zaimplementowany i sprawdzony lokalnie. Bez commita, publikacji ani wdrożenia Home Assistant.

D8 domknięte przez użytkownika w tej rozmowie: skala oczekiwań 400 przy K=32; pełna korekta historycznej obecności i składów z obowiązkowymi powodami oraz zachowaniem wersji; przeliczanie według startu i stałego ID spotkania. Wcześniej zatwierdzone: baza 1000, proporcja setów, jedna delta na drużynę, brak zaokrąglania do prezentacji po każdym meczu, 0:0 i korekty wyniku z przeliczeniem późniejszych spotkań. Decyzje są w `decisions.md`; kontrakt i polityka precyzji w `domain-api.md`.

## Odbiór E8

| Kryterium | Realizacja i dowód |
| --- | --- |
| Wzór i skala | elo-sets-v1, K=32, skala 400, średnie drużyn i proporcja setów. Testy 5:0 → ±16, 3:2 i 6:4 → ±3,2, remis równych → 0; remis słabszych daje wzrost, niewystarczająco wysoka wygrana silniejszych może obniżyć punkty |
| Bez zaokrąglania prezentacyjnego w stanie | Decimal, 50 cyfr znaczących; Numeric bez narzuconej skali; JSON dziesiętny jako string. UI zaokrągla dopiero do 1 miejsca. Odtworzenie tego samego replay daje dokładnie te same wartości zapisane |
| Wynik z zatwierdzonych składów | Serwer sprawdza stan, rewizję obecności, kompletność i liczebność składów. Sety nieujemne integer; bool/ułamki/ujemne są odrzucane. Podgląd i osobne zatwierdzenie w kroku 03 |
| 0:0 | Zakończenie bez setów, obecność/składy zachowane, bez RatingEntry i bez zwiększania liczby spotkań rankingowych. Wynik pozostaje w historii. Korekta do/z 0:0 przelicza pozostałe mecze |
| Jedna delta na stronę | Wszyscy faktyczni uczestnicy strony otrzymują tę samą deltę, również rotujący. Test 6:7 zachowuje ±16 na osobę bez wymuszania zerowej sumy całej grupy. Nieobecny nie otrzymuje RatingEntry |
| Dobór według rzeczywistych punktów | Generowanie i zapis składów pobierają PlayerRating, z bazą 1000 dla nowego profilu. Test po 5:0: punkty 1016/984 prowadzą do wyrównanych drużyn po 1000, bez używania stałych punktów z E6 |
| Retry i konflikty | Trwały Idempotency-Key z odciskiem operacji, expected_version Meeting i expected_rating_version. Powtórzenie nie tworzy drugiej rewizji ani delty; zmieniony payload pod tym samym kluczem i stary podgląd dają 409. E2E gubi odpowiedź po rzeczywistym zapisie i odzyskuje tę samą rewizję |
| Przeliczanie późniejszej historii | Stały porządek starts_at/ID. Test dopisuje starszy wynik po nowszym, a potem odwraca starszy wynik: późniejsze średnie, delty i punkty przed/po są zaktualizowane. Kolejność wpisywania wyników nie ma znaczenia |
| Pełna korekta historyczna | Nowy ResultRevision i TeamSheet; stare wersje/autor/czas/powód pozostają. Każda dodana/usunięta osoba wymaga jawnej korekty obecności z osobnym powodem. Aktualizuje to Attendance, PDF, faktyczny roster zakończonego spotkania i ranking razem; źródłowe deklaracje nie są przepisywane |
| Prywatność | Ranking, historia punktów i wynik nie ujawniają priorytetu, flag blokady, powodów ani zdarzeń obecności. Gracz nie mutuje ani nie odczytuje administracyjnego wyniku. Administrator widzi historyczne składy i powody; dana osoba własną poprawkę obecności. Punkty/historyczne profile pozostają po blokadzie dostępu |
| Atomowość i współbieżność | Wyłączna blokada RatingState przed Meeting; odczyty punktów i wyników mają współdzieloną blokadę stanu. Testy wyścigu przez HTTP i niezależne sesje PostgreSQL poza blokadą tożsamości: jeden zapis, drugi konflikt starego podglądu. Wstrzyknięta awaria po zapisie punktów wycofuje wynik, punkty i receipt; retry działa |
| Frontend na telefonie | Formularz setów, podgląd oczekiwań/delt, publiczny ranking i historia meczów, historia punktów zawodnika, korekta wyniku/składu/obecności i 0:0. Desktop oraz emulacja 360/390/430 px; brak poziomego overflow |

## Implementacja i granice

Migracja **0007_results** dodaje ResultRevision, RatingState, PlayerRating, RatingCalculation, RatingEntry i ResultMutation. TeamMember.rating_snapshot przechodzi na Numeric. Migracja developerska wykonana; Alembic check nie wykazuje różnic. Downgrade z zapisanymi wynikami jest blokowany, żeby nie kasować historii. Odtworzenie zgodnego backupu pozostaje procedurą E10.

Czysta matematyka: `backend/app/domain/rating.py`; czysty replay: `domain/replay.py`. API i transakcje: `api/results.py`, `api/result_schemas.py`, `services/results.py`. RatingEntry/RatingCalculation/PlayerRating są aktualną materializacją przeliczenia, a nie dodawaniem kolejnej delty do poprzedniej materializacji. Niezmienne wejścia to ResultRevision i snapshot TeamSheet. Dawne wyliczone wartości dziennika są zastępowane przez aktualny replay; poprzednie wyniki i składy pozostają w źródłowych rewizjach. Nie dodano osobnego archiwum wszystkich historycznych przebiegów przeliczania.

Wybrano pełny replay zamiast odwracania starych delt: przy jednej grupie i cotygodniowych spotkaniach upraszcza to poprawność i odtwarzanie po korektach. Wejścia są pobierane grupowo, a materializacja zapisywana partiami. Przy wzroście liczby grup/historii należy zmierzyć koszt i rozważyć checkpointy; nie wykonano benchmarku wieloletnich dziesiątek tysięcy meczów. Operacja nie korzysta z kolejki ani osobnego procesu workera.

50 cyfr to jawna, skończona precyzja obliczeniowa, nie twierdzenie o nieskończonej dokładności potęg/dzielenia. Brak kwantyzacji punktów po każdym spotkaniu. Frontend używa Number wyłącznie do prezentacji; obliczenia rankingu i dobór drużyn są serwerowe.

0:0, podobnie jak inny wynik, wymaga zatwierdzonych składów zgodnie z przyjętym kontraktem. Korekta wyniku nie zmienia historycznej daty startu. Test zmiany kolejności dotyczy dopisania starszego wyniku i ponownego wyliczenia porządku; nie dodawano niezatwierdzonej funkcji przesuwania dat zakończonych meczów.

Frontend: `features/results/{ResultEditor,ResultCard,RankingPage,format}.tsx/ts`; krok 03 zintegrowany z panelem organizatora, publiczna karta w szczegółach zakończonego spotkania. Zmiana wyniku/składu unieważnia podgląd; konflikt zachowuje pola. Operacje po utracie odpowiedzi ponawiają dokładnie ten sam payload i klucz. Prywatne historyczne powody i składy są dostępne wyłącznie z endpointu administratora.

## Weryfikacja

macOS arm64, Python 3.13.18, PostgreSQL 14.24 na 55432; dane testowe wyłącznie w izolowanej `volleycrew_test`. Bez bazy maybe-finance i produkcji.

- `npm run lint` — Ruff, format Python, ESLint i Prettier poprawnie.
- `npm run typecheck`, `npm run api:check`, `npm run build` — poprawnie.
- `VOLLEYCREW_TEST_DATABASE_URL=<baza *_test> npm run test:backend -- -x --tb=short` — **107 zaliczonych**, w tym **16 przypadków E8**: matematyka/0:0/proporcje, deterministyczny replay, zapis/retry, pełna korekta i prywatność, starszy wynik i późniejsze wyliczenia, rollback po awarii, walidacja, dwa zapisy HTTP, bezpośrednia współbieżność DB, zachowanie zablokowanych profili, aktualne punkty w generatorze oraz nierówne drużyny. Jedno wcześniejsze ostrzeżenie zależności Starlette o transporcie TestClient.
- `npm run test:frontend` — **1 test Vitest zaliczony**; pełne ścieżki wyniku/rankingu sprawdzone z prawdziwym API i DB w E2E.
- `VOLLEYCREW_E2E_DATABASE_URL=<baza *_test> npm run test:e2e` — **12 zaliczonych**, regresja E2–E7 i rozszerzona ścieżka sali E8: 13 obecnych → podział/zatwierdzenie → 5:3 → utrata odpowiedzi/retry/reload → ranking i historia meczów → pełna korekta do 14 faktycznie obecnych z prywatnym powodem → historia punktów i własna obecność → korekta 0:0. Wynik pozostaje w trzech rewizjach.
- Alembic `check` — `No new upgrade operations detected` dla developerskiej bazy z migracją 0007; testowa baza przechodzi migracje w testach.

Chromium **158.0.8127.18**: 1440 px oraz emulacja Pixel 7/390 px i kontrola 360/390/430 px. Wizualnie sprawdzono podgląd wyniku i ranking z długimi polskimi nazwiskami. Screenshoty w ignorowanym `volleycrew/frontend/test-results/room-attendance-court-swap-fbfa0--PDF-and-private-correction-{desktop,mobile}/`: `result-preview.png`, `ranking-*.png`, wcześniejsze boisko/PDF. Nie wykonywano próby na fizycznym telefonie ani Safari/iOS.

## Następny etap

**E9 — integracja UI A i próby na telefonie**. Wymaga końcowego przejścia całości, dostępności, zachowania przy sesji/sieci, porównania z wariantem A i prób na rzeczywistych urządzeniach. E10 nadal obejmuje CI/PostgreSQL 17, obrazy amd64/aarch64, Pi 4, pakiet HA/Ingress i faktyczny backup/restore. Nie deklarujemy wydania produkcyjnego ani instalacji w HA.
