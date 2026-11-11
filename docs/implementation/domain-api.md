# Domena, dane i API

## Reguły wspólne

- Jedna grupa. Limit spotkania: 14 uczestników. Administrator i status priorytetu to niezależne właściwości. Status priorytetu nie jest widoczny innym zawodnikom: własny status jest dostępny w profilu, administrator widzi statusy wszystkich. Własny widok pozostaje dotychczasowym założeniem; nowa instrukcja wyklucza publiczne oznaczenia.
- Domyślny harmonogram: wtorek, 18:00–20:00, I LO w Gdańsku, `Europe/Warsaw`. Dzień tygodnia jest ustawieniem, nie ograniczeniem modelu.
- Daty zdarzeń przechowuj jako świadome strefowo chwile UTC. Reguła powtarzalności zawiera lokalną godzinę i strefę IANA. Kolejny termin wyliczaj w strefie reguły, nie przez dodawanie 168 godzin UTC.
- Granica rezygnacji i ochrony miejsc wynosi dokładnie 24 godziny przed konkretnym startem. `now < starts_at - 24h` oznacza okres wcześniejszy, `now >= starts_at - 24h` okres chroniony. Zwykła rezygnacja dokładnie na granicy nie jest późna; późna jest dopiero po granicy. Zegar serwera jest źródłem prawdy, w testach wstrzykiwany.
- „Nie będę”, rezerwa, oczekiwanie na ponowne potwierdzenie i odmowa oferty nie oznaczają nieobecności bez odwołania.
- Zapisany uczestnik jest kimś innym niż osoba faktycznie obecna. Tylko faktycznie obecni mogą wejść do oficjalnych składów i ELO. Wstępne boisko z deklaracji jest osobnym podglądem bez skutków w obecności i rankingu.

## Model danych

Poniższe nazwy są kontraktem pojęciowym; konwencję nazw kodu ustala E1. Encje mają identyfikator, daty utworzenia/aktualizacji oraz odpowiednie ograniczenia bazy.

| Encja | Kluczowe dane i ograniczenia |
| --- | --- |
| Player | publiczny identyfikator, imię i nazwisko (oddzielne pola pozwalające maskować samo nazwisko), `priority_status`: `founder/player/guest` (domyślnie `guest`), opcjonalny przydomek do rozróżniania profili, osobna rola `admin/player`, aktywny/zablokowany, hash PIN-u, unieważnienie przez rekordy Session; nazwisko nie jest kluczem unikalnym |
| Invite | hash losowego tokenu, autor, data utworzenia i unieważnienia; wielokrotne użycie; domyślnie bez wygaśnięcia |
| Session | hash losowego tokenu, gracz, utworzenie, wygaśnięcie, ostatnie użycie i unieważnienie; wiele urządzeń |
| PinResetGrant | hash tokenu jednorazowego, gracz, autor, wygaśnięcie i zużycie; administracyjne prawo resetu, nie odczyt starego PIN-u |
| ScheduleVersion | dzień tygodnia, lokalna godzina, czas trwania, strefa, miejsce, data obowiązywania; wersje bez nakładających się okresów |
| Meeting | źródłowy termin harmonogramu, aktualny start/koniec, miejsce, status, wersja terminu i wersja danych; stabilna tożsamość po przesunięciu |
| Enrollment | jeden rekord gracz/spotkanie, deklaracja, pozycja wynikająca z statusu i kolejności, czas zgłoszenia, przydział miejsca, potwierdzona wersja terminu |
| SeatOffer | spotkanie, gracz z rezerwy, autor, stan `pending/accepted/declined/expired/revoked`, daty; w pierwszej wersji ręczne zamknięcie bez automatycznego timeoutu; powiązanie z przyjętym miejscem |
| EnrollmentEvent | historia zgłoszenia, rezygnacji, przesunięcia, ponownego potwierdzenia i oferty; wartości źródłowe pozwalające wyjaśnić kolejność |
| Attendance | unikalny gracz/spotkanie, obecny/nieobecny/nieustalony, kto i kiedy zatwierdził; decyzja o obecności oddzielona od deklaracji |
| AttendanceEvent | zwykła rezygnacja/późna rezygnacja/no-show oraz korekty administratora; korekta wskazuje zdarzenie źródłowe, autora, czas, poprawioną wartość i obowiązkowy powód |
| TeamAssignment | spotkanie, gracz, strona A/B, wersja zatwierdzonego składu; gracz najwyżej w jednej drużynie; udział nie oznacza pozycji na boisku |
| ResultRevision | spotkanie, rewizja wyniku i składów, sety A/B, autor, czas, powód korekty; aktywna rewizja jednoznaczna |
| RatingEntry | spotkanie, gracz, wersja algorytmu/rewizji, punkty przed, delta i po; dotyczy zatwierdzonych faktycznych uczestników |
| AuditEvent | autor, operacja, obiekt, czas i bezpieczne metadane; bez PIN-ów, sesji i pełnych tokenów zaproszeń |

Indeksy: terminy spotkań, aktywne zapisy spotkania, kolejność zgłoszeń, otwarte oferty, historia gracza, porządek spotkań rankingowych. Unikalność generowania terminu jest oparta na jego stabilnym źródle, a nie aktualnej przesuniętej dacie. Sekwencja rozstrzyga identyczne timestampy zgłoszeń.

## Stany spotkania

Cykl rozgrywki: `scheduled → attendance_checked → teams_confirmed → completed`. `cancelled` jest osobnym zakończeniem. Zmiana terminu tworzy nową wersję terminu i stan wymagający ponownego potwierdzenia; nie tworzy nowego identyfikatora spotkania. Wycofanie zatwierdzonych składów i korekty zakończonego meczu są osobnymi operacjami z audytem, zależnymi od D5/D8.

Odwołanie pozostawia spotkanie w kalendarzu, zamyka przyjmowanie deklaracji/ofert i nie generuje no-show. Odwołania zakończonego meczu nie traktować jak zwykłego odwołania przyszłego terminu.

## Kalendarz i harmonogram

Kalendarz musi sięgać dowolnie daleko w przyszłość, ale nie tworzy nieskończonej liczby rekordów. API prezentuje wyliczone wystąpienia reguły i istniejące spotkania. Zapis na wyliczony termin rozwiązuje go do trwałego Meeting w transakcji. Żądanie zakresu może mieć ograniczony rozmiar i paginację, nigdy ograniczenie „tylko najbliższy tydzień”.

Rozwiązywanie wystąpienia weryfikuje po stronie serwera, że klucz odpowiada obowiązującemu harmonogramowi albo istniejącemu wyjątkowi. Zawodnik nie tworzy dowolnego spotkania przez przesłanie własnej daty; deklaracje dotyczą przyszłych, nieodwołanych terminów.

Zmiana harmonogramu od daty zachowuje historię. Trzeba obsłużyć zarówno istniejące przyszłe rekordy z zapisami, jak i jeszcze niewygenerowane wystąpienia. Przed zatwierdzeniem administrator widzi podgląd dotkniętych terminów. Zmiana nie pozostawia ukrytych, starych terminów ani duplikatów. Po zmianie terminu zachowujemy pierwotną kolejność zapisów (czas zgłoszenia i rozstrzygającą remisy sekwencję). Potwierdzenie udziału musi dotyczyć nowej wersji terminu; czas odpowiedzi nie ustala nowej kolejności. Zatwierdzone 2026-11-06 (D4). Dotychczasowe miejsce jest zarezerwowane do odpowiedzi, bez automatycznego terminu jej udzielenia. Administrator ręcznie decyduje o zwolnieniu miejsca przy braku potwierdzenia. Nowe zgłoszenie nie zajmuje takiej rezerwacji. Zatwierdzone 2026-11-06. Każda kolejna zmiana terminu ponownie wymaga potwierdzenia aktualnej wersji terminu, zachowując pierwotną kolejność oraz rezerwacje miejsc. Dotyczy to również osób z otwartymi propozycjami z rezerwy: akceptacja starej propozycji jest odrzucana, a przyjęcie miejsca wymaga nowej akceptacji aktualnego terminu. Poprzednie oferty i potwierdzenia pozostają w historii jako nieaktualne; rezerwacja tej samej osoby jest kontynuowana, nie liczona drugi raz. Organizator nadal ręcznie przekazuje informację na Messengerze. Zatwierdzone 2026-11-06 (D4). Testować granicę daty obowiązywania i zmianę dnia tygodnia.

## Zapisy i miejsca

Trzy statusy pierwszeństwa, od najwyższego: założyciel (`founder`), zawodnik (`player`), gość (`guest`). Nowy profil zawsze otrzymuje status gościa; status zmienia administrator. Wcześniej niż 24 h przed startem decyduje ta hierarchia, a w ramach statusu kolejność „będę”. Późniejszy zapis może przesunąć ostatnią osobę o niższym priorytecie do rezerwy: założyciel zawodnika lub gościa, zawodnik gościa. Gość nie wypiera zawodnika ani założyciela. Zatwierdzone 2026-11-06; zastępuje wcześniejszy model dwupoziomowy. Po wejściu w okres chroniony istniejące miejsca nie są odbierane z powodu priorytetu. Wolne miejsca nadal mogą zostać zajęte.

Zmiana statusu przez administratora wcześniej niż 24 h przed startem przelicza pierwszeństwo przy zachowaniu czasu pierwotnego zgłoszenia. W ostatnich 24 h zmiana statusu nie odbiera nikomu zajętego miejsca. Przeliczenie respektuje rezerwacje ofert zatwierdzone w D2 i nie resetuje kolejności zgłoszeń. Operacja jest transakcyjna i audytowana. Zatwierdzone 2026-11-06 (D3).

Rezygnacja zwalnia miejsce. Jeśli istnieje rezerwa, miejsce jest zarezerwowane dla pierwszej osoby z kolejki; nowe zgłoszenie nie może go przejąć, także zanim organizator wyśle propozycję. Organizator ręcznie kontaktuje się przez Messenger i decyduje, kiedy przekazać propozycję następnej osobie. W pierwszej wersji brak automatycznego timeoutu odpowiedzi. Przejście z rezerwy wymaga przyjęcia oferty; nie przekształcać oczekującego automatycznie w uczestnika. W modelu rozróżnić przydzielone miejsce, rezerwację przed wysłaniem propozycji i aktywną ofertę; przekazanie nie może utworzyć dwóch rezerwacji tego samego miejsca. Suma przydziałów, rezerwacji dla rezerwy/ofert oraz miejsc oczekujących na ponowne potwierdzenie po zmianie terminu nie może przekraczać 14; to samo miejsce liczone jest tylko raz. Zatwierdzone 2026-11-06. Po odmowie albo ręcznym zakończeniu propozycji z powodu braku odpowiedzi zgłoszenie tej osoby na dany termin zostaje wycofane, bez oznaczenia nieobecności lub późnej rezygnacji. Może zgłosić się ponownie, z nowym czasem i sekwencją zgłoszenia; status nadal określa poziom priorytetu. Przy kilku wolnych miejscach rezerwacje otrzymują kolejne różne osoby z rezerwy, każda na jedno miejsce; jedna osoba nie może otrzymać dwóch równoległych rezerwacji. Zatwierdzone 2026-11-06 (D2).

### Transakcja zmiany zapisu

1. Odczytaj i zablokuj wiersz Meeting (`SELECT FOR UPDATE`). Wszystkie operacje konkurujące o miejsca korzystają z tej samej blokady.
2. Sprawdź uprawnienia, stan spotkania, blokadę profilu, wersję terminu i zegar.
3. Zapisz deklarację/ofertę oraz oblicz przydziały według zatwierdzonej polityki.
4. Zapisz zdarzenia historii i wersję spotkania, zatwierdź wszystko razem.
5. Zwróć aktualny stan własnej deklaracji, listy i rezerwy. Powtórzenie tej samej operacji nie zmienia kolejności ani nie tworzy kolejnego wpisu historii.

Akceptacja oferty weryfikuje tożsamość adresata, ważność oferty, wersję terminu i dostępność rezerwacji. Stary ekran nie może przyjąć cofniętej oferty. Zmiana terminu unieważnia odniesienia do poprzedniej wersji; użytkownik dostaje konflikt i nowy stan.

## Rezygnacje i obecność

Zwykła rezygnacja, późna rezygnacja i nieobecność bez odwołania są rozróżnione w prywatnej historii. Bez automatycznych kar.

Wyjątek: przyjęcie oferty z rezerwy w ostatnich 24 h pozwala później zgłosić rezygnację bez etykiety późnej rezygnacji. Eligibility wynika z serwerowego zdarzenia przyjęcia oferty; zwykły późny zapis nie daje tego wyjątku. Wyjątek nie obejmuje nieobecności bez odwołania.

No-show powstaje po świadomym zatwierdzeniu obecności przez administratora, nie z samego minięcia czasu startu. Kandydatem jest osoba z potwierdzonym miejscem, która nie zrezygnowała i została oznaczona jako nieobecna. Ponowienie zatwierdzenia nie tworzy duplikatów. Odwołane spotkania zawsze wykluczone. Administrator może poprawić błędne oznaczenie obecności, podając obowiązkowy powód. Pierwotny wpis pozostaje w historii; korekta wskazuje autora, czas i zdarzenie źródłowe, a bieżący stan uwzględnia poprawkę. Zarówno pierwotny wpis, jak i korekta z powodem są dostępne tylko administratorowi i danemu zawodnikowi. Zatwierdzone 2026-11-06 (D5). Spóźnionego administrator oznacza jako obecnego, bez osobnej kary za spóźnienie. Gdy wcześniej zatwierdzono nieobecność, poprawka korzysta z mechanizmu korekt z powodem. Administrator może dopisać osobę bez wcześniejszej deklaracji wyłącznie z istniejącego, niezablokowanego profilu, gdy jest wolne, niezarezerwowane miejsce i łączny limit 14 nie zostanie przekroczony. Operacja nie omija rezerwacji i jest audytowana. Usprawiedliwienie zapisuje się jako korektę z powodem, zachowując zdarzenie źródłowe; nie jest automatycznym kasowaniem historii. Zatwierdzone 2026-11-06 (D5). Korekta historii nie zmienia ukrycie zatwierdzonych składów, wyniku ani ELO; ich korekty podlegają osobnym operacjom i D8.

## Drużyny i ELO

Losowanie oficjalnych drużyn działa na rzeczywiście obecnych. Tryb wyrównany minimalizuje różnicę średnich ELO przy różnicy liczebności najwyżej 1 i maksymalnie 7 na stronę. Przy 14 osobach można deterministycznie przejrzeć kombinacje z usunięciem symetrii A/B. Ustalić jawny tie-break w kodzie. Administrator może zmienić składy; każda osoba dokładnie raz, nikt nieobecny nie może zostać dodany ukrytą zmianą UI.

Schemat boiska pokazuje sześć osób i ewentualną siódmą do rotacji. Nie zapisujemy czasu gry, pozycji ani zmian w setach. Cały zatwierdzony skład otrzymuje zmianę rankingową.

Założenia potwierdzone: start 1000, siła drużyny jako średnia punktów przed meczem, jedna aktualizacja po spotkaniu, wynik w setach. Proporcja setów zamiast liczby rozegranych setów; remis z silniejszą drużyną może zwiększyć punkty.

Skala K = 32 zatwierdzona 2026-11-06 (D8). Dla równorzędnych drużyn każdy zawodnik otrzymuje: 5:0 → +16/−16; 3:2 → +3,2/−3,2; 3:3 → 0/0. Zmiana przy nierównych drużynach uwzględnia ich siłę.

Wzór implementacyjny D8: K=32, skala oczekiwań 400 i polityka precyzji zatwierdzone 2026-11-06/07:

```text
EA = 1 / (1 + 10 ** ((meanB - meanA) / 400))
SA = setsA / (setsA + setsB)
K = 32
deltaA = K * (SA - EA)
deltaB = -deltaA
```

Wszyscy w A otrzymują deltaA, wszyscy w B deltaB. Przy nierównej liczebności nie wymuszać zerowej sumy punktów wszystkich graczy kosztem zmiany reguły równych delt w drużynie. K wynosi 32. W obliczeniach i trwałym zapisie zachowujemy dokładne wartości, bez zaokrąglania punktów po każdym meczu; UI pokazuje punkty i delty do jednego miejsca po przecinku. Średnie i oczekiwania korzystają z wartości obliczeniowych, nie prezentacyjnych. Zatwierdzone 2026-11-06. Reprezentację numeryczną i tolerancję porównań ustalić w E8. Skala oczekiwań 400 zatwierdzona 2026-11-07.

Wynik 0:0 zamyka spotkanie z oznaczeniem „bez rozegranych setów”, bez aktualizacji ELO i bez dzielenia przez zero. Obecność pozostaje zapisana; nie utożsamiać takiego zamknięcia z odwołaniem spotkania. Zatwierdzone 2026-11-06. Model Meeting rozróżnia rozegrany mecz od zakończenia bez setów. Rozegrany wynik zapisuj atomowo z RatingEntry, aktywną rewizją i statusem meczu. Ponowienie nie aktualizuje rankingu drugi raz.

Administrator może skorygować wynik z obowiązkowym powodem. Poprzedni wynik pozostaje w historii wraz z autorem i czasem korekty. Po korekcie przelicz ranking również dla późniejszych spotkań, ponieważ zmieniły się ich punkty wejściowe. Zatwierdzone 2026-11-06 (D8). Przeliczenie używa stabilnej kolejności spotkań i ich zatwierdzonych snapshotów składów. Operacja blokuje konkurujące zapisy wyników; ranking i dziennik zmian publikowane są atomowo, bez pokazywania połowy przeliczenia. Korekta z 0:0 na rozegrany wynik lub odwrotnie również wymaga spójnego przeliczenia. 2026-11-07 zatwierdzono pełne korekty historycznej obecności i składów z powodem oraz kolejność według chwili rozpoczęcia i stałego ID spotkania.

## Lista podpisów dla szkoły

Administrator może wygenerować PDF przed spotkaniem z aktualnych potwierdzonych zapisów, aby wydrukować go przed wyjściem z domu. Po zatwierdzeniu faktycznej obecności źródłem są osoby oznaczone jako obecne. Rezerwa i oczekujące rezerwacje nie trafiają do PDF. Po zmianie zapisów lub obecności można pobrać nowy dokument. D7 zaktualizowane na polecenie użytkownika 2026-11-08.

Dokument: data spotkania, I LO w Gdańsku, tabela z numerem porządkowym, pełnym imieniem i nazwiskiem oraz pustym miejscem na podpis. Bez przydomków, statusów, ELO i prywatnej historii. Układ A4 jest techniczną bazą projektu wydruku. Eksport nie zmienia obecności, nie zatwierdza meczu i nie aktualizuje rankingu.

## Dostęp i sesje

Rejestracja przez stały losowy link wielokrotnego użytku, bez akceptacji administratora. Nowy profil ma status gościa (`guest`) i żadnych uprawnień administracyjnych. Serwer nadaje ten status niezależnie od pól przesłanych przez klienta; rejestracja nie pozwala samodzielnie wybrać wyższego priorytetu. Zaproszenie można unieważnić; istniejący użytkownik nie potrzebuje linku do logowania.

PIN dokładnie sześć cyfr, hashowany algorytmem do haseł, np. Argon2id z losową solą. Po 5 błędnych PIN-ach dla profilu w oknie 15 minut następne próby są odrzucane do końca okna (HTTP 429, Retry-After); brak trwałej blokady konta. Dodatkowo limit 30 nieudanych PIN-ów na źródło/15 minut. Liczniki w PostgreSQL przetrwają restart. Parametry sesji/resetu/limitu profilu zatwierdzone 2026-11-06. Nie używać PIN-u jako tokenu sesji. Reset przyznaje administrator przez jednorazowy grant ważny 30 minut; szczegóły UI bez dodatkowej automatycznej wysyłki wiadomości.

Sesja zapamiętuje profil na urządzeniu. Losowy token w `HttpOnly`, `Secure` cookie z określonym terminem i kontrolowanym odnawianiem; w DB hash tokenu. Sesja wygasa po 30 dniach bez korzystania, najpóźniej po 180 dniach od jej utworzenia (zatwierdzone 2026-11-06). Każde autoryzowane żądanie odnawia okres bezczynności do twardej granicy. Zmiana/reset PIN-u unieważnia wszystkie wcześniejsze sesje i tworzy nową na bieżącym urządzeniu; odblokowanie profilu nie przywraca starych sesji. Mutacje chronione przed CSRF, z walidacją Origin i odpowiednim SameSite. Zweryfikować zachowanie cookies w iframe Ingress; jeżeli wymaga innego SameSite, dopasować ochronę CSRF i udokumentować. Tokeny nie trafiają do localStorage.

Blokada profilu unieważnia wszystkie sesje i uniemożliwia ponowne logowanie. Zwalnia przyszłe miejsca, pozycje w rezerwie i rezerwacje po zmianie terminu oraz zamyka otwarte oferty tego zawodnika. Zwolnione miejsca podlegają standardowej obsłudze rezerwy D2; nie oznacza to automatycznego przyjęcia kolejnej osoby. Zmianę zapisać jako zdarzenie administracyjne, bez kasowania wcześniejszych deklaracji i historii. Dotychczasowe spotkania, obecności, składy, wyniki i ELO pozostają zachowane. Zatwierdzone 2026-11-06 (D6). Operacja musi być odporna na równoczesne przyjęcie oferty lub zgłoszenie zawodnika, z unieważnieniem sesji i rozliczeniem zwalnianych rezerwacji. Zmiana/reset PIN-u unieważnia pozostałe sesje. Przy identycznych imionach i nazwiskach rozróżniać profile dodatkowym przydomkiem, np. „Michał Nowak — Misiek”. Przydomek nie zastępuje imienia i nazwiska, a lista podpisów dla szkoły zawiera wyłącznie imię i nazwisko. Zatwierdzone 2026-11-06 (D6). Unikalnym identyfikatorem logowania pozostaje ID profilu, a nie napis z nazwiskiem/przydomkiem. Zawodnik sam ustawia i zmienia własny przydomek w profilu przez `PATCH /me`; zmiana nie zmienia ID konta, imienia/nazwiska, statusu ani historii. Zatwierdzone 2026-11-06. Katalog logowania jest dostępny przed uwierzytelnieniem i pokazuje listę profili: imię, pierwszą i ostatnią literę nazwiska, a pomiędzy nimi zawsze dokładnie pięć gwiazdek, niezależnie od długości nazwiska (np. `Michał N*****k`). Opcjonalny przydomek pomaga odróżnić podobne wpisy. Użytkownik wybiera istniejący profil i podaje swój sześciocyfrowy PIN. Zatwierdzone 2026-11-06 (D6). Rejestracja przez zaproszenie tworzy profil, nie wybiera istniejącego. Prywatne zdarzenia nigdy nie są zwracane z publiczną listą uczestników.

## Proponowany kontrakt HTTP

Prefiks `/api/v1`. Backend utrzymuje OpenAPI. Identyfikatory UUID, daty ISO 8601 ze strefą. Publiczne DTO gracza zawiera jedynie potrzebne imię/nazwisko, identyfikator i ewentualny przydomek do rozróżnienia profili. Eksport szkolny pomija przydomek. Status priorytetu trafia wyłącznie do własnego DTO `/me` oraz DTO dla administratora. Listy uczestników, rezerwa, ranking, wyniki i katalog logowania nie ujawniają statusu ani odpowiedników typu `founder`, `priority` czy opisu zmiany identyfikującego cudzy status. Prywatne DTO oddzielne; ukrycie etykiety CSS nie stanowi ochrony danych.

W tym dokumencie „publiczne” oznacza widoczne dla zalogowanej grupy. Kalendarz, uczestnicy, wyniki i ranking wymagają sesji. Anonimowo dostępne są wyłącznie niezbędne operacje wejścia/rejestracji/resetu i ograniczone health; katalog profili przed logowaniem zwraca wyłącznie dedykowaną projekcję z maskowaniem według D6. Samo posiadanie URL spotkania nie udostępnia jego danych.

| Obszar | Endpointy i znaczenie |
| --- | --- |
| Dostęp | `POST /auth/register`, `/auth/login`, `/auth/logout`; `GET /auth/profiles` z DTO `{profile_id, first_name, masked_last_name, nickname?}` według D6; `GET /me`; `PATCH /me`; `POST /me/pin` |
| Reset | `POST /admin/players/{id}/pin-reset` tworzy grant; `POST /auth/reset-pin` zużywa grant |
| Zaproszenia | `POST /admin/invites`, `GET /admin/invites`, `POST /admin/invites/{id}/revoke` |
| Profile | `GET /admin/players`; `PATCH /admin/players/{id}` dla roli priorytetu i blokady zgodnie z D3/D6 |
| Terminy | `GET /calendar?from=&to=`; `POST /meetings/resolve` dla klucza wystąpienia; `GET /meetings/next`; `GET /meetings/{id}` |
| Zapisy | `PUT /meetings/{id}/my-declaration` z `going/not-going`; `DELETE /meetings/{id}/my-declaration` jako wycofanie; żądanie zawiera wersję terminu |
| Oferty | `POST /admin/meetings/{id}/offers`; `POST /admin/offers/{id}/close`; `POST /offers/{id}/accept`, `/decline` |
| Harmonogram | `GET /schedule`; `POST /admin/schedule/preview`; `POST /admin/schedule/versions`; `POST /admin/meetings/{id}/reschedule`, `/cancel` |
| Obecność | `PUT /admin/meetings/{id}/attendance`; `POST /admin/meetings/{id}/attendance/confirm`; `POST /admin/meetings/{id}/attendance/corrections` z graczem/zdarzeniem, poprawioną wartością, powodem i oczekiwaną wersją; `GET /me/attendance-history` |
| Drużyny | `POST /admin/meetings/{id}/teams/generate` z trybem; `PUT /admin/meetings/{id}/teams`; `POST /admin/meetings/{id}/teams/confirm` |
| Wynik | `PUT /admin/meetings/{id}/result`; korekta osobnym endpointem po D8 z powodem i oczekiwaną wersją |
| Ranking | `GET /ranking`; `GET /results` z paginacją; `GET /results/{id}` z zatwierdzonym składem i zmianami ELO |
| Dokument | `GET /admin/meetings/{id}/signature-list` zwraca PDF potwierdzonych zapisów przed zatwierdzeniem obecności, później faktycznie obecnych (D7) |
| Stan usług | `/health/live`, `/health/ready`; bez sekretów i szczegółów infrastruktury |

Katalog `/auth/profiles` nie używa DTO gracza dostępnego dla zalogowanej grupy. Nazwisko maskuje backend; pełne nazwisko nie trafia do JSON, HTML, atrybutów, etykiet dostępności ani ukrytych pól listy logowania. Profile zablokowane nie są oferowane do logowania. Obsłużyć polskie znaki i nazwiska jedno-/dwuliterowe bez błędu indeksowania; maskowanie dotyczy znaków, nie bajtów. Maskowana etykieta nie jest unikalnym kluczem: logowanie przesyła ID wybranego profilu i PIN.

Mutacje administracyjne wymagają backendowej roli administratora. Profile historyczne zachowują identyfikatory także po blokadzie. Kolekcje mają paginację; zakres kalendarza ma walidowany limit rozmiaru.

Błędy: `401` brak/wygaśnięcie sesji, `403` brak uprawnienia, `404` brak obiektu, `409` konflikt stanu/wersji, `422` walidacja, `429` próby logowania. Format: `{code, message, field_errors?, current_version?}`. Frontend używa stabilnego `code`, nie parsuje komunikatu. Konflikt nigdy nie zostaje udawanym sukcesem optymistycznego UI.

Operacje narażone na ponowienie mają idempotentne znaczenie lub `Idempotency-Key` z ograniczeniem unikalności w DB. Klucz jest związany z użytkownikiem, operacją i treścią żądania. Wersjonowanie edycji chroni składy, harmonogram, wyniki i obecność przed cichym nadpisaniem przez drugą kartę.

## Szczegóły realizacji E2

Pierwszego administratora tworzy jednorazowy bootstrap, dostępny wyłącznie po wygenerowaniu 30-minutowego linku komendą operatora `npm run auth:bootstrap`. Po utworzeniu administratora bootstrap zamyka się trwale. Administrator sam wybiera PIN, bez hasła domyślnego. Kanoniczne linki używają fragmentu URL: `/setup#token`, `/join#token`, `/reset-pin#token`, dzięki czemu token nie jest wysyłany w adresie żądania HTTP ani standardowym nagłówku Referer. Token jest przesyłany w treści chronionej mutacji. W bazie przechowujemy wyłącznie hashe tokenów, a PIN jako Argon2id z indywidualną solą.

`GET /auth/csrf` wydaje podpisany token związany z sesją. Każda mutacja (także logowanie/rejestracja/reset) wymaga poprawnego Origin, cookie CSRF i identycznego nagłówka X-CSRF-Token. Domyślne cookies Secure, SameSite=Lax; cookie sesji dodatkowo HttpOnly. Odstępstwo od Secure dozwolone wyłącznie dla localhost w development. Wszystkie odpowiedzi API no-store, Referrer-Policy=no-referrer. Odczyt surowego linku zaproszenia/resetu jest możliwy tylko przy jego utworzeniu, późniejsza lista zawiera metadane.

E2 dostarcza blokadę dostępu, sesji i grantów. Zwalnianie przyszłych zapisów/rezerwacji/ofert przy blokadzie musi zostać dodane w E4 po powstaniu tych modeli. Zmiana statusu przez administratora również jest zakresem E4, ze wspólną transakcją przeliczającą miejsca według D3; E2 odrzuca payload zmieniający status. Nie można zablokować jedynego administratora. To ograniczenie etapów nie zmienia docelowych reguł D3/D6.

## Szczegóły realizacji E3

`ScheduleVersion` ma przedział lokalnych dat `[effective_from, effective_until)` i numer dnia tygodnia od 0 (poniedziałek) do 6 (niedziela). PostgreSQL wyklucza nakładanie się przedziałów. Domyślna reguła działa od 1970-01-01; nie tworzy to historii spotkań. Minione terminy w kalendarzu pochodzą wyłącznie z utrwalonych rekordów, bez tworzenia pozornej historii z samej reguły.

Identyfikator wystąpienia to UUIDv5 z wersji harmonogramu i daty źródłowej. Meeting zachowuje te pola oraz ID po zmianie rzeczywistego startu. GET kalendarza niczego nie tworzy; scalenie tłumi termin pierwotny także wtedy, gdy przesunięte spotkanie trafiło poza żądany miesiąc. `POST /meetings/resolve` przyjmuje `{schedule_version_id, source_date}` i idempotentnie utrwala poprawny przyszły lub trwający termin. Nie zapisuje uczestnictwa; zakończonego wystąpienia nie tworzy, ale istniejący rekord zwraca również historycznie. Deklaracje E4 muszą samodzielnie walidować przyszły start, odwołanie i wersję terminu.

Zakres `/calendar` jest półotwarty (`from` włącznie, `to` wyłącznie), daty w Europe/Warsaw, od 1 do 366 dni na żądanie; paginacja `limit/offset`, odpowiedź `items/total/next_offset`. Nie ma limitu tygodnia ani najbliższego roku. `/meetings/next` uwzględnia trwającą grę i pomija rekordy odwołane/zakończone; brak terminu daje null. `/players` udostępnia zalogowanej grupie paginowane DTO wyłącznie z ID, imieniem, nazwiskiem i przydomkiem. Publiczne w sensie grupy nie oznacza anonimowego dostępu.

Czas trwania jest rzeczywistą liczbą minut od startu w UTC. Generator odrzuca nieistniejącą lub niejednoznaczną lokalną godzinę początku (np. niedziela 02:30 w dniu zmiany czasu); reguła wtorek 18:00 jest jednoznaczna. Przed dopuszczeniem takich godzin przy zmianie harmonogramu E5 potrzebna jest jawna polityka DST i walidacja. Pozostałe przejścia DST utrzymują lokalną 18:00, zmieniając właściwy offset UTC. [Raport E3](e3-report.md) opisuje dowody i przekazanie do E4.

## Szczegóły realizacji E4

D2/D3/D6 w zakresie zapisów zrealizowano w E4. Rezerwacja miejsca istnieje przed kontaktem organizatora jako Enrollment `allocation=reserved`, `reservation_kind=offer` i SeatOffer `state=reserved`. Po ręcznej aktywacji propozycji stan oferty to `pending`; wyłącznie jawne przyjęcie daje `seat`. Rezerwacje są chronione także przed granicą 24 godzin. Odmowa i ręczne zamknięcie `no-response` wycofują zgłoszenie, a ponowny zapis dostaje nowy czas i sekwencję. Przyjęcie oferty nie uruchamia ponownego wypierania; rezygnacja uzupełnia wakaty z zachowaniem innych miejsc. Nowe zgłoszenie i zmiana statusu przed granicą przeliczają pierwszeństwo z ochroną rezerwacji.

PUT/DELETE deklaracji wymagają Idempotency-Key (UUID) i wersji terminu. Osobna tabela receiptów zapobiega ponownemu zastosowaniu dawnego żądania nawet po późniejszej rezygnacji. Inna treść z tym samym kluczem daje konflikt; odpowiedź na retry pokazuje stan aktualny. Historia domenowa nie jest dublowana. Równoczesne mutacje korzystają z tej samej blokady Meeting, a zegar jest odczytywany dopiero po jej uzyskaniu. To zapobiega wykorzystaniu nieaktualnego czasu po oczekiwaniu w kolejce do DB.

Własny odczyt `/meetings/{id}/my-participation` jest oddzielony od publicznego dla grupy DTO. Prywatnie pokazuje klasyfikację rezygnacji i własną propozycję; publicznie dostępne są wyłącznie listy i liczniki miejsc. Rzeczywiście późna rezygnacja wymaga `acknowledge_late=true`; serwer wylicza ją ponownie. Klasyfikacja oraz wyjątek późnej oferty trafiają do EnrollmentEvent jako źródło historii E6, bez automatycznej kary.

Administracyjna zmiana statusu i blokada aktualizują zapisy przyszłych spotkań w tej samej transakcji. Blokada nie usuwa przeszłych deklaracji ani zdarzeń i nie przywraca ich po odblokowaniu. Role administratora są niezależne od statusu. E5 uzupełni proces ponownego potwierdzenia terminu; pole `reservation_kind=reconfirmation` nie oznacza jeszcze wdrożenia tego etapu. Kontrakt, scenariusze i ograniczenia: [raport E4](e4-report.md).

## Szczegóły realizacji E5

Użytkownik zatwierdził 2026-11-06: przesunięcia stałej reguły w tym samym tygodniu poniedziałek–niedziela, zachowanie odwołań oraz indywidualnych wyjątków bez przesuwania. Podgląd oznacza wyjątki osobno. Nowa reguła zastępuje zaplanowane reguły od wskazanej daty; zastąpione wersje pozostają jako superseded, bez usuwania powiązanej historii. Konflikt, kolizja lub przesunięcie przed początek zakresu blokują zatwierdzenie zamiast scalać dane.

Meeting zachowuje ID i oryginalne źródło. `calendar_schedule_id/calendar_source_date` identyfikują aktualnie zastępowany slot nowej reguły, dzięki czemu ten sam termin nie pojawia się drugi raz wirtualnie. Resolver rozpoznaje oba klucze. Podgląd jest ponownie liczony przy zapisie i porównywany tokenem obejmującym wersje spotkań/reguł oraz żądaną zmianę. Blokada ScheduleState koordynuje materializację, odczyt kalendarza i zbiorcze mutacje.

Przy każdej rzeczywistej zmianie term_version rośnie. Poprzednie daty oraz trwała MeetingTermRevision zachowują ślad zmiany. Wszystkie zgłoszenia going wymagają nowego potwierdzenia: dotychczasowe miejsca przechodzą do reserved/reconfirmation, rezerwa zachowuje kolejność, aktywne stare oferty są unieważniane i mają nowe chronione rezerwacje w aktualnej wersji terminu. Potwierdzenie nie resetuje declared_at ani queue_number; przyjęcie oferty nadal wymaga nowej propozycji i akceptacji aktualnej daty. Brak timeoutu, ręczne zwolnienie przez administratora. Każda kolejna zmiana ponawia ten proces.

Odwołanie przyszłego spotkania zachowuje deklaracje i historię, zeruje alokacje, zamyka aktywne oferty i pozostawia cancelled w kalendarzu. Nie generuje ani no-show, ani późnej rezygnacji. Zakończone lub rozpoczęte spotkania nie podlegają tej operacji. Źródłem nowego potwierdzenia jest zawsze aktualna term_version, nie dawne zgłoszenie lub dawne ID oferty.

Nieistniejące/niejednoznaczne godziny DST są odrzucane przy konfiguracji, bez nieuzgodnionego przesuwania w tle. Zbiorcza zmiana sprawdza także kolizje z wyliczonymi, niewytworzonymi jeszcze slotami. Szczegółowy kontrakt, granice i dowody: [raport E5](e5-report.md).

## Implementacja obsługi sali E6

Zatwierdzone 2026-11-06: podział działa dla 2–14 faktycznie obecnych osób, różnica liczebności najwyżej 1, maksymalnie 7 w drużynie. Mniej niż 2 osoby blokują podział. Ponowne otwarcie zatwierdzonych składów przed wynikiem wymaga powodu. Korekty składów zakończonego spotkania zależą od E8.

Szkic obecności można przygotować wcześniej, ale zatwierdzić go dopiero od rozpoczęcia spotkania. Nieustalone osoby blokują zatwierdzenie. Źródłem kandydatów są miejsca potwierdzone dla aktualnej wersji terminu; wycofane deklaracje i niepotwierdzone rezerwacje nie są nieobecnością bez odwołania. Zmiana terminu lub odwołanie usuwa niezatwierdzony szkic obecności. Rezygnacja przed zatwierdzeniem usuwa osobę z bieżącego szkicu.

Zatwierdzenie zapisuje obecność i prywatne źródłowe zdarzenia atomowo. Zwalnia przydziały nieobecnych i rezerwuje miejsca dla kolejnych osób z rezerwy. Nieobecny zachowuje deklarację i historię, ale nie uczestniczy w ponownym przydziale miejsc. Organizator może potwierdzić na sali fizycznie obecnego adresata jego własnej rezerwacji (również oczekującego na ponowne potwierdzenie terminu) albo ręcznie zwolnić rezerwację i przekazać ją następnej osobie bez oznaczenia nieobecności. Dopisanie innego aktywnego profilu wymaga wolnego niezarezerwowanego miejsca. Osoba wcześniej oznaczona jako nieobecna wraca wyłącznie korektą z powodem i pod warunkiem dostępności miejsca. Nie wolno przejąć cudzej rezerwacji. Zasada zwalniania miejsc oraz potwierdzania na sali zatwierdzona przez użytkownika 2026-11-06.

`AttendanceEvent` przechowuje źródłowy wpis obecności, nieobecności albo rezygnacji. Kolejne korekty wskazują ten sam źródłowy wpis i nie nadpisują go. Bieżąca klasyfikacja wynika z ostatniej korekty według sekwencji. Korekta faktycznej obecności aktualizuje `Attendance`, alokację miejsca i rewizję obecności. Jeśli istnieje szkic drużyn, zostaje zarchiwizowany i wymaga nowego podziału. Przy zatwierdzonych składach najpierw trzeba jawnie je otworzyć; po zapisaniu wyniku fizyczna obecność jest zamknięta do zasad E8. Sama zmiana klasyfikacji nieobecności na usprawiedliwioną nie zmienia składu.

`TeamSheet` to wersjonowany szkic/zatwierdzony skład/archiwum, z rewizją obecności, której dotyczy. `TeamMember` zapisuje jedno członkostwo gracza w tym składzie, stronę, kolejność prezentacji i snapshot punktów. Kolejność prezentacji nie oznacza rzeczywistej pozycji ani czasu gry. Aktywny skład jest najwyżej jeden; archiwalnego nie nadpisujemy. Korekta szkicu przekazuje pełne listy A/B i musi zawierać każdego obecnego dokładnie raz. Przy 7:7 wykonywana jest zamiana dwóch osób, bez przejściowego zapisywania ósmej osoby w drużynie.

Generator losowy używa systemowego źródła losowości (w testach wstrzykiwanego). Wyrównany przegląda kombinacje, minimalizuje bezwzględną różnicę średnich, usuwa symetrię przy równych liczebnościach i rozstrzyga remis leksykograficznie po ID zawodników. W E6 wszyscy mają rzeczywistą bazę 1000; pobieranie przeliczonych rankingów będzie podłączone w E8. Siódma osoba jest prezentowana w rotacji. Publiczny dla zalogowanej grupy odczyt zwraca wyłącznie zatwierdzony skład, nigdy szkic ani prywatną historię.

Endpointy E6 (prefiks `/api/v1`):

- `GET/PUT /admin/meetings/{id}/attendance`, `POST .../attendance/confirm` — odczyt, zapis szkicu i zatwierdzenie.
- `POST .../attendance/admit`, `POST .../attendance/release-reservation`, `POST .../attendance/corrections` — obsługa sali i korekty.
- `GET /me/attendance-history` oraz `GET /admin/players/{id}/attendance-history` — prywatna historia z paginacją po wpisach źródłowych (`limit` 1–50, `offset` ≥0), wraz z korektami i autorami.
- `GET /admin/meetings/{id}/teams`, `POST .../teams/generate`, `PUT .../teams`, `POST .../teams/confirm`, `POST .../teams/reopen` — obsługa składów.
- `GET /meetings/{id}/teams` — zatwierdzone drużyny albo `null`, dostępne zalogowanym zawodnikom.

Każda mutacja E6 wymaga administratora, CSRF, `expected_version` spotkania i UUID w `Idempotency-Key`. Jedna blokada wiersza Meeting obejmuje obecność, miejsca, historię, skład i potwierdzenie operacji. Ponowienie identycznej operacji z tym samym kluczem zwraca bieżący stan bez ponownego skutku. Inny payload pod tym samym kluczem albo stara wersja dla nowej operacji daje 409. Zapis obecności/składów oraz ich publikacja są atomowe. Migracja E6 przenosi wcześniejsze klasyfikowane rezygnacje z EnrollmentEvent do prywatnej historii bez zmiany źródłowych dat i autorów.

## Lista podpisów — implementacja E7

`GET /api/v1/admin/meetings/{id}/signature-list` zwraca `application/pdf`. Domyślnie `Content-Disposition: inline`; opcjonalne `?download=true` ustawia `attachment` i nazwę `lista-podpisow-YYYY-MM-DD.pdf`, z datą spotkania w jego strefie. Odczyt wymaga sesji i rzeczywistej roli administratora. Brak lub usunięcie obiektu daje 404, odwołanie — 409. Przed zatwierdzeniem obecności drukujemy potwierdzone miejsca; lista rezerwowa nie jest eksportowana.

Po zatwierdzeniu obecności źródłem są rekordy `Attendance.confirmed_state=present`, również dla historycznego profilu zablokowanego po spotkaniu. Wcześniej źródłem są aktywne potwierdzone miejsca `Enrollment` dla aktualnej wersji terminu. Jedna blokada Meeting, wspólna z korektami i dopisywaniem, pozwala pobrać spójną rewizję obecności i jej nazwiska. Następnie blokada jest zwalniana, a PDF powstaje w puli wątków z niezmiennego snapshotu. Odczyt nie zmienia obecności, wersji spotkania, drużyn ani rankingu. Każde nowe żądanie pobiera aktualny stan. Nagłówek `X-Attendance-Revision` identyfikuje rewizję dokumentu, a `Cache-Control: no-store` wyklucza cache HTTP.

PDF zawiera datę i godziny lokalne spotkania, I LO w Gdańsku, liczbę osób na liście oraz tabelę: Lp., imię i nazwisko, podpis. Kolejność według nazwiska, imienia i ID, bez ujawniania ID na wydruku. Nie zawiera przydomków, statusów, punktów ani historii/korekt. Puste miejsca na podpis są przeznaczone do podpisu odręcznego; nie jest to formularz elektronicznego podpisu.

Format A4, font Noto Sans osadzony w pliku, odstęp wierszy co najmniej 14 mm. Zwykła lista 14 osób, również z długim polskim nazwiskiem, mieści się na jednej stronie. Dla skrajnych, wielowierszowych nazw dozwolonych przez limit profilu tabela przechodzi na kolejną stronę A4, powtarza nagłówek i nie ucina nazwisk ani wierszy. Brak obecnych daje jawny komunikat i zero pozycji. Fonty z licencją OFL są dostarczane z backendem; generowanie nie łączy się z zewnętrznym serwisem i nie tworzy trwałego archiwum dokumentów.


## Wyniki i ranking — E8

Algorytm `elo-sets-v1` używa K=32, skali oczekiwań 400, bazy 1000 i proporcji setów. Wszystkie obliczenia, średnie i dodawanie delty działają na Decimal w lokalnym kontekście 50 cyfr znaczących. Zapis PostgreSQL Numeric nie narzuca skali dziesiętnej; nie kwantyzujemy wyniku do wartości prezentacyjnej po meczu. Potęga i dzielenie mają skończoną precyzję obliczeniową 50 cyfr; nie deklarujemy symbolicznej/arbitralnie nieskończonej dokładności. Identyczny replay daje identyczne wartości zapisane; testy porównują je dokładnie, a porównania z niezależnie zaokrąglonymi wzorcami dopuszczają tolerancję 1e-40. Publiczne JSON używa ciągów dziesiętnych, frontend pokazuje punkty i delty do jednego miejsca.

Kolejność to `(Meeting.starts_at, Meeting.id)`, rosnąco. Dopisanie starszego wyniku i każda korekta przeliczają historię w tym samym porządku. Podział drużyn korzysta z bieżących przeliczonych punktów; zapisany skład jest snapshotem członkostwa i nie jest ponownie losowany podczas replay. Każdy uczestnik strony otrzymuje tę samą deltę, również siódmy rotujący. Różna liczebność stron nie wymusza sumy zerowej dla całej grupy. Przykładowo przy równych średnich 5:0 daje ±16, 3:2 i 6:4 ±3,2, 3:3 daje 0. Przy 1000 kontra 1200 słabsi dostają za remis +8,3; silniejsi przy zwycięstwie 3:2 tracą 5,1.

`ResultRevision` przechowuje niezmienną wersję setów, autora, czas, algorytm i odwołanie do wersji TeamSheet. Poprzednia wersja pozostaje w bazie, a aktywna jest najwyżej jedna na spotkanie. `RatingState` wersjonuje publikowany ranking i jest blokowany przed zapisem Meeting. `RatingEntry` (punkty przed/delta/po), `RatingCalculation` (średnie/oczekiwanie/proporcja/delty) oraz `PlayerRating` są materializacją aktualnego replay z niezmiennych wejść, wymienianą atomowo w tej samej transakcji. Zmiana rewizji nie dodaje drugi raz punktów do obecnego stanu.

Wynik wymaga zatwierdzonych aktualnych składów. Sety są nieujemnymi liczbami całkowitymi; bool i ułamki są odrzucane. Techniczny zakres odpowiada dodatniemu PostgreSQL integer. 0:0 zamyka spotkanie z `state=no_sets`, zachowuje obecność i składy, nie tworzy RatingEntry ani nie zwiększa liczby spotkań rankingowych. W historii wyników pozostaje widoczne. Zmiana do/z 0:0 również przelicza późniejsze mecze. Remis z rozegranymi setami jest spotkaniem rankingowym, nawet gdy delta wynosi zero.

Podgląd przed zapisem pokazuje faktyczne punkty wejściowe dla miejsca meczu w historii, oczekiwania i delty, a nie po prostu bieżące punkty wszystkich zawodników. Zapis wymaga expected_version spotkania, expected_rating_version z podglądu oraz Idempotency-Key. Nowy zapis ze starym podglądem daje 409. Identyczne ponowienie tego samego klucza zwraca bieżący stan bez nowej rewizji/punktów; inny payload pod tym kluczem jest odrzucany. Współdzielona blokada RatingState chroni odczyty rankingu, wyników i dziennika przed mieszaniem części różnych przeliczeń. Awaria wycofuje wszystkie zmiany, łącznie z wynikiem, obecnością, składem i receipt.

Pełna korekta historyczna ma osobny podgląd i zatwierdzenie. Wymaga ogólnego powodu oraz kompletnych list A/B. Każda osoba dodana do faktycznie obecnych albo z nich usunięta wymaga jawnej, odrębnej zmiany obecności z prywatnym powodem. Dodawana otrzymuje `present`, usuwana `no_show` albo `excused`; nie wolno usunąć kogoś z punktów ukrytą zmianą samego składu. Każdy faktycznie obecny jest w jednym składzie: 2–14, maks.7 na stronę i różnica liczebności najwyżej 1. Dopuszczone są istniejące profile historyczne, również zablokowane obecnie; korekta nie przywraca im dostępu do aplikacji.

Korekta tworzy nowy zatwierdzony TeamSheet i ResultRevision, aktualizuje Attendance oraz jego prywatne zdarzenia, następnie publikuje wynik i pełne przeliczenie razem. Dla wcześniej nieewidencjonowanego uczestnika powstaje źródłowy wpis obecności z powodem uzupełnienia; pozostałe korekty wskazują istniejący wpis. Nie przepisujemy dawnych deklaracji i rezerwacji: to źródłowa historia zapisów, a historyczna korekta odzwierciedla faktyczny mecz. Liczba uczestników zakończonego spotkania oraz PDF są pobierane z aktualnej Attendance, nie z dawnego Enrollment. Rezerwa zakończonego spotkania nie jest aktywną listą do dopisywania na sali.

Grupa widzi punkty, historię meczów, aktualne zmiany przed/delta/po i poprzednie wersje wyniku z autorem/czasem. Nie otrzymuje powodów korekt ani prywatnych zdarzeń obecności. Administrator dodatkowo odczytuje powody i poprzednie składy; zawodnik nadal widzi własną prywatną korektę obecności. Zablokowane profile zachowują punkty i historię; ranking nie publikuje flag blokady, roli ani statusu priorytetu. Wszyscy, także bez meczów rankingowych, zaczynają od 1000. Pozycja jest liczona z niezaokrąglonych punktów; identyczne wartości współdzielą pozycję, a prezentacja jest porządkowana nazwiskiem, imieniem i ID.

Endpointy E8, prefiks `/api/v1`:

- POST `/admin/meetings/{id}/result-preview`, POST `/admin/meetings/{id}/result` — podgląd i pierwszy zapis.
- POST `/admin/meetings/{id}/result-correction-preview`, POST `/admin/meetings/{id}/result/corrections` — pełna korekta z powodem i opcjonalnymi zmianami obecności.
- GET `/admin/meetings/{id}/result` — wynik, prywatne powody i poprzednie składy dla organizatora.
- GET `/meetings/{id}/result` — wynik i wersje bez prywatnych powodów; null przed pierwszym zapisem.
- GET `/ranking`, GET `/results`, GET `/players/{id}/rating-history` — ranking, historia spotkań i aktualnie przeliczona historia punktów. Limit 1–100 i offset≥0; własna i cudza historia punktów są grupowe, historia obecności pozostaje prywatna.

## Uzupełnienie E3/E5 — planowanie z kalendarza, 2026-11-08

`ScheduleInput.effective_until` jest opcjonalną, wyłączną datą końca serii. Zakres musi zawierać wybrany dzień tygodnia. Podgląd i zapis obejmują ten sam zakres, zachowują stabilne ID, odwołania i indywidualne wyjątki. Przy ograniczonej serii wcześniejsze reguły po końcu zakresu są zachowane; utrwalone późniejsze spotkania otrzymują powiązanie z zachowaną regułą, bez zmiany terminu ani zapisów.

`POST /admin/meetings` przyjmuje wersję harmonogramu, lokalną datę/godzinę, czas gry i miejsce. Tylko administrator może utworzyć dodatkowy, przyszły termin. Operacja pod blokadą ScheduleState odrzuca kolizje z zapisanymi i wyliczanymi terminami, zwiększa wersję harmonogramu i zapisuje audyt. `Meeting.is_additional` odróżnia dodatkowy termin od wystąpienia zmienianego harmonogramu. Jego źródłowa reguła jest nieaktywna (superseded), a rekord Meeting jest od razu trwały; zmiana serii nie przesuwa dodatkowego spotkania. Dodany termin podlega zwykłym deklaracjom, przesunięciom, odwołaniu, obecności i wynikom. Migracja 0008 zachowuje wszystkie dotychczasowe rekordy jako wystąpienia harmonogramu.

## Uzupełnienie: usuwanie spotkań, edycja serii i wydruk przed spotkaniem (2026-11-08)

Administrator może usunąć przyszłe nierozpoczęte lub odwołane spotkanie. Usunięty termin nie pojawia się w kalendarzu/next, nie otwiera się przez stary URL/API ani nie odtwarza przy rozwiązywaniu wystąpienia. W bazie zachowujemy niewidoczny znacznik wystąpienia (`deleted_at`), tożsamość oraz audyt; zamykamy miejsca/oferty bez oznaczania nieobecności. Historia rozegranych/obsługiwanych meczów jest chroniona. Usunięcie odwołanego terminu jest dostępne także po jego dacie. Zmiana harmonogramu przenosi znaczniki usunięcia do nowej reguły, dzięki czemu nie przywraca ich przypadkiem.

Administracyjne `/schedule/rules/{id}/preview` oraz `/edit` edytują wskazaną istniejącą regułę, również domyślną wtorkową. Obowiązuje wersja harmonogramu i token podglądu zawierający wersje wszystkich dotkniętych spotkań. Zmieniamy przyszłą część wskazanej reguły; zachowana przeszła część nie generuje nowych terminów. Zmiana dnia/godziny/miejsca wymaga ponownego potwierdzenia jak w D4, zachowuje ID i kolejność. Indywidualne terminy wewnątrz nowego zakresu pozostają wyjątkami. Spotkania poza nowym zakresem znikają z kalendarza. Inne aktywne reguły i dodatkowe pojedyncze terminy nie są nadpisywane; konflikt zakresów lub godzin jest odrzucany.

`/schedule/rules/{id}/delete-preview` oraz `/delete` usuwają przyszłą część serii i jej przyszłe utrwalone terminy (także indywidualne przesunięcia). Zachowujemy przeszłe/rozegrane spotkania, niezależne pojedyncze terminy i pozostałe reguły. Reguła nie zostaje zastąpiona wcześniejszym domyślnym wtorkiem: w usuniętym zakresie kalendarz jest pusty. Zmiana jest atomowa, pod wspólną blokadą ScheduleState i Meeting.

Lista podpisów jest dostępna administratorowi także przed spotkaniem. Gdy faktyczna obecność nie jest zatwierdzona, źródłem są `going/seat` z aktualną wersją terminu, bez oczekiwania na ponowne potwierdzenie i z aktywnego profilu. Rezerwa i zarezerwowane/pending oferty są wykluczone. Szkic obecności nie zmienia tej listy. Po zatwierdzeniu obecności źródłem są wyłącznie faktycznie obecni. Nagłówki `X-List-Basis` i `X-Meeting-Version` opisują źródło/świeżość; UI informuje o podstawie i zmianie danych po podglądzie. Pobranie zawsze generuje aktualny dokument. Eksport nie mutuje wersji spotkania, deklaracji ani obecności. Odwołany/usunięty termin nie ma eksportu.

## Wstępne drużyny z zapisów (2026-11-09)

Przed zatwierdzeniem obecności zaplanowane spotkanie pokazuje podział potwierdzonych miejsc według bieżącego ELO. Rezerwa, oferty, nieaktywne profile i niepotwierdzone zmienione terminy są wykluczone. Te same reguły wyrównania obejmują 2–14 osób, maksymalnie 7 na stronę; przy 0–1 nie tworzymy drużyn. Domyślny podział jest deterministyczny, odczyt nie zapisuje obecności ani oficjalnego składu.

Administrator może zapisać podział losowy, ręczną zamianę lub wrócić do ELO. Migracja 0010 dodaje osobną tabelę `preliminary_teams`. Odcisk wejścia obejmuje wersję terminu, aktualne ELO, osoby i kolejność zapisów oraz licznik zdarzeń zapisów. Każda zmiana deklaracji unieważnia stary wyjątek, również gdy po rezygnacji lista wróci do tych samych osób. Nie aktualizujemy wersji spotkania przy zmianie wstępnego podziału. Blokada spotkania oraz odcisk i rewizja podziału chronią listę i równoległe zmiany administratora (409). Publiczny DTO zawiera wyłącznie publiczne profile i punkty, bez statusów priorytetu czy powodów korekt.

- GET `/api/v1/meetings/{id}/preliminary-teams`: dla zalogowanych, podgląd lub null po zatwierdzeniu obecności/zmianie statusu; usunięte spotkanie daje 404.
- PUT `/api/v1/admin/meetings/{id}/preliminary-teams`: administrator i CSRF, `roster_token`, `revision`, tryb `balanced`, `random` lub `manual`; ręczny podział wymaga każdej uprawnionej osoby dokładnie raz.
- Istniejące generowanie oficjalnych drużyn przyjmuje też tryb `preliminary`. Nadal wymaga zatwierdzonej obecności. Zgodna lista i punkty zachowują podział wstępny; różnica osób lub punktów daje wyrównany podział faktycznie obecnych.
