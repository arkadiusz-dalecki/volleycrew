# E2/E9 — wpisywany login i hasło

Data: 2026-11-15. Użytkownik zastąpił wcześniejszy wybór profilu i PIN osobną nazwą użytkownika i hasłem. Potwierdził, że jedyny zarejestrowany profil to organizator; migracja graczy nie jest potrzebna. Zmiana rozszerza otwarty PR #11 z Google. Bez wdrożenia i bez zmian w produkcyjnej bazie.

## Zachowanie

- Login 3–32 znaki ASCII (litery/cyfry, kropka, myślnik, podkreślenie), normalizacja do małych liter i usunięcie skrajnych spacji. Unikalność wymuszona w PostgreSQL; równoczesne rejestracje oraz różna wielkość liter nie tworzą dwóch kont o tym samym loginie.
- Nowe hasło 15–128 punktów kodowych Unicode, bez obcinania, normalizacji i usuwania spacji. Argon2id z losową solą i dotychczasowymi parametrami. Frontend liczy Unicode także dla emoji, wspiera menedżery haseł i pełną klawiaturę. Bez zmieniania globalnej walidacji innych formularzy.
- Rejestracja i bootstrap wymagają loginu/hasła; rejestracja nadal wymaga aktywnego zaproszenia i nadaje gościa. Nie ma publicznego katalogu loginów/profili ani wyboru z listy.
- Zmiana hasła wymaga obecnego hasła. Reset od organizatora działa przez jednorazowy 30-minutowy fragment URL; pozwala ustawić hasło i odzyskać/zastąpić login. Konflikt nazwy nie zużywa grantu. Reset odłącza Google; samodzielna zmiana hasła zachowuje powiązanie. Zmiany unieważniają wcześniejsze sesje/granty i pozostawiają świeżą sesję bieżącego urządzenia.
- Google nadal wskazuje istniejący profil przez zweryfikowany sub. Połączenie/odłączenie wymaga obecnego hasła, bez PIN-u. Profile bez ustawionego hasła po migracji nie logują się również przez dawną sesję/Google.
- Trwałe limity 5 błędów/konto i 30/źródło w oknie 15 minut; potwierdzenia Google współdzielą licznik konta. Brak konta i konto zablokowane mają ten sam błąd i koszt sprawdzenia zastępczego hasha. Ochrona serii przed DB, logi bez sekretów, CSRF, oddzielność Ingress i kanonicznego OAuth pozostają.
- Własny login jest widoczny w profilu i w odpowiedziach konta/organizatora; nie trafia do list grupy, uczestników ani PDF. Przeglądarka pamięta tylko login; hasła nie są zapisywane w storage.

## Migracja i obsługa organizatora

`0012_password_login` zmienia kolumnę PIN-u na nullable password_hash, usuwa stare hashe PIN i dodaje prywatny unikalny username z ograniczeniami pary i formatu. Zmienia tabelę grantów na password_reset_grants, unieważnia stare sesje i granty oraz usuwa oczekujące przepływy Google. Dane profili, historia, zapisy i ELO pozostają. Dawne PIN-y nie są hasłami i nie ma endpointu migracji graczy.

Dla organizatora bez nowych danych dostępny jest nowy operatorowy grant setup: nowy losowy BOOTSTRAP_TOKEN w opcjach HA + restart + PUBLIC_URL/setup#token. Stary wykorzystany token nie jest reaktywowany. Ustawienie danych zachowuje istniejące ID, rolę, status, nazwisko i historię, odłącza poprzednie Google i ponownie zamyka bootstrap; kolejne tokeny nie zastępują konta z już ustawionym hasłem. Alternatywa poza HA: npm run auth:bootstrap -- --rotate. Procedura i kopia przed aktualizacją: [DOCS](../../volleycrew/DOCS.md#przejście-z-pin-u-na-login-i-hasło).

Downgrade zachowuje profile, ale **nie odtwarza PIN-ów ani loginów**; nie jest procedurą cofnięcia dostępu. Rollback wymaga zgodnego obrazu i kopii sprzed aktualizacji. Wersja pakietu pozostaje 0.3.4 (bez zlecenia zmiany wersji). Automatyczny backup startu wykrywa także zmianę head migracji.

## Weryfikacja

- Lokalny PostgreSQL 17.11, Python 3.13.18, Node 26.8.1, macOS arm64. Wyłącznie bazy testowe: volleycrew_password_test oraz osobna volleycrew_password_e2e_test na tymczasowym klastrze loopback. Po rozdzieleniu baz pełny backend: **197 zaliczonych**, 2 istniejące ostrzeżenia HTTPX. Nowe testy obejmują format/normowanie loginów, długość i dokładność haseł, brak ujawniania danych, konkurencję loginów, wspólne limity, odzyskiwanie loginu i przejście istniejącego organizatora z zachowaniem danych oraz zamknięciem bootstrapu.
- **10 testów jednostkowych frontendu** zaliczonych, w tym Unicode/whitespace i formularze Ingress. Lint, typy, kontrakt OpenAPI i build zaliczone lokalnie.
- Pełne E2E desktop/mobile/WebKit: **83 zaliczone, 1 celowo pominięty na desktopie** (4,3 min). Dedykowane Google: **6 zaliczonych** (20,5 s), z połączeniem po haśle, logowaniem na ten sam profil i odłączeniem. Lokalny wystawca podpisuje RSA; callback, PKCE i sesje wykonuje rzeczywisty kod. Mobilne zrzuty logowania i profilu sprawdzono wizualnie; zapisano lokalnie poza repozytorium.
- Docker lokalnie niedostępny; rzeczywiste obrazy amd64/aarch64, HTTPS/Ingress i backup/restore w CI dla końcowego HEAD PR. Wynik w PR; lokalne buildy/atrapa Google nie zastępują tych testów.

## Ograniczenia odbioru

Nie konfigurowano projektu Google ani rzeczywistego konta, nie wdrażano na HA i nie wykonywano odbioru na fizycznym telefonie/PWA. Po wdrożeniu organizator musi jednorazowo ustawić login i hasło przez nowy link setup. Dotychczasowe sesje/PIN-y są celowo nieważne. Pełna migracja graczy oraz logowanie e-mailem nie należą do zlecenia.

Podstawa polityki długości: [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), odczyt 2026-11-15. Dokument nie jest deklaracją kompletnej zgodności z NIST/ASVS.
