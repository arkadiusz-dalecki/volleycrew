# Weryfikacja i odbiór wydania

## Zasady

Dobieraj testy do skutków zmiany. Najważniejsze są reguły miejsc, autoryzacja, czas, ranking i trwałość. Używaj PostgreSQL do testów transakcji; SQLite i mocki repozytorium nie dowodzą poprawności blokad. Zegar i źródło losowości muszą być kontrolowalne w testach. Komendy i wyniki raportuj z rzeczywistego uruchomienia, a niewykonane próby oznaczaj wprost.

## Macierz obowiązkowych przypadków

| Obszar | Przypadki i oczekiwany rezultat |
| --- | --- |
| Dostęp | Brak zaproszenia/nieaktywny link nie rejestruje; wielokrotny aktywny link działa; nowy profil ma status gościa nawet przy próbie przesłania `founder`/`player` w rejestracji; niepoprawny PIN jest limitowany; grant resetu jednokrotny i wygasa; restart nie zeruje ochrony logowania |
| Sesje | Pamiętanie urządzenia, inne urządzenie wymaga PIN; logout i blokada unieważniają sesje; blokada uniemożliwia logowanie i zwalnia przyszłe miejsca/rezerwacje/oferty bez usunięcia historii, wyników i ELO; równoczesne przyjęcie oferty/zapis nie przywraca miejsca zablokowanemu; zwolnienie podlega D2; mutacja bez CSRF odrzucona; użytkownik nie zmienia roli payloadem |
| Lista logowania | Anonimowy katalog zawiera tylko ID, imię, maskowane nazwisko i ewentualny przydomek; brak pełnego nazwiska/statusu w JSON i DOM. `Nowak → N*****k`; zawsze pięć gwiazdek niezależnie od długości nazwiska, poprawne polskie znaki i krótkie nazwiska; jednakowe maskowane etykiety nadal wybierają różne ID; wybranie profilu nie loguje bez PIN-u. Rejestracja tworzy nowy profil i nie wybiera go z listy |
| Prywatność | Gracz A nie odczytuje historii ani statusu priorytetu gracza B przez endpointy, URL, ranking, listę uczestników/rezerwę ani katalog logowania; pola statusu nie trafiają do jego odpowiedzi API. Własny status i administracyjny odczyt działają. Zwykły gracz nie edytuje składu/wyniku/obecności |
| Limit | Dwie równoczesne próby ostatniego miejsca, oferta kontra nowy zapis, dwa przyjęcia tej samej oferty; suma miejsc i rezerwacji nie przekracza 14 |
| Priorytet | Założyciel wypiera zawodnika/gościa, zawodnik wypiera gościa, gość nie wypiera wyższych statusów wcześniej niż 24 h; ten sam status respektuje kolejność; po granicy brak wyparcia; wolne miejsce nadal dostępne; zmiana statusu przed granicą przelicza miejsca bez zmiany czasu zgłoszenia, po granicy chroni zajęte miejsca, aktywne rezerwacje D2 zachowane |
| Ponowienie | Dwuklik, retry po utracie odpowiedzi i ponowne otwarcie strony nie zmieniają timestampu kolejności ani nie dublują skutków |
| Rezerwa | Żadna automatyczna obecność; miejsce chronione dla pierwszej osoby z kolejki także przed wysłaniem propozycji; nowy zapis nie przejmuje rezerwacji; brak automatycznego timeoutu; tylko adresat przyjmuje ważną ofertę; ręczne przekazanie unieważnia poprzednią; odmowa/ręczne zamknięcie za brak odpowiedzi wycofuje zgłoszenie bez kary; ponowny zapis ma nowy czas i respektuje status; kilka miejsc przypisanych odrębnym osobom, bez duplikatów; odwołanie zamyka oferty zgodnie z D2 |
| Rezygnacja | Przed, dokładnie na i po granicy; wyjątek późno przyjętej oferty; zwykły późny zapis bez wyjątku; no-show nie jest usprawiedliwiony przez ofertę |
| Kalendarz | Dalsze miesiące, zmiana dnia, DST w marcu i październiku, przekroczenie roku, dwa generowania tego samego wystąpienia |
| Zmiany | Pojedynczy termin i harmonogram od daty; stabilny ID; zachowana pierwotna kolejność zgłoszeń niezależnie od kolejności odpowiedzi; stare potwierdzenie/oferta nieważne, ponowne dotyczą aktualnej wersji; dwie kolejne zmiany terminu wymagają potwierdzenia ostatniej wersji, zachowując pierwotną kolejność i pojedynczą rezerwację zgodnie z D4; brak automatycznego zwalniania miejsca przy braku odpowiedzi; nowe zgłoszenie nie przejmuje rezerwacji, ręczne zwolnienie działa bez przekroczenia 14 miejsc; odwołane w kalendarzu, bez no-show |
| Obecność | Deklaracja nie równa się obecności; finalizacja tworzy poprawną historię raz; korekta wymaga administratora i niepustego powodu, zachowuje wpis źródłowy, autora i czas; zawodnik widzi własną poprawkę, inni nie widzą ani wpisu, ani powodu; konflikt wersji odrzucony; korekta nie modyfikuje po cichu składu/wyniku/ELO; spóźniony jako obecny bez osobnej kary; usprawiedliwienie zachowuje pierwotny wpis; dopisanie bez deklaracji tylko przez administratora, istniejący niezablokowany profil, wolne niezarezerwowane miejsce i maks.14, także przy konkurencyjnej mutacji; nieobecni poza drużynami |
| Wstępne boisko | Potwierdzone miejsca bez rezerwy/ofert/ponownego potwierdzenia; 0–1 stan pusty, 2–14 bez duplikatów; aktualne ELO i deterministyczny podział; wspólne wyjątki administratora, reset po join/cancel, brak odradzania starego wyjątku; konflikty rewizji/listy, brak mutacji obecności/ELO; jawne użycie po obecności, zmieniona faktyczna lista wyrównana ponownie |
| Drużyny | Losowy podział nie gubi/nie dubluje graczy; wyrównany zgodny z definicją; 11/12/13/14 osób; maks.7; ręczna zamiana przy 7:7; konflikt drugiej karty nie nadpisuje zatwierdzenia |
| Wynik | Sety nieujemne całkowite; 0:0 zamyka bez setów i bez ELO, zachowując obecność; wynik wyłącznie dla zatwierdzonych składów; retry nie zmienia ELO drugi raz; korekta wymaga administratora i powodu, zachowuje stary wynik i atomowo przelicza późniejsze mecze, również przy zmianie do/z 0:0; audyt spójny |
| Dokument | PDF po kontroli z listy faktycznie obecnych (bez samych deklaracji i rezerwy), ponowne generowanie po korekcie daje aktualny skład wg D7; polskie znaki, długie nazwiska i 14 podpisów; przydomek rozróżnia profile przy wyborze, ale nie trafia na wydruk szkolny; zawodnik może zmienić własny przydomek, nie cudzy, bez zmiany ID, imienia/nazwiska, statusu i historii; brak obcięcia na A4; autoryzacja pobrania |
| UI | 360/390/430/768/1440px; wszystkie stany własnej deklaracji, klawiatura ekranowa, safe area, dialogi, fokus, błąd API, utrata sieci i stara wersja |
| Wdrożenie | Start, migracja i restart bez utraty danych; nowa instalacja oraz aktualizacja poprzedniego wydania; brak DB; błędna konfiguracja; health odróżnia readiness |
| HA/proxy | Ingress i domena HTTPS; dynamiczny prefiks i przeładowanie tras; cookies i CSRF; brak zaufania do sfałszowanych forwarded headers; listener Ingress niedostępny z publicznego wejścia |
| Backup | Odtworzenie bazy i konfiguracji na pustym środowisku; zgodne konta, sesje/polityka ponownego logowania, zapisy, historia, składy i ELO |

## Własności ELO (K=32 zatwierdzone, pozostałe reguły według D8)

Dla identycznych średnich ELO przed spotkaniem: 5:0 daje +16/−16 na osobę; 3:2 daje +3,2/−3,2; 3:3 daje 0/0. Te przykłady stanowią kryteria zaakceptowanej skali.

- Równorzędne drużyny: 5:0 powoduje większą bezwzględną zmianę niż 3:2.
- Ta sama proporcja, te same składy i te same punkty przed: 3:2 i 6:4 dają identyczny przyrost.
- Remis równorzędnych nie zmienia punktów; remis słabszych z silniejszymi daje słabszym wzrost.
- Każdy członek tej samej drużyny ma równą deltę, również siódmy rotujący.
- Punkty oczekiwane korzystają ze stanu przed meczem; zapis strony A nie zmienia wejścia dla strony B.
- Nieobecni bez wpisu ELO. Ponowny zapis tej samej rewizji bez kolejnej zmiany.
- Powtórne przeliczenie pełnej historii daje to samo co zapis kolejnych spotkań i ich zatwierdzonych korekt.

## Minimalne ścieżki E2E

1. Zaproszenie → rejestracja → deklaracja na dalszy termin → odświeżenie → stan zachowany → ponowne otwarcie z sesją.
2. Rezygnacja uczestnika → ręczne utworzenie propozycji → gracz rezerwy przyjmuje → aktualna lista na drugim urządzeniu.
3. Administrator zatwierdza obecność → dzieli drużyny → poprawia pełne składy → zatwierdza → tworzy listę → zapisuje wynik → gracze widzą ranking.
4. Zmiana daty → stare potwierdzenie nieważne → ponowne potwierdzenie; odwołanie kolejnego terminu pozostaje w kalendarzu bez kar.
5. Gracz próbuje endpointów administratora i historii innego gracza → odmowa bez ujawnienia danych.

Scenariusze uruchamiać na seederze testowym z jawną strefą i czasem. Sprawdzenie UI obejmuje rzeczywiste renderowanie i screenshoty; sprawdzenie samego wygenerowanego HTML nie zastępuje próby w przeglądarce.

## Warunki pierwszego wydania

- Uzgodniony zakres D9 działa od rejestracji do zakończenia meczu; brak otwartej reguły implementowanej przez przypadek.
- Backend lint/testy, frontend lint/typecheck/testy/build oraz wymagane E2E zakończone powodzeniem.
- Testy konkurencji miejsc, uprawnień i własności ELO mają dowody; brak znanych błędów naruszających limit, prywatność lub spójność punktów.
- UI wariantu A sprawdzone na telefonie; brak elementów demo, sekretów i testowych kont w produkcji.
- Docelowa instalacja Home Assistant i dostęp spoza LAN sprawdzone; architektury i przeglądarki z wynikiem w raporcie, nie jako domniemanie.
- Backup i restore faktycznie wykonane; podana lokalizacja kopii, częstotliwość i instrukcja odtworzenia bez ujawniania sekretów.
- Instrukcja instalacji, aktualizacji, rollbacku i podstawowych działań administratora jest gotowa.

## Raport odbioru

Raport zawiera wersję/commit, środowisko i CPU, wersje przeglądarek, testowane scenariusze z rezultatem, odnośniki do dowodów, wykonany restore, otwarte błędy i decyzję użytkownika o wydaniu. „Build przechodzi” nie zastępuje raportu działania aplikacji.

Precyzja: seria meczów jest obliczana bez pośredniego zaokrąglania do 1 miejsca; punkty i delty w UI mają 1 miejsce po przecinku. Odtworzenie historii daje ten sam stan w ustalonej tolerancji. Format UI nie zmienia obliczeń.
