# E2/E9 — rejestracja przez Google z edytowalnymi danymi

Data: 2026-11-15. Zlecenie: zaproszenie od organizatora → Dołącz przez Google → podpowiedziane imię/nazwisko z możliwością zmiany → zatwierdzenie i konto bez hasła. Uzupełnia otwarty PR #11. Bez wdrożenia ani odczytu/zmian danych produkcyjnych.

## Kryteria i zachowanie

| Kryterium | Realizacja / dowód |
| --- | --- |
| Zaproszenie pozostaje wymagane | Sprawdzenie przy starcie, po zewnętrznym I/O Google oraz przy odczycie/zatwierdzeniu formularza. Testy cofnięcia w każdym etapie. Normalne Google login nie rejestruje nieznanego konta. |
| Podpowiedzi można zmienić | Zweryfikowane given_name/family_name trafiają do formularza, z ograniczeniem długości i usunięciem znaków kontrolnych; finalne dane przechodzą zwykłą walidację profilu. Brak nazw u Google oznacza puste pola, bez zgadywania. Nazwisko istniejącego profilu nie jest nadpisywane podczas logowania. |
| Konto dopiero po potwierdzeniu | Callback wydaje krótki grant, nie tworzy Player. Zatwierdzenie tworzy Player, GoogleIdentity i sesję w jednej transakcji. Zawsze role=player, priority_status=guest; brak pól roli/sub w DTO klienta. |
| Bez lokalnego hasła | Username/password_hash pozostają null; aktywna sesja wymaga co najmniej hasła lub powiązania Google. Google-only loguje się normalnym przyciskiem Google. Nie ma sztucznego hasła ani wymuszonej nazwy użytkownika. |
| Brak duplikatów | Unikalny sub i istniejąca blokada auth w PostgreSQL. Dwie finalizacje tego samego Google kończą się na tym samym profilu; ponowne zaproszenie loguje istniejącego aktywnego gracza. Brak dopasowania po e-mailu/nazwisku i brak odblokowania zablokowanego profilu. |
| Granice dowodu | GoogleActionGrant ma tylko hash losowego tokenu i cookie przeglądarki, cel, sub, zaproszenie albo dokładną sesję, podpowiedzi i daty. Maks.10 minut od startu OAuth; jednorazowość, przeglądarka i CSRF. Odrzucony replay/wygaśnięcie nie tworzy konta. |
| Prywatność | Token finalizacji wraca we fragmencie, jest usuwany z adresu i przesyłany w body. Nie trafia do storage ani kluczy Query. E-mail, zdjęcie i tokeny Google nie są zapisywane. Podpowiedzi/sub są czyszczone po konsumpcji grantu; wygasłe granty usuwane przy kolejnym starcie Google. |
| Dodatkowa metoda logowania | Google-only może ustawić login/hasło po nowym dowodzie tego samego sub, tej samej aktywnej sesji i przeglądarki. Samo posiadanie sesji Volleycrew nie wystarcza. Operacja zachowuje Google i ID profilu, unieważnia stare sesje/reset i wydaje świeżą sesję. |
| Bez odcięcia dostępu | Nie można odłączyć jedynego Google. Po ustawieniu lokalnych danych odłączenie wymaga hasła. Organizator nadal może odzyskać konto jednorazowym resetem hasła, który usuwa stare powiązanie Google. |
| HA/Ingress i limity | Brak przenoszenia sesji: osobna karta kanonicznego join z zaproszeniem wyłącznie we fragmencie. Odczyt potwierdzenia ma oddzielny, ograniczony budżet krótkich serii i trwałe 60/źródło/15 min; weryfikacje haseł zachowują dotychczasowy budżet. Rejestracja Google współdzieli trwały limit rejestracji 10/źródło/15 min. UI pokazuje Retry-After i pozwala ponowić odczyt; mutacje bez automatycznego retry. |

## Kontrakt i migracja

Nowy tryb register (invite_token) oraz password w Google start, podstawowy zakres openid/profile. JWT, PKCE, nonce, issuer/aud/exp i jednorazowy browser-bound state nadal realizuje dotychczasowy dostawca Authlib/PyJWT; podpowiedzi są odczytywane dopiero z tokenu po poprawnej weryfikacji. W opisie Google pola profilu są opcjonalne, dlatego nie stanowią identyfikatora.

Nowe endpointy: POST /auth/google/completion {token}, POST /auth/google/register {token, first_name, last_name, nickname?}, POST /me/google/password {token, username, password}. DTO własnego konta zawiera has_password i nullable username. Cienkie route delegują finalizację do google_actions; przepływ OAuth pozostaje w google_auth, a wspólne sesje/CSRF w auth/security.

Migracja **0013_google_registration** dodaje tryb/kontekst zaproszenia w GoogleFlow i tabelę GoogleActionGrant. Profile bez danych po starszej migracji PIN-u nie uzyskują wstecznie dostępu Google-only: ich dawne powiązania/sesje są unieważniane przed uruchomieniem nowej ścieżki. Bootstrap pozostaje zamknięty dla organizatora mającego dowolną metodę dostępu. Nazwy, zapisy, obecność, drużyny, historia i ELO pozostają. Downgrade nie zapewnia dostępu Google-only w starszym kodzie; do rollbacku stosuj zgodny backup/obraz. Wersja 0.3.4 bez zmiany (brak zlecenia bumpa).

## Weryfikacja lokalna

macOS arm64, Python 3.13.18, PostgreSQL 17.11, Node 26.8.1. Backend: osobna volleycrew_google_join_test; przeglądarki: volleycrew_google_join_e2e_test, port loopback 59643. Jedna baza nie jest jednocześnie resetowana przez oba zestawy.

- Pełny pytest na PostgreSQL: **207 zaliczonych**, 2 istniejące ostrzeżenia HTTPX. Obejmuje podpisane JWT i rzeczywisty exchange Authlib przez podstawiony wyłącznie transport Google, granice sesji/linków, konkurencję, migracje, prawa i reguły pozostałej aplikacji.
- Dedykowane Google E2E: **12 zaliczonych** (58,2 s) w desktop/mobile/WebKit. Sprawdza podpowiedzi, zmianę nazwiska, brak konta przed zatwierdzeniem, guest/bez hasła po zatwierdzeniu, logowanie tym samym sub, dodanie hasła po nowym Google, odłączenie i logowanie lokalne. Osobno czyszczenie fragmentu i odświeżenie. Testy respektują rzeczywisty Retry-After przy zbyt szybkich kliknięciach; nie wyłączają ani nie resetują limitera aplikacji.
- **11 unit frontend**, lint, typy, OpenAPI generate/check i build zaliczone. Mobilny zrzut formularza sprawdzono wizualnie; zrzuty pozostają poza repozytorium.
- Pełna zwykła macierz E2E: **83 zaliczone, 1 celowo pominięty na desktopie** (4,4 min). Rzeczywiste obrazy amd64/aarch64, HTTPS/Ingress i backup/restore: wynik CI dla końcowego HEAD w PR. Docker lokalnie niedostępny.

## Odbiór operatora i źródła

Instrukcja: [Dołączanie przez Google](../../volleycrew/DOCS.md#dołączanie-przez-google). Nadal potrzebny własny klient Google, dokładny callback, PUBLIC_URL i dane w HA. Bez rzeczywistego consent/login Google i fizycznego HA/telefonu/PWA; testowy wystawca nie trafia do obrazu produkcyjnego. Brak automatycznego merge/wdrożenia.

[Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), odczyt 2026-11-15: openid/profile, opcjonalne given_name/family_name, podpowiedzi formularza i sub jako identyfikator; [Google branding](https://developers.google.com/identity/branding-guidelines). Lokalny Google Sans od oficjalnego Google Fonts rozszerzony o Dołącz przez Google (2700 B), zachowana licencja OFL i oficjalna ikona G.
