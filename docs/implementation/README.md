# Plan budowy Volleycrew

Data: 2026-11-06. Stan: plan do realizacji etapami; część reguł wymaga decyzji. Dokumenty nie oznaczają rozpoczęcia implementacji ani wdrożenia.

## Cel i granice

Prywatna aplikacja jednej grupy siatkarskiej, z Arkadiuszem jako początkowym jedynym administratorem. Użytkownicy zapisują się na spotkania, organizator obsługuje obecność, drużyny, wynik i listę podpisów. ELO ma charakter zabawy. UI: zaakceptowany wariant A, jasny, wygodny na telefonie.

Pierwsze wydanie ma obsłużyć pełny cykl od zaproszenia przez deklaracje i mecz do historii oraz rankingu. Kolejność dostarczania funkcji jest w backlogu; wcześniejsze demonstracje nie oznaczają gotowości produkcyjnej.

Poza zakresem pierwszego wydania: płatności, automatyczne kary, integracja i automatyczne wiadomości Messenger, powiadomienia push, statystyki punktowe, śledzenie rotacji, wiele grup, aplikacje natywne i automatyczne uprawnienia wynikające z konta HA. Instalacja strony na ekranie telefonu jest pożądana; działanie zapisów offline nie jest wymagane.

## Jak używać planu

1. Przeczytaj [architekturę](architecture.md) i [rejestr decyzji](decisions.md).
2. Wybierz gotowe zadanie z [etapów budowy](tasks.md); sprawdź zależności i blokujące decyzje.
3. Backend i baza: przeczytaj [domenę oraz API](domain-api.md). Frontend: [specyfikację interfejsu](frontend.md).
4. Przed zakończeniem zadania zastosuj właściwe [kryteria weryfikacji i wydania](verification.md).
5. Zapisz wynik w tabeli postępu poniżej. Kolejny agent powinien móc odtworzyć stan na podstawie dokumentacji, kodu i wyników testów.

Dokumenty opisują docelowe zachowanie. E1 dostarcza już szkielet frontendu, API i migracji w `volleycrew/`; E2 dodaje dostęp i profile. E3 dodaje harmonogram, kalendarz i trwałe terminy spotkań. E4 dodaje deklaracje, priorytety i rezerwę z ofertami. E5 dodaje podgląd i zmiany harmonogramu, przesunięcia, odwołania i ponowne potwierdzenia. E6 dodaje faktyczną obecność, prywatną historię z korektami i wersjonowane drużyny na boisku wariantu A. E7 dodaje lokalnie generowany PDF listy podpisów z autoryzowanym podglądem i pobraniem. E8 dodaje wyniki, ranking ELO, historię punktów i pełne korekty historyczne z atomowym przeliczeniem. E9 integruje UI, dostępność i odporność sieci/sesji; odbiór na fizycznych telefonach i porównania wizualnego pozostaje otwarty. E10 dostarcza pakiet HA i lokalne testy obu CPU, Ingress oraz odtworzenia; samodzielna instalacja użytkownika i wydanie pozostają do odbioru. `prototype/` jest osobną referencją wizualną. Stan weryfikacji i ograniczenia: [raport E1](e1-report.md).

## Hierarchia ustaleń

Polecenia użytkownika mają pierwszeństwo. Potwierdzone reguły produktu zapisano w `domain-api.md` i `frontend.md`. Proponowane rozstrzygnięcia oznaczono identyfikatorami D w `decisions.md`. Gdy decyzja zmienia specyfikację, aktualizuj właściwy dokument; rejestr ma przechowywać datę i uzasadnienie, nie kopię całej reguły.

Architektura techniczna stanowi bazę planu opartą na wcześniejszej propozycji. Konkretne wersje zależności i szczegóły publikacji należy zweryfikować w E0. Agent nie powinien traktować wartości z prototypu, przykładowych portów ani otwartych parametrów rankingu jako wymagań; skala K=32 jest już zatwierdzona w domain-api.md.

## Postęp i przekazywanie pracy

| Etap | Stan | Dowody / pozostałe zależności |
| --- | --- | --- |
| E0 | W toku — fundament techniczny przygotowany | [Ustalenia E0](e0-foundations.md): Pi 4 aarch64, Tunnel poza zakresem, osobny PostgreSQL, pełny zakres i polityka backupu potwierdzone. D2 zatwierdzone; D3 zatwierdzone z prywatnością statusu; D4 zatwierdzone (kolejność, rezerwacje i nowe potwierdzenie przy każdej zmianie, także dla ofert); D5 zatwierdzone (korekty, usprawiedliwienia, spóźnienia, dopisywanie); D6 zatwierdzone (blokada, przydomek, lista logowania z maskowaniem); D7 zatwierdzone; D8 zatwierdzone (K=32, skala 400, precyzja, 0:0, pełne korekty i porządek start/ID); D10 zatwierdzone (lokalny build HA jak w maybe-finance); parametry sesji/resetu/limitu PIN zatwierdzone w E2; wersje/digesty i oba obrazy sprawdzono lokalnie w E10; szczegóły produkcyjnego D1 i odbiór pozostają po stronie użytkownika. |
| E1 | Zaimplementowany i sprawdzony lokalnie; pełny odbiór oczekuje | [Raport E1](e1-report.md): działający frontend/API, migracje i testy. Zdalne CI oczekuje na publikację kodu; lokalne PostgreSQL 17 i oba obrazy potwierdzone w E10. |
| E2 | Zaimplementowany i sprawdzony lokalnie | [Raport E2](e2-report.md): PIN, sesje, zaproszenia, bootstrap, profil, reset, blokada dostępu; testy PostgreSQL i UI. Obsługa miejsc przy blokadzie oraz zmiana priorytetu w E4; HA/Ingress i Pi w E10. |
| E3 | Zaimplementowany i sprawdzony lokalnie | [Raport E3](e3-report.md): modele, wyliczany kalendarz, najbliższy termin, szczegóły, idempotentne utrwalanie i prywatność DTO. 35 testów backendu, 6 E2E; deklaracje w E4, edycja harmonogramu w E5. |
| E4 | Zaimplementowany i sprawdzony lokalnie | [Raport E4](e4-report.md): deklaracje, prywatne priorytety, rezerwacje/oferty, ochrona ponowień, granica 24 h, blokada i zwalnianie przyszłych miejsc. 52 testy backendu, 8 E2E. |
| E5 | Zaimplementowany i sprawdzony lokalnie | [Raport E5](e5-report.md): podgląd/wersje harmonogramu, zachowanie indywidualnych wyjątków, stabilne ID, odwołania i nowe potwierdzenia/oferty. 63 testy backendu, 10 E2E. |
| E6 | Zaimplementowany i sprawdzony lokalnie | [Raport E6](e6-report.md): szkic/zatwierdzenie obecności, zwalnianie miejsc z rezerwą, dopisywanie na sali i prywatne korekty; dwa generatory, boisko z rotacją i zamiana 7:7, wersje/publikacja/ponowienia. 85 testów backendu, 12 E2E. |
| E7 | Zaimplementowany i sprawdzony lokalnie | [Raport E7](e7-report.md): PDF A4 z faktycznie obecnych, polskie znaki/osadzone fonty, podgląd na telefonie i aktualne pobranie po korekcie, wyłącznie dla administratora. 91 testów backendu, 12 E2E. |
| E8 | Zaimplementowany i sprawdzony lokalnie | [Raport E8](e8-report.md): wynik/0:0, Decimal/Numeric ELO, wersje i pełne korekty, przeliczenie późniejszych spotkań, ranking i historia punktów; prawdziwe ELO w podziale drużyn. 107 testów backendu, 12 E2E. D8 domknięte. |
| E9 | Zaimplementowany i sprawdzony lokalnie; pełny odbiór oczekuje | [Raport E9](e9-report.md): kontrast, cele dotykowe, dialogi/fokus, zachowanie formularzy przy błędach sieci, wygaśnięcie sesji i manifest. 32 E2E zaliczone w Chromium/WebKit, 1 celowo pominięty na desktopie. Pozostają fizyczny Chrome Android/Safari iOS z wersjami oraz akceptacja porównania A. |
| E10 | Zlecony zakres pakietu i testów lokalnych zakończony; instalacja po stronie użytkownika | [Raport E10](e10-report.md) i [instrukcja HA](../../volleycrew/DOCS.md): lokalny build, token bez SSH, Nginx/Ingress i cookies, migracje, backup i osobny restore. 115 testów na PG17, 32 E2E i 12 prób UI produkcyjnych obrazów. ARM64 oraz amd64/QEMU sprawdzone. Bez push i instalacji na HA; Pi/RAM, produkcyjne proxy, fizyczne telefony i kopia poza hostem pozostają do odbioru. |
| E10 — poprawka HA 0.1.1 | Scalona w PR #2, instalacja HA potwierdzona przez użytkownika; start zatrzymany na braku zewnętrznej bazy | [Raport](ha-build-fix.md): usunięty build.yaml, przypięty runtime Debian, regresja z awaryjnym BUILD_FROM Supervisor; 8 testów konfiguracji i lint zaliczone. |
| E10 — własna baza 0.2.0 | Implementacja i testy w toku | [Raport](bundled-postgresql.md): decyzja użytkownika o własnym PostgreSQL; start, trwałość, backup i restore oraz zgodność external. Fizyczna instalacja/odbiór po stronie użytkownika. |
| E11 | Nierozpoczęty | Końcowy odbiór i wydanie po samodzielnej instalacji oraz kontroli CI; otwarte punkty E9/Pi/backup pozostają jawne. |

Po etapie dodaj osobny wiersz: identyfikator, stan, commit/PR jeśli istnieje, komendy weryfikacyjne i wynik, otwarte D, następne gotowe zadanie. Nie oznaczaj zadania ukończonego przy niespełnionym kryterium. Jeżeli agent pracuje nad ograniczonym zakresem, raportuje ten zakres zamiast ogłaszać gotowość całej aplikacji.
