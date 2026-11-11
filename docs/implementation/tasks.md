# Etapy budowy i zadania dla agentów

Każdy etap jest osobnym, reviewowalnym przyrostem. Domyślnie realizacja sekwencyjna. Osobne gałęzie pracy są możliwe dopiero po ustaleniu wspólnego kontraktu i wyraźnym zleceniu; sam plan nie uruchamia agentów. Nie rozpoczynać produkcyjnej implementacji tylko dlatego, że dokument istnieje.

## E0 — zamknięcie fundamentów

Wejście: cały indeks planu, `architecture.md`, `decisions.md`, lokalna referencja maybe-finance. Zależności: polecenie rozpoczęcia.

- Potwierdzić D1 i proponowany zakres D9: host HA, CPU, domena/TLS, metoda wystawienia, PostgreSQL, odpowiedzialność za backup.
- Zweryfikować aktualne dokumentacje HA, Python/FastAPI, React/Vite i obrazu bazowego. Zapisać wspierane wersje oraz zgodność `amd64/aarch64`.
- Ustalić porty bez konfliktu z maybe-finance; nazwy bazy, sluga i ustawień.
- Zapisać decyzje: stack z planu lub uzgodniona zmiana; metoda logowania i ograniczeń PIN; model sesji i termin ważności.
- Przejść D2–D6 na przykładach. Gdy odpowiedzi jeszcze nie ma, oznaczyć zależne podzadania; można budować fundamenty bez udawania gotowej polityki.

Odbiór: agent potrafi opisać drogę telefonu z internetu do API oraz sposób odtworzenia DB. Rejestr ma decyzje albo precyzyjnie wskazane otwarte zależności. Samo przeczytanie plików nie kończy E0, jeśli brak ustaleń niezbędnych dla wybranego zakresu.

## E1 — szkielet i środowisko

Zależności: techniczny zakres E0. Czytać: architektura, weryfikacja.

- Utworzyć strukturę produkcyjną obok `prototype/`, konfigurację formatowania/lintowania, lockfile, testową konfigurację i przykładowe ustawienia bez sekretów.
- Uruchomić PostgreSQL developerską; pustą migrację i pierwsze tabele bazowe ustalić z modelem E3.
- Backend: health live/ready, konfiguracja, sesje DB, obsługa błędów i zależność wstrzykiwanego zegara.
- Frontend: router, pusty AppShell A, design tokens, klient API, generowanie typów OpenAPI i podstawowe stany loading/error.
- Zdefiniować komendy: dev, lint, typecheck, test backend, migracje, test frontend/e2e, build. Dodać CI uruchamiające je w izolowanych usługach.

Odbiór: nowy checkout uruchamia się z README bez ręcznego poprawiania kodu; health ready sprawdza DB; frontend dochodzi do API; build produkcyjny przechodzi; CI nie dotyka produkcji.

## E2 — sesje, PIN i zaproszenia

Zależności: E1, D6 dla pełnej polityki profili. Czytać: sekcje dostępu w domenie, frontend, weryfikacja.

- Modele Player, Invite, Session, PinResetGrant i trwałe ograniczenia prób logowania.
- Jednorazowy bootstrap Arkadiusza; losowy, unieważnialny link zaproszenia; nowa rejestracja tylko z aktywnym linkiem i zawsze ze statusem gościa.
- Rejestracja, profil chooser wg D6, logowanie, zapamiętana sesja, wylogowanie, zmiana PIN-u i grant resetu.
- Autoryzacja roli w każdym administracyjnym endpointzie; publiczne DTO profilu; unieważnianie sesji po blokadzie/resetach.
- UI ścieżek wejścia i profilu, komunikaty wygasłego zaproszenia oraz resetu.

Odbiór: po ponownym otwarciu użytkownik ma sesję; nowe urządzenie wymaga PIN-u; gracz nie uzyskuje admina przez zmianę requestu; unieważniony link nie rejestruje nowych osób; ograniczenia prób i reset mają testy integracyjne. D6 pozostawione otwarte oznacza nieukończone odpowiednie operacje, nie ich milczące pominięcie.

## E3 — modele spotkań i kalendarz

Zależności: E1/E2; D6 dla operacji blokowania. Czytać: model i harmonogram w domenie, kalendarz w frontendzie.

- Migracje ScheduleVersion, Meeting i Enrollment z ograniczeniami i indeksami.
- Domyślny wtorkowy harmonogram i strefa, czysta funkcja generowania terminów, scalenie wystąpień z trwałymi rekordami.
- Idempotentne rozwiązanie wystąpienia do Meeting przy mutacji.
- Najbliższe spotkanie, szczegóły i paginowany zakres kalendarza. Publiczna lista graczy bez danych prywatnych.
- Frontend kalendarza i szkielet szczegółów z danymi API, pustym stanem i odwołanym terminem.

Odbiór: przejście do przyszłego miesiąca i zapis terminu nie jest ograniczone do najbliższego tygodnia; dwa żądania tworzą ten sam Meeting; testy DST i nowego dnia tygodnia; historyczny termin ma stabilny identyfikator.

## E4 — deklaracje, priorytety i rezerwa

Zależności: E2/E3; D2 i D3. Czytać: transakcja zapisu i reguły miejsc.

- EnrollmentEvent, SeatOffer i endpointy deklaracji/ofert. Jedna blokada Meeting dla wszystkich zmian alokacji.
- Trzy poziomy pierwszeństwa (założyciel > zawodnik > gość) i kolejność, wypieranie przed granicą, ochrona miejsca po granicy, zwalnianie miejsc.
- Jawne przyjęcie/odmowa/zamknięcie oferty; rezerwacja miejsca według D2. Ręczna komunikacja przez Messenger, bez integracji.
- Karta własnego stanu, uczestnicy i rezerwa. Serwerowe komunikaty o konflikcie, przekroczeniu granicy i wygaśnięciu oferty.
- Przyjęcie późnej oferty zapisuje dane potrzebne do wyjątku rezygnacji.

Odbiór: testy na dwóch równoczesnych sesjach DB dowodzą limitu 14; powtórzenie nie zmienia kolejności; założyciel wypiera tylko zgodnie z regułą czasu; gracz rezerwy wymaga potwierdzenia; cudzej/starej oferty nie można przyjąć. E2E zapisuje dalszy termin i sprawdza rezultat po odświeżeniu.

## E5 — zmiana harmonogramu i odwołanie

Zależności: E3/E4; D4. Czytać: harmonogram i stany spotkań.

- Podgląd zmian od wybranej daty, wersjonowanie harmonogramu, przesunięcie jednego spotkania i odwołanie.
- Zmiana wersji terminu, aktualizacja zapisów/ofert zgodnie z D4, ponowne potwierdzenie.
- UI administratora z podsumowaniem zakresu przed zatwierdzeniem, UI zawodnika ze starym i nowym terminem.
- Weryfikacja uprawnień i konfliktu wersji przy drugiej karcie administratora.

Odbiór: zmiana dnia od daty obejmuje rekordy istniejące i wystąpienia przyszłe; brak duplikatów; stare potwierdzenie nie jest aktualnym; odwołany termin widać w historii i nie tworzy nieobecności.

## E6 — obecność i drużyny

Zależności: E4/E5; D5. Czytać: obecność i drużyny, panel organizatora w frontendzie.

- Attendance i zdarzenia prywatnej historii, szkic oraz zatwierdzenie obecności.
- Klasyfikacja rezygnacji i wyjątek późnej oferty; no-show dopiero przy zatwierdzeniu, zgodnie z D5.
- Dwa generatory składów: losowy i wyrównany. ELO do czasu E8 może wynosić bazowe 1000 w prawdziwych danych, bez fikcyjnych punktów z prototypu.
- Edycja szkicu, weryfikacja członkostwa/obecności/liczebności, zatwierdzenie i kontrolowany powrót do zmian.
- Boisko z pełnymi nazwiskami, rotacją i ręczną zamianą pełnych drużyn; widok zatwierdzonych składów dla graczy.

Odbiór: każda obecna osoba jest dokładnie w jednym składzie; nieobecni nie trafiają do generatora; oba tryby działają dla 11–14 osób, mniejsze liczby mają jawną walidację; edycja 7:7 pozwala zamienić osoby; historia jest prywatna także przez bezpośredni URL/API. Testy ponowionego zatwierdzenia bez duplikatów.

## E7 — lista podpisów

Zależności: E6 i D7.

- Generowanie PDF po zatwierdzeniu faktycznej obecności; data, I LO w Gdańsku, numer, imię/nazwisko, miejsce na podpis.
- Autoryzowany podgląd/pobranie; polskie znaki i dostarczony font, bez wysyłania danych do zewnętrznego generatora.
- Źródłem PDF są wyłącznie faktycznie obecni. Po korekcie obecności ponowne generowanie pobiera aktualne dane; nie dodawać niezatwierdzonego wariantu eksportu z deklaracji.

Odbiór: odczyt i wizualna kontrola wygenerowanego pliku dla 14 osób i długich nazwisk; druk A4 bez obcięć; zmiana obecności zmienia kolejną wygenerowaną listę; zwykły gracz nie pobiera dokumentu administracyjnego.

## E8 — wyniki, ELO i korekty

Zależności: E6, D8.

- Zatwierdzić symulacje wzoru i przykładowe przyrosty; zapisać wersję algorytmu i precyzję.
- Wdrożyć czystą funkcję oceny spotkania, ResultRevision, RatingEntry, transakcyjny zapis i ochronę przed powtórzeniem.
- Zrealizować politykę 0:0 i korekt. Przy replay sprawdzić również korektę składu i przeniesienie kolejności w historii.
- Formularz wyniku z podsumowaniem, ranking, historia spotkań, szczegóły zmian punktów.

Odbiór: spełnione własności matematyczne w `verification.md`; wynik 5:3 nie liczy się drugi raz po retry; nieobecny nie ma RatingEntry; korekta daje ten sam ranking co przeliczenie historii od początku; awaria nie zapisuje połowy meczu.

## E9 — integracja UI A i próby na telefonie

Stan: implementacja i kontrola lokalna wykonane; [raport i porównanie A](e9-report.md). Odbiór fizycznych telefonów i akceptacja porównania wizualnego pozostają otwarte.

Zależności: E2–E8. Czytać: frontend i weryfikacja.

- Sprawdzić wszystkie trasy, odświeżenia, wygasłe sesje, błędy/konflikty i powrót po utracie sieci.
- Ujednolicić tokeny CSS i komponenty; usunąć demo/przełącznik wariantów z builda produkcyjnego.
- Obsłużyć klawiaturę, fokus, cele dotykowe i nazwy graczy na boisku. Dołączyć fonty lokalnie.
- Przejść pełny scenariusz uczestnika i organizatora w rozmiarach 360/390/430 i desktop. Dodać manifest/ikony jeśli mieszczą się w ustalonym zakresie.

Odbiór: zaakceptowane porównanie z wariantem A, brak poziomego overflow i zasłoniętych przycisków, obsługa Chrome Android i Safari iOS sprawdzona z podaniem wersji. Emulacja to etap kontroli, nie dowód testu na fizycznym urządzeniu.

## E10 — pakiet Home Assistant

Zakres użytkownika z 2026-11-07: samodzielne dodanie repozytorium, token i instalacja w HA. Agent przygotowuje pakiet i sprawdza go lokalnie; nie wykonuje instalacji ani zmian w HA/tunelu. [Raport E10](e10-report.md) oddziela weryfikację kontenerów od odbioru na Pi.

Zależności: E0/E1 oraz działająca aplikacja; D1/D10. Eksperyment z pustym kontenerem można wykonać wcześniej jako część E1, bez ogłaszania gotowego wdrożenia.

- Manifest repozytorium i aplikacji, Dockerfile, s6, oba listenery Nginx, opcje konfiguracji, health, migracje i logi.
- Przeprowadzić test produkcyjnego obrazu z testową DB; sprawdzić start po braku DB, błędnej konfiguracji i migracji.
- Sprawdzić Ingress pod dynamicznym prefiksem oraz bezpośrednią domenę HTTPS; sesje i CSRF w obu trybach.
- Zbudować/testować oba CPU; zastosować D10: lokalny build w HA, brak pola `image` z gotowym obrazem Volleycrew, wersjonowanie przez `config.yaml`, ręczna instalacja/aktualizacja. Sprawdzić build na Pi 4 (RAM/czas). Udokumentować dodanie repozytorium, odświeżenie sklepu, backup i aktualizację. CI może testować build bez publikowania obrazu.
- Wykonać backup i odtworzenie na osobnej instancji, opisać rollback schematu i obrazu.

Odbiór: instalacja i aktualizacja w docelowym HA, trwałość danych po restarcie, poprawny dostęp z telefonu poza LAN, bez konta HA dla zawodnika. Wynik sprawdzenia drugiej architektury opisany; nie utożsamiać samej kompilacji z uruchomieniem.

## E10 — własny PostgreSQL 0.2.0

Zlecone 2026-11-08. Zastępuje wymóg osobnego serwera w nowej instalacji. Własna baza z automatycznym hasłem i trwałym /data; zachowanie istniejącego external; migracje, restart/awaria/aktualizacja, backup i restore HA. Odbiór: realny start i bootstrap bez osobnego serwera, dane po restartach, odtworzenie na nowym wolumenie, blokada startu przy braku kopii, kontrole obu CPU. Instalację wykonuje użytkownik.

## E11 — odbiór i pierwsze wydanie

Zależności: wszystkie wymagane etapy, rozstrzygnięte D1–D10 albo jawnie zawężony zakres zatwierdzony przez użytkownika.

- Przejść scenariusz szkolnej sali: 14 zapisów, rezygnacja, oferta, przyjęcie, kontrola obecności, drużyny, podpisy, wynik i ranking.
- Przejść scenariusz zmiany harmonogramu, odwołania i korekty według zatwierdzonych zasad.
- Audyt autoryzacji i sesji, brak sekretów w logach, odtworzenie danych, monitoring dostępności i log błędów.
- Przekazać instrukcję administratora: zaproszenie, PIN reset, harmonogram, rezerwa, obecność, wynik, backup/restore.
- Przed publikacją/instalacją postępować zgodnie z upoważnieniem użytkownika; plan nie jest poleceniem publikacji.

Odbiór: wszystkie kryteria wydania z `verification.md` mają dowód. Użytkownik zatwierdza zakres i zachowanie. Pozostałe prace mają osobne zadania; błędy w limitach, prywatności, trwałości i rankingu blokują wydanie.

## Format zlecenia pojedynczego etapu

```text
Zrealizuj E<n> z docs/implementation/tasks.md.
Zakres: <konkretne podzadania>.
Rozstrzygnięcia: <ID decyzji i zatwierdzony wariant>.
Przeczytaj wskazane specyfikacje; zweryfikuj zależności w kodzie.
Zakończ dopiero po kryteriach odbioru dla tego zakresu.
Raportuj: zmiany, testy i ich wynik, nierozstrzygnięte zależności,
pozostałe ryzyka oraz następne gotowe zadanie. Zaktualizuj postęp.
```

## Uzupełnienie E3/E5/E9 — kalendarz administratora

Zlecone 2026-11-08: widoczna data na karcie, najbliższe spotkanie w bocznym panelu, planowanie w kalendarzu zamiast ustawień, pojedynczy termin i cotygodniowa seria od–do. Odbiór: uprawnienia, brak kolizji, zachowanie zapisów i wyjątków, powrót wcześniejszej reguły po serii, sprawdzenie desktop/mobile/WebKit. [Raport](calendar-management-report.md).

## Uzupełnienie E2/E9 — poprawki mobilne i instalacja

Zlecone 2026-11-08 po zrzutach z iPhone: formularz pojedynczego terminu bez wychodzących pól/ramki, usunięcie podpisu spotkania, rozwijany wybór konta z pamięcią ostatniego logowania, przełącznik widoku administrator/użytkownik, przycisk dodania aplikacji na iOS i Android. Zakres i dowody: [raport](mobile-improvements-report.md).

## Uzupełnienie E3/E5/E9 — usuwanie i istniejące serie

Zlecone 2026-11-08: „Usuń spotkanie” także dla odwołanych terminów, bez ich dalszej prezentacji i odradzania z harmonogramu; widoczna lista istniejących serii z edycją i usuwaniem, również dla dotychczasowej domyślnej reguły wtorkowej. Odbiór: uprawnienia, trwałość usunięcia, zakres serii, zachowana historia rozegranych meczów, zwolnienie ofert/miejsc bez nieobecności, wersje/podgląd i UI mobile/desktop.

## Uzupełnienie E3/E9 — osobisty kalendarz

Zlecone 2026-11-08: „Dodaj do kalendarza” z wyborem Google, Outlook, Apple i innych aplikacji. Odbiór: bieżąca data/godzina/miejsce, poprawne UTC/DST i polskie znaki, bez eksportu odwołanych/usuniętych spotkań i danych uczestników, plik ICS oraz czytelne ograniczenie do jednorazowego eksportu.

Zlecone 2026-11-09 uzupełnienie osobistego kalendarza: przycisk także na kafelkach oraz zbiorczy plik dla wyświetlanego miesiąca lub najbliższych 12 miesięcy. Weryfikacja i źródła importu w [raporcie](personal-calendar-report.md).


Aktualizacja 2026-11-09: eksport zbiorczy miesiąca/12 miesięcy wycofany na prośbę użytkownika. Pozostają przyciski eksportu pojedynczego terminu na kafelkach i w szczegółach.

## Uzupełnienie E4/E6/E9 — wstępne drużyny

Zlecone 2026-11-09: boisko z potwierdzonych zapisów przed obecnością, domyślnie ELO, automatyczne odświeżanie po deklaracjach i rezygnacjach, zapisane losowanie/ręczna zamiana administratora oraz wykorzystanie podglądu po sprawdzeniu obecności. Odbiór: limit 14 i jedno miejsce na osobę, brak rezerwy/ofert, aktualne ELO, konflikty listy/drugiej karty, prywatność, brak skutków w obecności/ELO i widok mobile. Zakres i wyniki: [raport](preliminary-court-report.md).

## Uzupełnienie E3/E9 — gesty nawigacji spotkań

Zlecone 2026-11-11: gest w lewo/prawo oraz przyciski następnego/poprzedniego spotkania na głównym ekranie i szczegółach. Odbiór: chronologia także dla przesuniętych terminów i granic miesięcy/lat, pomijanie usuniętych, brak deklaracji przy nawigacji, brak kolizji z przewijaniem/formularzami/dotknięciami i obsługa błędu odczytu.


### Płynny kafelek — uzupełnienie 2026-11-11

Zlecone i zaimplementowane: ruch całego kafelka za palcem, powrót po krótkim/anulowanym geście, kierunkowe przejście także z przycisków, pobranie nowego terminu przed animacją i ograniczenie ruchu według ustawienia systemu. Dowody i ograniczenia: [raport nawigacji](meeting-navigation-report.md#płynny-kafelek--uzupełnienie-2026-11-11).
