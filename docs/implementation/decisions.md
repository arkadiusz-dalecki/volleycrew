# Rejestr decyzji otwartych

Podane propozycje nie są zatwierdzonymi regułami. Agent może implementować niezależne elementy i testować techniczne mechanizmy; nie może oznaczać zależnego etapu jako zakończonego bez rozstrzygnięcia. Po odpowiedzi użytkownika zapisz datę, decyzję i zaktualizuj właściwą specyfikację.

| ID | Pytanie i propozycja do omówienia | Blokuje |
| --- | --- | --- |
| D1 | Jak działa dostęp z internetu? Ustalić domenę, HTTPS, reverse proxy/tunel i adresy zaufanych proxy. Potwierdzić dostępny PostgreSQL oraz architekturę hosta HA. | Docelowy ingress, publikację i E10 |
| D2 | Zatwierdzone 2026-11-06: rezerwacja dla pierwszej osoby z kolejki, propozycje i zamykanie ręczne, bez automatycznego timeoutu. Odmowa lub ręczne zamknięcie z powodu braku odpowiedzi wycofuje zgłoszenie na ten termin; ponowny zapis ma nowy czas. Kilka wolnych miejsc oznacza osobne rezerwacje dla kolejnych osób. Reguły w domain-api.md. | Rozstrzygnięte |
| D3 | Zatwierdzone 2026-11-06: przed granicą 24 h zmiana statusu przelicza pierwszeństwo, zachowując czas pierwotnego zgłoszenia; w ostatnich 24 h nie odbiera zajętego miejsca. Status nie jest widoczny innym zawodnikom; własny profil i widok administratora pozostają zgodnie ze specyfikacją. | Rozstrzygnięte; reguły w domain-api.md i frontend.md |
| D4 | Zatwierdzone 2026-11-06: każda zmiana terminu wymaga nowego potwierdzenia, przy zachowaniu pierwotnej kolejności i rezerwacji miejsc. Miejsca zwalnia administrator ręcznie, bez timeoutu. Obejmuje to propozycje z rezerwy; stare oferty i potwierdzenia są nieaktualne, przyjęcie wymaga akceptacji nowego terminu. Reguły w domain-api.md. | Rozstrzygnięte |
| D5 | Zatwierdzone 2026-11-06: korekty i usprawiedliwienia z obowiązkowym powodem oraz prywatnym audytem bez kasowania wpisu źródłowego; spóźniony jest obecny bez osobnej kary. Administrator dopisuje osobę bez deklaracji z istniejącego, niezablokowanego profilu tylko przy wolnym, niezarezerwowanym miejscu i limicie 14. Reguły w domain-api.md. | Rozstrzygnięte |
| D6 | Zatwierdzone 2026-11-06: blokada unieważnia sesje, blokuje logowanie, zwalnia przyszłe miejsca i rezerwacje, zamyka oferty; historia i wyniki pozostają. Reguła w domain-api.md. Zatwierdzono też przydomek odróżniający identyczne imiona/nazwiska; wydruk szkolny zawiera tylko imię i nazwisko. Przydomek ustawia i zmienia sam zawodnik w profilu (zatwierdzone 2026-11-06). Przed logowaniem lista profili pokazuje imię, pierwszą i ostatnią literę nazwiska oraz gwiazdki zamiast środka; wybór profilu i sześciocyfrowy PIN. Reguły i projekcja API w domain-api.md. | Rozstrzygnięte |
| D7 | Zmienione 2026-11-08 na polecenie użytkownika: PDF z potwierdzonych zapisów dostępny przed spotkaniem do wydruku w domu; po zatwierdzeniu obecności z faktycznie obecnych. Bez rezerwy/ofert/oczekujących, bez wpływu wydruku na obecność. | Rozstrzygnięte; szczegóły poniżej |
| D8 | Zatwierdzone 2026-11-06/07: K=32, skala oczekiwań 400, bez pośredniego zaokrąglania, prezentacja do 1 miejsca; 0:0 bez ELO; korekty wyniku, historycznej obecności i składów z powodem oraz pełnym przeliczeniem. Kolejność według chwili startu i stałego ID. | Rozstrzygnięte; szczegóły poniżej i w domain-api.md |
| D9 | Akceptacja zakresu pierwszej wersji z README i kryteriów wydania; horyzont wsparcia, oczekiwany backup i dopuszczalna utrata danych. | Ostateczny odbiór E11 |
| D10 | Zatwierdzone 2026-11-06: jak w maybe-finance — repozytorium aplikacji HA, lokalny build przez Supervisor z Dockerfile (od 0.1.1 bez przestarzałego build.yaml; poprawka zgodności po próbie HA 2026-11-08), ręczne instalacje/aktualizacje po zmianie wersji config.yaml. Bez wymaganej publikacji własnych gotowych obrazów GHCR. Referencja potwierdzona odczytem manifestów i Dockerfile. | Rozstrzygnięte |

## Kolejność rozmowy

Aktualizacja 2026-11-06: [ustalenia E0](e0-foundations.md) zapisują odpowiedzi użytkownika. D1: Raspberry Pi 4 aarch64, osobny serwer PostgreSQL, dostęp Cloudflare Tunnel konfigurowany samodzielnie przez użytkownika; szczegóły wdrożeniowe odłożone do E10. D9: pełny zakres, codzienna kopia poza hostem i backup przed aktualizacją zatwierdzone; backupu jeszcze nie ma, retencja/cel i czas odtworzenia pozostają otwarte. D10 zatwierdzone: lokalny build przez HA i ręczne aktualizacje jak w maybe-finance, bez pipeline publikacji własnego obrazu. D7 zatwierdzone: PDF z faktycznie obecnych po kontroli, generowany ponownie po korektach. D2 zatwierdzone zgodnie z tabelą; D3 zatwierdzone wraz z prywatnością statusu; D4 zatwierdzone (każda zmiana wymaga ponownego potwierdzenia, zachowuje kolejność i rezerwacje, obejmuje oferty); D5 zatwierdzone (korekty/usprawiedliwienia, późne przyjście, dopisanie bez deklaracji); D6 zatwierdzone (blokada, przydomek oraz lista logowania z maskowanymi nazwiskami); D8 domknięte 2026-11-07: K=32, skala 400, precyzja, 0:0, pełne korekty wyników/obecności/składów z przeliczeniem oraz kolejność według startu i ID; szczegóły w tabeli i sekcji E8. Powyższe propozycje w tabeli należy czytać z tym statusem.

Najpierw D1 i D9, następnie D2–D6 przed finalizacją modelu zapisów, potem D7–D8. Nie trzeba rozstrzygać ELO przed zbudowaniem logowania i podstaw spotkań. Fundamenty techniczne można rozpocząć po zleceniu E0/E1, a zależne funkcje pozostawić jawnie nieukończone.

## Zatwierdzone rozszerzenie statusów — 2026-11-06

Trzy statusy: założyciel > zawodnik > gość. Gość jest domyślny przy rejestracji i ma najniższy priorytet. Zmiana statusu przez administratora podlega zatwierdzonemu D3, a prywatność statusów pozostaje w mocy. Reguła zastępuje wcześniejsze dwa poziomy; specyfikacja w domain-api.md. Przydomek w D6 zatwierdzony w tej samej rozmowie.

## Parametry dostępu E2 — zatwierdzone 2026-11-06

Użytkownik zatwierdził: sesja wygasa po 30 dniach bez korzystania, nie później niż 180 dni od utworzenia; grant resetu PIN-u jest jednorazowy i ważny przez 30 minut; po 5 nieudanych PIN-ach dla profilu w oknie 15 minut następne próby są czasowo odrzucane do końca tego okna. Nie ma trwałej blokady wskutek błędnych PIN-ów. Poprawne logowanie przed wyczerpaniem limitu zeruje licznik profilu. Po upływie okna można ponowić próbę. Osobna ochrona techniczna źródła: 30 nieudanych PIN-ów/15 minut; rejestracja/bootstrap/reset: 10 prób danej operacji/źródło/15 minut. Liczniki są trwałe w PostgreSQL. Zaufanie do nagłówków proxy wymaga jawnej konfiguracji; konfiguracja tunelu i test Ingress pozostają E10.

## Szczegóły zmiany harmonogramu E5 — zatwierdzone 2026-11-06

Istniejące przyszłe spotkania przesuwamy na nowy dzień w tym samym tygodniu (poniedziałek–niedziela). Odwołane pozostają odwołane. Wcześniej ręcznie przesunięte spotkania zachowują indywidualny termin i są osobno oznaczone w podglądzie. Przyjęto po odpowiedzi użytkownika „Tak, zachowaj indywidualne terminy”. Kolizji istniejących spotkań i przesunięcia poza początek zakresu nie rozstrzygać przez scalenie lub skasowanie danych: podgląd ma wskazać konflikt wymagający zmiany zakresu.

## Szczegóły obsługi sali E6 — zatwierdzone 2026-11-06

Podział dla 2–14 obecnych osób, różnica liczebności najwyżej 1, maksymalnie 7 na stronę. Mniej niż 2 blokuje podział. Zatwierdzone składy można otworzyć do poprawy z obowiązkowym powodem; korekty składów po zapisaniu wyniku czekają na E8.

Po zatwierdzeniu obecności zwalniamy miejsca nieobecnych, zachowując pierwszeństwo rezerwy. Organizator może na sali potwierdzić fizycznie obecnego adresata jego rezerwacji. Spóźniony wraca przez korektę z powodem, jeżeli nadal jest miejsce. Użytkownik zatwierdził obie zasady w tej rozmowie.

## Domknięcie D8 w E8 — zatwierdzone 2026-11-07

Użytkownik zatwierdził skalę oczekiwań 400 przy K=32. Dla średnich 1000 kontra 1200 słabsi otrzymują za 5:0 +24,3, za 3:2 +11,5, za remis +8,3; silniejsi przy zwycięstwie tylko 3:2 tracą 5,1 punktu. Wynik jest oceniany względem oczekiwań, nie tylko samego zwycięstwa.

Dopuszczono pełną korektę historycznej faktycznej obecności oraz składów w jednej operacji z obowiązkowym powodem, zachowaniem poprzednich wersji i przeliczeniem tego oraz późniejszych spotkań. Powody korekt obecności nadal są dostępne wyłącznie organizatorowi i danemu zawodnikowi.

Mecze są liczone według chwili rozpoczęcia, a przy identycznej chwili według stałego ID spotkania. Kolejność wpisywania wyników nie ma znaczenia; dopisanie starszego wyniku przelicza kolejne mecze. Korekta nie zmienia chwili rozpoczęcia spotkania; stabilny porządek replay nie zależy od numeru rewizji ani czasu jej zapisania.


## Zakres wdrożenia E10 — 2026-11-07

Użytkownik potwierdził, że sam doda repozytorium do HA, wygeneruje token i zainstaluje aplikację. Zakres agenta: przygotowanie pakietu i instrukcji oraz lokalne testy kontenerów, Ingress i backup/restore. Bez dalszych działań w panelu HA, konfiguracji tunelu, publikacji repozytorium lub używania produkcyjnej bazy. Odbiór na docelowym Pi 4, pomiary i kopia poza hostem pozostają po stronie użytkownika. Zachowano D10: lokalny build jak w maybe-finance; BOOTSTRAP_TOKEN w opcjach umożliwia utworzenie pierwszego administratora bez SSH i tokenu API HA.

## Własna baza w pakiecie — zatwierdzone 2026-11-08

Użytkownik nie ma PostgreSQL i zlecił bazę wewnątrz Volleycrew. To zastępuje wcześniejsze wymaganie osobnego serwera dla nowych instalacji (D1/E0/E10). Pakiet 0.2.0 zawiera PostgreSQL 17, trwały katalog /data/postgresql, automatycznie tworzoną bazę/rolę/hasło i prywatny listener loopback. DATABASE_MODE=auto wybiera bazę własną przy pustym POSTGRES_HOST; istniejący host zachowuje tryb external. Zmiana utrwalonego trybu wymaga jawnej migracji danych, bez automatycznego tworzenia pustej alternatywy. Backup HA zatrzymuje aplikację i kopiuje spójny klaster; dodatkowo działa backup logiczny i odtworzenie z archiwum przy braku plików klastra. Nie ma automatycznego upgrade głównej wersji PostgreSQL.

## Kalendarz administratora — 2026-11-08

Użytkownik zlecił wyeksponowanie daty spotkania, stałe wyświetlanie najbliższego terminu w bocznym panelu oraz przeniesienie planowania z ustawień do kalendarza. Kalendarz udostępnia administratorowi dodanie pojedynczego terminu i planowanie cotygodniowej serii od–do. Przesunięcie jednego istniejącego spotkania (np. wtorek → środa) pozostaje indywidualnym wyjątkiem. Przyjęte zachowanie serii: zastępuje dotychczasowy harmonogram w wskazanym okresie; po dacie końcowej wraca poprzednia reguła. Dodatkowe pojedyncze spotkania pozostają niezależne. Szczegóły i odbiór: [raport](calendar-management-report.md).

## Poprawki mobilne, logowanie i podgląd administratora — 2026-11-08

Użytkownik zlecił poprawę formularza pojedynczego spotkania na telefonie, usunięcie podpisu pod „Najbliższe spotkanie”, rozwijaną listę logowania z domyślnym „Wybierz użytkownika” i zapamiętaniem ostatnio zalogowanego profilu oraz przełącznik użytkownik/administrator. Podgląd działa na własnym koncie administratora, bez podszywania się pod innego gracza i bez zmiany uprawnień API. Użytkownik zlecił również przycisk instalacji na iOS/Android. Android korzysta z dostępnego systemowego promptu, iOS z instrukcji dodania przez menu Safari, zgodnie z ograniczeniami platformy.

## Usuwanie spotkań i zarządzanie istniejącymi seriami — 2026-11-08

Użytkownik zlecił usuwanie wydarzeń bez pozostawiania ich jako odwołanych oraz edycję/usuwanie istniejących serii, w tym domyślnej wtorkowej na produkcji. Usunięty termin znika z kalendarza, najbliższego spotkania i bezpośrednich wejść; jego wystąpienie nie odradza się z reguły tygodniowej. Usuwanie serii obejmuje przyszłą część wskazanej reguły, również utrwalone i przesunięte terminy należące do niej; niezależne spotkania i rozegrana historia pozostają. Edycja wskazanej serii zmienia jej przyszłą część, zachowuje ID spotkań i reguły ponownego potwierdzania, a skrócenie zakresu usuwa wypadające terminy z widoku. Przed zmianą/usunięciem serii użytkownik widzi podgląd skutków; wersje chronią przed zmianami z drugiej karty. Nie wykonujemy zmian w produkcyjnej bazie.

## Lista podpisów przed wyjściem z domu — 2026-11-08

Użytkownik zmienił D7: potrzebuje wydrukować listę przed spotkaniem, a podpisy zebrać na sali. Przed zatwierdzeniem faktycznej obecności generujemy PDF z aktualnych potwierdzonych miejsc (bez rezerwy, rezerwacji ofert i oczekujących na ponowne potwierdzenie). Po zatwierdzeniu obecności źródłem są obecni. UI jasno podaje źródło, pobranie zawsze odczytuje aktualny stan. Sam wydruk nie zatwierdza obecności i nie wpływa na historię/ELO. Zastępuje wcześniejszą blokadę eksportu do zatwierdzenia obecności.

## Dodanie terminu do osobistego kalendarza — 2026-11-08

Użytkownik zlecił wybór aplikacji po kliknięciu „Dodaj do kalendarza”. Menu obejmuje Google Calendar, Outlook.com, Outlook Microsoft 365, Apple Calendar oraz inne aplikacje przyjmujące plik iCalendar. To eksport jednego terminu, z aktualnymi godzinami i miejscem, bez uczestników, sesji ani linku Ingress. Google/Outlook otwierają formularz do samodzielnego zapisania, Apple/inne pobierają `.ics`. Zmiany i odwołania w Volleycrew nie synchronizują automatycznie osobistego wpisu. Nie zapisujemy wydarzeń przez podłączone konto użytkownika ani nie wysyłamy zaproszeń.

## Kalendarz: eksport z kafelków i wielu terminów — 2026-11-09

Użytkownik zlecił tę samą opcję na kafelkach listy kalendarza oraz dodanie wielu spotkań naraz. Nad listą jest „Dodaj wiele spotkań do kalendarza” z wyborem wyświetlanego miesiąca albo najbliższych 12 miesięcy. Eksport zbiorczy pobiera aktualny zakres z API, pomija odwołane/zakończone/minione/usunięte wpisy i tworzy jeden plik ICS z osobnymi VEVENT. Import obsługują Google/Outlook/Apple i inne aplikacje; nie otwieramy kilkudziesięciu formularzy ani nie tworzymy nieskończonej serii ignorującej wyjątki. To jednorazowy import bez automatycznej synchronizacji.


## Wycofanie eksportu zbiorczego — 2026-11-09

Użytkownik zrezygnował z masowego przenoszenia spotkań do osobistego kalendarza. Zastępuje to powyższe zlecenie miesiąca/12 miesięcy: usuwamy funkcję zbiorczą i jej kod. Zachowujemy wybór aplikacji dla jednego spotkania na kafelkach oraz w szczegółach. Migracja bazy 0009 dotycząca usuwania spotkań i funkcje zarządzania seriami nie należą do wycofanego eksportu.

## Wstępne boisko przed obecnością — 2026-11-09

Użytkownik zlecił boisko przed sprawdzeniem obecności, przeliczane po zapisach/rezygnacjach, domyślnie według ELO, z możliwością innego podziału przez administratora. Źródłem wstępnych składów są wyłącznie osoby z aktualnym potwierdzonym miejscem (bez rezerwy, ofert i oczekujących na ponowne potwierdzenie). Podgląd jest widoczny całej ekipie i nie potwierdza obecności ani nie wpływa na wynik/ELO. Domyślny podział jest deterministyczny i wyrównany według bieżącego ELO. Ręczny/losowy podział administratora jest zapisany dla danej listy; zmiana osób, kolejności ponownego zapisu, terminu lub ELO unieważnia go i przywraca aktualny podział ELO. Po obecności administrator może jawnie użyć wstępnego podziału; przy różnicy osób generujemy wyrównany podział faktycznie obecnych.


## Etykieta deklaracji udziału — 2026-11-09

Na prośbę użytkownika przycisk „Będę” zmieniono na „Potwierdzam obecność”. To nadal deklaracja udziału przed spotkaniem; faktyczną obecność zatwierdza osobno administrator.

## Przesuwanie między spotkaniami — 2026-11-11

Użytkownik zlecił przechodzenie do kolejnego i poprzedniego spotkania gestem w głównym widoku. W lewo przechodzimy do następnego terminu, w prawo do poprzedniego, w kolejności kalendarza (aktualny start, następnie ID). Dostępne są także przyciski. Usunięte terminy pomijamy, odwołane pozostają widoczne jak w kalendarzu. Samo przejście nie deklaruje udziału.
