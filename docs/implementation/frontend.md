# Specyfikacja frontendu

## Referencja

Zaakceptowany wariant A w `prototype/index.html?variant=A`. `prototype/phone.html` pokazuje go na telefonie. Zachować jasne tło, zieleń, typografię, rytm kart, boczną nawigację desktopową i cztery zakładki mobilne. Przełącznik A/B/C i fikcyjne scenariusze należą tylko do prototypu/developmentu.

Odtworzyć UI jako komponenty z rzeczywistymi danymi. Główna struktura: `AppShell`, `MeetingHeader`, `ParticipationCard`, `ParticipantList`, `Waitlist`, `Calendar`, `Court`, `AttendanceChecklist`, `ResultForm`, `RankingTable`, `ProfileForm`. Nazwy katalogów dopasować do `architecture.md`.

## Trasy i zakres

| Trasa | Zawartość |
| --- | --- |
| `/` | Najbliższe spotkanie; pusty stan, gdy nie ma następnego terminu |
| `/meetings/:id` | Ten sam ekran dla wybranego spotkania, powrót do kalendarza |
| `/calendar` | Miesiąc i lista terminów, nawigacja dalej bez limitu tygodni |
| `/ranking` | Ranking i wyniki z linkiem do meczu |
| `/profile` | Dane, status, zmiana PIN-u i prywatna historia |
| `/join#token` | Walidacja zaproszenia, imię/nazwisko, sześciocyfrowy PIN i jego powtórzenie |
| `/login` | Lista profili: imię, maskowane nazwisko (np. Michał N*****k), ewentualny przydomek; wybór istniejącego profilu i sześciocyfrowy PIN |
| `/reset-pin#token` | Ustawienie nowego PIN-u przez jednorazowy grant |
| `/admin/settings` | Statusy i blokady, link zaproszenia, reset PIN-u |

Ustawienia administracyjne są dodatkową trasą, nie piątą główną zakładką. Panel obsługi konkretnego meczu pozostaje w jego szczegółach. Uprawnienia są danymi z API; frontend nie nadaje ich przez przełącznik. Przed blokadą profilu administrator widzi podsumowanie: wylogowanie zawodnika, zablokowanie dostępu i zwolnienie przyszłych miejsc/rezerwacji/ofert przy zachowaniu historii i wyników. Po zatwierdzeniu UI pobiera aktualne listy.

Status „założyciel/zawodnik/gość” nie jest publiczną etykietą. Uczestnicy i ranking w widoku zawodnika nie pokazują statusów innych osób. Własny status pozostaje w profilu i własnym podsumowaniu, a administrator ma dostęp do statusów w swoim widoku. Reguły pierwszeństwa mogą być objaśnione ogólnie, bez wskazywania, kto ma jaki status. Nowy profil otrzymuje status „gość”; formularz rejestracji nie oferuje wyboru statusu. Administrator wybiera jeden z trzech poziomów. Wybór profilu rozróżnia identyczne imiona i nazwiska dodatkowym przydomkiem, na ekranie logowania np. „Michał N*****k — Misiek”; wydruk szkolny zawiera samo imię i nazwisko. Zawodnik sam ustawia i zmienia własny przydomek w osobnym polu profilu. Pole jest niezależne od imienia i nazwiska; zapis nie zmienia tożsamości konta ani statusu. Zatwierdzone 2026-11-06.

## Spotkanie zawodnika

Kolejność: termin/miejsce → własny stan i akcja → liczba miejsc → wstępne boisko → uczestnicy/rezerwa → zatwierdzone drużyny/wynik. W desktopowym bocznym panelu własny ranking i kolejne terminy; na telefonie główna deklaracja pozostaje przed dodatkowymi treściami.

Osobne stany własnej karty: brak deklaracji, potwierdzony udział, rezerwa z pozycją, aktywna oferta, „nie będę”, ponowne potwierdzenie po zmianie terminu, odwołane, zakończone. Stan oferty pochodzi z API, nie z pozycji 1 na rezerwie. Każda zmiana daty pokazuje stary i nowy termin oraz wymaga nowego potwierdzenia, także przy propozycji z rezerwy. Stary ekran z ofertą po próbie akceptacji informuje o zmianie i pobiera aktualny stan; nie pokazuje pozornego sukcesu. Przy ponownym potwierdzaniu miejsce czeka na odpowiedź bez automatycznego timeoutu. Administrator ma jawną akcję zwolnienia miejsca przy braku odpowiedzi; nie przedstawiać oczekującego gracza jako potwierdzonego uczestnika.

Przed rezygnacją backendowy preview lub spójnie obliczona informacja ze stanu API wyjaśnia, czy będzie to rezygnacja zwykła/późna/z wyjątkiem. Ponownie walidować przy zatwierdzeniu — granica czasu mogła zostać przekroczona. Zamrożenie priorytetu nie blokuje przycisku zapisu na wolne miejsce.

## Obsługa organizatora

1. Obecność: duże pola dotykowe przy nazwiskach; osobne zapisanie szkicu i świadome zatwierdzenie. Wyjaśnić skutek dla historii nieobecności.
   Spóźnionego oznacz jako obecnego; wcześniejszy błędny wpis popraw z powodem. Akcja „Dopisz obecną osobę” wybiera istniejący profil, a API sprawdza wolne niezarezerwowane miejsce i limit 14. Usprawiedliwienie używa formularza korekty z zachowaniem pierwotnego wpisu.
2. Drużyny: „Losowo” i „Według rankingu”, potem schemat boiska z liczbą osób i średnim ELO obu stron. Do sześciu na połowie, siódmy w rotacji. Rozmieszczenie nie oznacza pozycji sportowej.
3. Dotknięcie zawodnika umożliwia ręczne przeniesienie; backend potwierdza cały podział. Dla pełnych drużyn przewidzieć zamianę dwóch graczy lub edycję szkicu bez pośredniego zapisu niepoprawnego składu. Zmiana szkicu nie zmienia zatwierdzonego składu.
4. Zatwierdzenie blokuje przypadkowe edycje. Powrót do edycji jest jawną operacją z regułą korekty, a nie ponownym losowaniem w tle.
5. Po grze wynik setów A/B, podsumowanie i jedno zatwierdzenie. Wynik 0:0 zamyka spotkanie bez rozegranych setów i bez zmiany ELO, zachowując obecność. Korekta wyniku wymaga powodu; pokazać stary i nowy wynik oraz informację o przeliczeniu późniejszych meczów. Punkty i delty prezentować do jednego miejsca po przecinku. Zapisany wynik widać po ponownym wejściu.

Lista podpisów ma osobną akcję przed spotkaniem (potwierdzone zapisy) oraz po zatwierdzeniu faktycznej obecności (aktualni obecni): podgląd i pobranie PDF. Po korekcie obecności można wygenerować go ponownie (D7). Historia innych osób dostępna administratorowi w ekranie gracza, nie przez publiczny ranking. Przy wpisie administrator ma akcję korekty z obowiązkowym powodem i podsumowaniem zmiany. Pierwotny wpis i poprawkę widać w prywatnej historii gracza, wraz z datą, autorem i powodem; żaden z tych elementów nie trafia do publicznych list.

## Dostępność i odporność

- Sprawdzić szerokości 360, 390, 430, 768 i 1440 px. Brak poziomego przewijania; boisko przechodzi na pion przy wąskim kontenerze. Pełne nazwiska pozostają czytelne, również długie i powtarzające się.
- Cel dotyku co najmniej 44 × 44 px; tekst akcji i nazwisk czytelny na telefonie. Status oznaczony słowem i kolorem. Kontrast WCAG AA dla tekstów i kontrolek.
- Semantyczne przyciski i etykiety, obsługa klawiatury, widoczny fokus, dialog z pułapką i powrotem fokusu. Boisko dostępne także jako uporządkowana treść dla czytnika.
- Dolna nawigacja uwzględnia safe area i klawiaturę ekranową. Dialog dłuższy niż ekran przewija się i pozwala dotrzeć do akcji.
- Każdy ekran danych ma loading, pusty stan, błąd z ponowieniem i stan sesji wygasłej. Błąd serwera nie usuwa wpisanego wyniku ani PIN-u przed pokazaniem komunikatu; PIN nie jest logowany ani trwale zapisywany.
- Przy wysyłce blokada ponownego kliknięcia; ochrona backendowa nadal obowiązuje. Brak optymistycznego „masz miejsce” przed odpowiedzią.
- Odświeżaj po własnej mutacji, powrocie do karty i ponownym połączeniu. Gdy lista spotkania jest widoczna, proponowane odpytywanie co 30 s; po konflikcie od razu. WebSocket nie jest wymagany.
- Zapis bez połączenia pokazuje błąd i pozwala ponowić. Nie kolejkuj deklaracji offline. Ekran ze starą listą wyraźnie oznacza problem z odświeżaniem.
- Adres spotkania i aktywna zakładka działają po odświeżeniu/przejściu bezpośrednim, również pod prefiksem Ingress.
- Fonty i ikony dostarczane z aplikacją. Produkcyjny UI nie wymaga pobierania Google Fonts z internetu.

Manifest web-app i ikony można dodać bez service workera. Ewentualny cache nie przechowuje prywatnej historii ani autoryzowanych odpowiedzi API i nie może podawać starej listy jako aktualnej.

Ekran logowania nie wymaga wpisywania pełnego nazwiska ani nie udostępnia pełnych nazwisk w danych strony. Rejestracja przez zaproszenie to osobny formularz tworzący nowy profil z pełnym imieniem i nazwiskiem; nie pokazuje selektora istniejących kont. Po zalogowaniu grupa widzi imiona i nazwiska uczestników zgodnie z pozostałą specyfikacją.

## Dostęp w E2

`/setup#token` to osobny formularz pierwszego organizatora, bez wyboru istniejącego profilu. Publiczne ekrany logowania, rejestracji i resetu nie pokazują nawigacji prywatnej grupy. Po wylogowaniu lub utracie sesji prywatne dane z pamięci klienta są usuwane, a widok wraca do logowania. PIN-y istnieją wyłącznie w polach formularzy i żądaniu; nie są zapisywane w localStorage. Ustawienia ekipy są osiągalne również na telefonie z własnego profilu administratora. Zmiana statusów i rozliczanie przyszłych miejsc przy blokadzie dojdą w E4; E2 udostępnia zaproszenia, reset i blokadę dostępu.

## Kalendarz i spotkanie w E3

Miesiąc jest zapisany w URL `/calendar?month=YYYY-MM`. Można przechodzić strzałkami, wybrać dowolny miesiąc polem natywnym lub wrócić do obecnego. Siatka i lista korzystają z tego samego API; wybór dnia filtruje listę. Odwołanie jest podpisane słowem i oznaczone osobnym kolorem. Otwieranie wirtualnego terminu utrwala wyłącznie spotkanie i prowadzi pod stabilny `/meetings/:id`. Nie jest deklaracją „będę”. Powrót ze szczegółów prowadzi do miesiąca aktualnego terminu, także po jego przesunięciu.

Najbliższe spotkanie pobiera datę, godzinę, miejsce i stan z API. Nie zawiera stałego ograniczenia do wtorków. Szczegóły odczytują uczestników/rezerwę z bezpiecznych DTO. Do E4 zapisy nie są dostępne; brak pozornego sukcesu albo fikcyjnej listy graczy. W E3 są stany ładowania, pustego zakresu, błędu z ponowieniem i starych danych przy błędzie odświeżenia.

## Udział i rezerwa w E4

Karta własnego udziału działa przy najbliższym oraz wybranym z kalendarza spotkaniu. „Potwierdzam obecność” na wirtualnym terminie najpierw rozwiązuje go do Meeting, potem zapisuje deklarację; sukces jest prezentowany dopiero po odpowiedzi. Pokazujemy potwierdzone miejsce, pozycję rezerwy, rezerwację przed propozycją, aktywną propozycję do jawnego przyjęcia/odmowy oraz „nie będę”. Liczniki wolnych i zarezerwowanych miejsc wyjaśniają, dlaczego np. przy 13 potwierdzonych osobach może nie być wolnego miejsca.

Rezygnacja ma własne potwierdzenie z aktualną informacją: zwykła, późna, z wyjątkiem późno przyjętej oferty albo wycofanie samej rezerwy. Po konflikcie lub błędzie API pobieramy aktualny stan. Żądanie deklaracji zachowuje UUID do ponowienia przy błędzie sieci; po odpowiedzi 4xx i nowej decyzji powstaje nowy klucz. Nie zapisujemy deklaracji offline.

Organizator ma w szczegółach panel rezerwacji. „Zaproponuj miejsce” aktywuje propozycję i przypomina o ręcznej wiadomości na Messengerze. „Przekaż dalej” wymaga potwierdzenia skutku: wycofanie zgłoszenia i rezerwacja dla następnej osoby. Bez automatycznego odliczania czasu. Zmiana statusu w ustawieniach jest prywatnym selektorem administratora. Podsumowanie blokady obejmuje przyszłe miejsca, rezerwacje i oferty oraz zachowanie historii.

## Harmonogram i zmiany w E5

Ustawienia organizatora zaczynają się od harmonogramu: data obowiązywania, dzień tygodnia, godzina, czas gry i miejsce. „Pokaż podgląd harmonogramu” wyświetla zakres istniejących zmian, nowe potwierdzenia, zachowane wyjątki i przykłady przyszłej reguły. Zapis wymaga osobnego zatwierdzenia. Zmiana któregokolwiek pola usuwa dawny podgląd; konflikt odświeża dane i wymaga nowego podglądu.

W szczegółach spotkania administrator zmienia pojedynczy termin lub odwołuje spotkanie po potwierdzeniu skutków. Przy zmianie grupa widzi poprzednią i aktualną datę. „Potwierdzam nowy termin” przywraca dotychczasowe miejsce; oczekujący są osobną listą, nie potwierdzonymi uczestnikami. Organizator może ręcznie zwolnić oczekujące miejsce, z wyjaśnieniem skutku dla kolejki. Stare propozycje z rezerwy nie dają miejsca w nowym terminie.

Indywidualne wyjątki pozostają bez zmiany przy nowej stałej regule, zgodnie z decyzją użytkownika. Odwołanie zostaje widoczne w kalendarzu i szczegółach. Dwie karty organizatora nie nadpisują zmian po cichu: błąd wersji zachowuje formularz, pokazuje komunikat i pobiera aktualne dane. Powiadomienia na Messengerze są nadal ręczne.

## Obecność, boisko i prywatna historia w E6

W szczegółach trwałego, nieodwołanego spotkania organizator ma panel „01 Obecność → 02 Drużyny → 03 Wynik”. Wynik jest kolejnym krokiem E8; nie ma pozornego formularza ani zapisu wyniku w E6.

Obecność: duże przyciski „Obecny/a” i „Nieobecny/a”, możliwość oznaczenia wszystkich jako obecnych, osobny zapis szkicu i osobne potwierdzenie skutków zatwierdzenia. Nieustalony stan blokuje zatwierdzenie. Przed rozpoczęciem gry można zapisać szkic; zatwierdzenie jest dostępne od startu spotkania. Zatwierdzony stan zmienia się korektą z obowiązkowym powodem. Spóźnienie używa klasyfikacji obecności. Usprawiedliwienie zachowuje źródłowy wpis. Sekcja rozwijana obsługuje fizycznie obecnych adresatów rezerwacji, przekazywanie rezerwacji dalej z potwierdzeniem i dopisywanie istniejącego aktywnego profilu przy wolnym miejscu.

Drużyny: losowanie lub wyrównanie według rankingu, następnie boisko wariantu A. Pełne imiona i nazwiska zawijają się bez ucinania; przydomek pomaga rozróżniać osoby. Każda połowa pokazuje do sześciu osób, siódma trafia do podpisanej rotacji pod boiskiem. Na wąskim ekranie połowy są jedna nad drugą, na szerokim obok siebie (próg szerokości samego boiska). Przycisk zawodnika zaznacza go, dotknięcie osoby z przeciwnej drużyny zamienia obie osoby. Zamiana działa przy pełnym 7:7 i obejmuje rotację. Wybraną osobę można też przenieść z większej do mniejszej drużyny. Ręczne poprawki zapisuje się przed osobnym zatwierdzeniem. Zatwierdzone składy widać graczom; szkic widzi wyłącznie organizator. Otwarcie do poprawy wymaga powodu i ponownego zatwierdzenia.

Prywatna historia jest w „Mój profil”. Organizator otwiera historię zawodnika z ustawień ekipy lub zatwierdzonej listy obecności (`/admin/players/:playerId/history`). Wpis zawiera źródłową klasyfikację, bieżącą wartość oraz korekty z powodami, datami i autorami. Brak tych pól w kartach uczestników i publicznym boisku. Zwykły gracz nie otworzy administracyjnej trasy ani API innej osoby.

Mutacje pokazują sukces po odpowiedzi serwera. Utrata odpowiedzi zachowuje dokładną operację i jej klucz do jawnego ponowienia. Konflikt wersji odświeża stan, ale nie nadpisuje lokalnych poprawek: użytkownik widzi ostrzeżenie i przycisk wczytania aktualnej listy/składów. Niezapisane lokalne poprawki nie są publikowane i nie służą do zatwierdzenia.

## Lista podpisów — E7

W nagłówku panelu organizatora jest „Lista podpisów”, dostępna już przed spotkaniem z potwierdzonych zapisów, a po zatwierdzeniu obecności z faktycznie obecnych (zmiana D7 z 2026-11-08). Prowadzi do administracyjnej trasy `/admin/meetings/:meetingId/signature-list`, z powrotem do konkretnego spotkania. Zwykły zawodnik nie ma przycisku ani dostępu do trasy/API.

Podgląd renderuje rzeczywisty PDF lokalnie przez PDF.js, także na telefonie bez wbudowanej przeglądarki PDF. Parser i jego worker są dostarczane z aplikacją, ładowane dopiero przy podglądzie; nie korzystają z CDN. Wszystkie strony są pokazywane w szerokości karty. Warstwa tekstowa dla czytników ekranu zawiera treść dokumentu. Osobny link otwiera PDF w nowej karcie.

„Pobierz aktualny PDF” zawsze wykonuje nowe autoryzowane żądanie i uwzględnia korekty, nawet jeśli wcześniejszy podgląd pozostawał otwarty w innej karcie. „Odśwież podgląd” ponownie pobiera dokument. Porównanie rewizji z odpytywaną obecnością pozwala ostrzec o zmianie listy. Są stany generowania, renderowania, błędu, ponowienia i wygasłej sesji; podgląd i operacja pobierania są zwalniane/anulowane przy opuszczeniu strony. PDF nie trafia do localStorage ani trwałego cache aplikacji.

Wydruk: A4, skala 100%; przeglądarka PDF udostępnia druk. Źródło bieżącej listy jest jasno opisane w podglądzie. Przed zatwierdzeniem obecności dokument powstaje z potwierdzonych miejsc, a później z zatwierdzonej faktycznej obecności.


## Wyniki i ranking — E8

Krok „03 Wynik” w panelu organizatora jest dostępny po zatwierdzeniu składów. Dwa duże pola numeryczne pokazują sety A/B. „Pokaż podgląd punktów” pobiera wyliczenie z serwera; osobne „Zapisz wynik i ranking” publikuje je razem. Zmiana pól unieważnia podgląd. Dla 0:0 jest jawna informacja o zamknięciu bez setów i bez wpisów ELO za ten mecz. Stara wersja spotkania/rankingu wymaga nowego podglądu; błąd nie kasuje pól, a utrata odpowiedzi pozwala ponowić tę samą operację z tym samym kluczem.

Po zapisaniu organizator widzi wynik, delty na osobę, średnie sprzed meczu, wersje z autorem/czasem i prywatną historię powodów/składów. „Skoryguj wynik lub składy” otwiera formularz z obowiązkowym powodem. Skład jest edytowany dotykiem na tym samym boisku; każda zmiana zbioru obecnych wymaga osobnej klasyfikacji i prywatnego powodu. UI nie dopisuje ósmej osoby na stronę i blokuje zatwierdzenie niewłaściwej liczebności. Podczas edycji historycznej nie pokazuje pozornych średnich dla jeszcze nieprzeliczonego składu. Po podglądzie następuje osobne zatwierdzenie całej korekty.

Gracz w szczegółach zakończonego spotkania ma kartę wyniku i aktualne drużyny. „Ranking” zawiera widoki „Punkty zawodników” i „Historia spotkań”, z paginacją i odświeżaniem co 30 s. Zawodnik bez meczów ma 1000,0 punktów; punkty i delty są prezentowane do jednego miejsca. Kliknięcie nazwiska otwiera `/ranking/players/:id` z historią przed → delta → po i linkami do meczów. Wynik 0:0 jest w historii spotkań, ale nie w dzienniku punktów.

Powody korekt wyniku/składu są widoczne tylko organizatorowi, a prywatne powody obecności tylko jemu i danej osobie w profilu. Publiczny ranking, historia punktów i karta wyniku nie zawierają priorytetów, flag blokady ani zdarzeń nieobecności. Są osobne stany ładowania, błędu i ponowienia. Poprawki nie są publikowane optymistycznie.


## Integracja E9

Potwierdzenia rezygnacji, przekazania miejsca, blokady i pojedynczej zmiany/odwołania terminu używają wspólnego natywnego dialogu. Escape i anulowanie nie zapisują zmian; fokus wraca do przycisku otwarcia, a po jego usunięciu do głównej treści. Anulowanie podglądu edycji terminu zachowuje formularz.

Przy błędzie odświeżania sesji z zachowaną tożsamością UI pozostaje otwarty z ostrzeżeniem i ponowieniem. Edytory sali/wyniku i harmonogramu oraz korekty historii nie są demontowane przy chwilowej awarii odczytu już pobranych danych. Potwierdzone 401 usuwa dane prywatne i prowadzi do logowania; po zalogowaniu wracamy do żądanej wewnętrznej trasy. Zwykłe wejście do logowania bez zapamiętanej trasy prowadzi po zalogowaniu do spotkania. Nieudany zapis nie jest kolejką offline: użytkownik ponawia go świadomie.

Manifest i ikona są lokalne, bez service workera. Dolna nawigacja uwzględnia safe area i wykrywanie klawiatury przez visualViewport. Kontrola Chromium/WebKit i geometrii klawiatury nie oznacza odbioru fizycznych telefonów; aktualny stan jest w [raporcie E9](e9-report.md).


## Wejścia pakietu E10

Nginx renderuje `<base>` osobno dla zwykłego wejścia i aktualnego prefiksu Ingress. `lib/base.ts` dostarcza basename routera i bazę klienta API. Wszystkie nowe połączenia API i zasoby muszą zachować ten kontekst; nie konstruuj URL z samego `window.location.origin` ani ręcznie zakodowanego tokenu Ingress. Manifest i lazy worker PDF.js działają względem tej bazy. Oba wejścia wymagają własnego logowania Volleycrew, z oddzielnymi nazwami/ścieżkami cookies i właściwym CSRF. Testy produkcyjnego obrazu są oddzielne od Vite w `container-tests/`.

## Uzupełnienie kalendarza — 2026-11-08

Data (dzień tygodnia, dzień, miesiąc, rok) jest głównym nagłówkiem zielonej karty spotkania; godzina i miejsce są poniżej. Boczne menu wyświetla termin z `/meetings/next`, odświeżany co 30 s i po mutacjach, także gdy otwarte jest inne spotkanie. Obsługuje ładowanie, brak terminu i błąd z ponowieniem.

Planowanie dostępne wyłącznie administratorowi w `/calendar`: „Dodaj spotkanie” oraz „Zaplanuj serię”. Można wybrać również pusty dzień siatki jako datę nowego spotkania. Dodawanie wymaga podglądu i zatwierdzenia. Seria zawiera dzień tygodnia, godzinę, czas gry, miejsce i zakres od–do; koniec w UI jest włącznie, opcjonalny, po nim wraca wcześniejszy harmonogram. Podgląd wyjaśnia zastąpienie istniejącej reguły i ponowne potwierdzenia. Pojedynczą zmianę wtorku na środę wykonuje się przyciskiem „Zmień termin” na kafelku w kalendarzu; szczegóły spotkania zachowują dotychczasowe akcje. Ustawienia ekipy obejmują dostęp i zawodników.

### Akcje na kafelku — 2026-11-08

Kafelek przyszłego zaplanowanego spotkania w kalendarzu ma dla administratora przyciski „Zmień termin” i „Odwołaj”. Pierwszy rozwija formularz daty, godziny i czasu gry na tym samym kafelku; zapis nadal wymaga podglądu oraz potwierdzenia skutków dla zapisanych. Drugi otwiera dialog potwierdzenia odwołania. Widok pozostaje w kalendarzu; po przesunięciu aktywny filtr daty i ewentualnie miesiąc przechodzą do nowego terminu. Odwołany kafelek pozostaje ze statusem, bez ponownych akcji zmiany/odwołania. Zawodnik nie widzi tych przycisków.

### Rozmieszczenie mniejszych drużyn — 2026-11-08

Boisko dopasowuje układ do liczby graczy na danej połowie zamiast wyświetlać sześć miejsc z pustymi znacznikami. Jedna osoba jest pośrodku; dwie są ustawione przód/tył; trzy to jedna przy siatce i dwie z tyłu; cztery to 2+2; pięć to dwie przy siatce i trzy z tyłu; sześć to 3+3. Siódma osoba pozostaje w panelu rotacji. Obie drużyny są skierowane ku siatce, również przy pionowym boisku na telefonie. To układ poglądowy, bez zmiany przypisania graczy i reguł podziału.

## Uzupełnienie E2/E9 — poprawki po próbie na iPhonie (2026-11-08)

Logowanie używa natywnej listy rozwijanej „Twój profil”, z maskowanymi nazwiskami i przydomkami. Na nowym urządzeniu wybrana jest pusta opcja „Wybierz użytkownika”. Po poprawnym logowaniu, rejestracji lub resecie PIN-u zapamiętujemy wyłącznie ID ostatniego profilu w localStorage; przy istniejącej sesji także odtwarzamy ten wybór. Nie zapisujemy PIN-u. Gdy profil znika z publicznej listy, lista wraca do pustej opcji. Zablokowany localStorage nie uniemożliwia logowania.

Administrator ma nad treścią przełącznik „Administrator / Użytkownik”, również na telefonie. W widoku użytkownika ma własny profil i deklaracje oraz zwykłe widoki kalendarza, zatwierdzonych drużyn i wyniku; nie ma narzędzi ani tras administracyjnych. Przełączenie z trasy `/admin/…` prowadzi do spotkania. Wybór widoku jest zachowany w sessionStorage osobno dla konta; uprawnienia serwera pozostają niezmienione. To podgląd interfejsu na własnym koncie, nie logowanie jako inny gracz.

Podpis „Dobra ekipa, trochę ruchu i dwie godziny dla siebie.” usunięto. Formularz pojedynczego terminu nie ma ramki fieldset; pola daty i godziny mają ograniczoną szerokość także w Safari, a wąskie formularze używają jednej kolumny.

Na ekranach dostępu i w stopce aplikacji jest „Dodaj aplikację do telefonu”. Jeśli przeglądarka udostępnia `beforeinstallprompt`, kliknięcie wywołuje systemowe okno. W pozostałych przypadkach przycisk otwiera dialog z instrukcją właściwą dla iPhone/iPad, Androida lub komputera. iOS wymaga użycia menu Udostępnij → Do ekranu początkowego; strona nie może wykonać tego kroku automatycznie. Po wykryciu trybu standalone lub zdarzenia appinstalled przycisk znika. Manifest zawiera lokalne PNG 192/512, a iOS otrzymuje apple-touch-icon 180. Nie dodajemy cache API ani pracy offline. Instalacja wymaga docelowego adresu HTTPS; fizyczny odbiór instalacji i wejścia przez HA pozostaje osobnym testem.

## Zarządzanie istniejącymi seriami i wydruk przed spotkaniem (2026-11-08)

Kalendarz administratora ma stale widoczną listę „Twoje serie spotkań” z akcjami „Edytuj serię” i „Usuń serię”. Edycja ładuje wybraną regułę, w tym istniejącą domyślną wtorkową, i wymaga podglądu przed zapisem. Skrócenie zakresu pokazuje liczbę istniejących terminów do usunięcia; pozostałe reguły nie są automatycznie nadpisywane. Usunięcie serii wymaga dialogu z zakresem przyszłych spotkań i informacją o zachowanej historii. „Zaplanuj serię” pozostaje osobnym tworzeniem reguły.

„Usuń spotkanie” jest dostępne na kafelku i w szczegółach przyszłego lub odwołanego terminu. Dialog wyjaśnia zniknięcie z kalendarza, zamknięcie zapisów/ofert oraz zachowanie innych terminów. Po usunięciu w szczegółach wracamy do miesiąca w kalendarzu. Akcja „Odwołaj” nadal oznacza pozostawienie wpisu jako odwołanego; „Usuń” pozwala go usunąć z widoku.

Przycisk „Lista podpisów” w panelu organizatora jest aktywny także przed startem i zatwierdzeniem obecności. Podgląd podaje źródło: potwierdzone zapisy albo zatwierdzona faktyczna obecność. Przed spotkaniem pozwala pobrać i wydrukować dokument A4 do zebrania podpisów na sali. Nie wymaga zatwierdzania obecności z domu. Zmiana danych spotkania po wygenerowaniu podglądu pokazuje ostrzeżenie; pobranie zawsze pobiera aktualną listę. To ustalenie zastępuje wcześniejsze ograniczenie E7/D7 do faktycznie obecnych.

## Dodanie terminu do osobistego kalendarza (2026-11-08)

Na karcie najbliższego i wybranego spotkania, po własnej deklaracji, jest „Dodaj do kalendarza”. Dostępne administratorowi i zawodnikowi, także przed zapisem na grę. Dialog pokazuje aktualną datę, godziny i miejsce oraz wybór: Google Calendar, Outlook.com, Outlook Microsoft 365, Apple Calendar (.ics), inna aplikacja (.ics). Zapis w zewnętrznej aplikacji użytkownik zatwierdza sam. Eksport nie zmienia deklaracji.

Google i oba warianty Outlook otwierają formularz w nowej karcie. Apple/inne pobierają plik ICS do importu; dla iPhone UI podaje możliwość importu z Mail, a dla Maca otwarcia w Kalendarzu. UI wyjaśnia brak automatycznej synchronizacji późniejszych zmian/odwołań. Odwołane, usunięte, zakończone lub minione terminy nie mają przycisku. Eksport zawiera tylko tytuł, termin i miejsce; nie zawiera listy uczestników ani linku/autoryzacji Ingress.

### Eksport z listy (2026-11-09)

Każdy kwalifikujący się kafelek kalendarza ma „Dodaj do kalendarza” z tym samym wyborem aplikacji co szczegóły. Na prośbę użytkownika usunięto eksport zbiorczy: nie ma przycisku wielu spotkań, zakresu miesiąca/12 miesięcy ani generowania zbiorczego ICS. Pozostaje eksport jednego terminu.

## Wstępne boisko (2026-11-09)

Nad listą uczestników zaplanowanego spotkania jest „Wstępne drużyny”, oznaczone „Z zapisów” i informacją o niesprawdzonej obecności. Boisko korzysta z układów wariantu A, pokazuje nazwiska i średnie ELO. Przy mniej niż dwóch osobach podaje warunek pokazania boiska. Widzą je administrator i użytkownicy, także podgląd użytkownika na koncie administratora.

Własne „Potwierdzam obecność”, rezygnacja i przyjęcie oferty odświeżają boisko od razu; na innych urządzeniach odczyt odbywa się co 30 sekund oraz po powrocie do karty. Administrator ma „Według ELO”, „Losuj wstępne składy”, zamianę przez dotknięcie osoby z obu stron i przeniesienie z większej drużyny do mniejszej. Zapis jest wspólny dla ekipy; zmiana deklaracji przywraca aktualny podział ELO. Nieaktualna lista/rewizja wymaga odświeżenia zamiast nadpisania. Błąd odczytu oznacza ostatni podział, utrata odpowiedzi zapisu pozwala ponowić bez drugiego losowania.

Po zatwierdzeniu obecności podgląd znika, a krok „Drużyny” ma „Użyj wstępnego podziału”. Użycie jest jawne; zmieniona lista faktycznie obecnych jest ponownie wyrównana według ELO. Sam podgląd nie zatwierdza obecności, drużyn ani wyniku.

## Nawigacja gestem między spotkaniami — 2026-11-11

Na `/` i `/meetings/:id` przesunięcie w lewo otwiera następne spotkanie, w prawo poprzednie. Te same akcje są dostępne przyciskami z nazwami dostępnymi dla czytnika i klawiatury. Kolejność według aktualnego czasu startu i ID, jak w kalendarzu; usunięte pomijamy, odwołane pokazujemy. Brak sąsiada wyłącza przycisk. Wirtualny termin otwieramy dotychczasowym rozwiązaniem wystąpienia, bez deklaracji udziału.

Gest wymaga wyraźnego poziomego ruchu jednego palca. Pionowe przewijanie, krótki ruch, gest wielopalcowy i ruch rozpoczęty na kontrolce/formularzu/dialogu nie nawigują. Błąd odczytu sąsiednich terminów ma komunikat i ponowienie, bez usuwania bieżącego spotkania.


## Płynne przesuwanie kafelka — 2026-11-11

Użytkownik zlecił graficzne przejście między terminami: cały kafelek spotkania podąża za poziomym gestem; krótki/anulowany gest wraca do pozycji początkowej. Po zmianie obecny kafelek wyjeżdża w kierunku gestu, a nowy wjeżdża z przeciwnej strony. Przyciski korzystają z tego samego przejścia. Pobranie szczegółów poprzedza animację wyjścia; błąd zachowuje bieżący termin. Gest jest ograniczony do kafelka, z zachowaniem przewijania i wykluczeniem kontrolek. Preferencja ograniczenia ruchu wyłącza animacje.
