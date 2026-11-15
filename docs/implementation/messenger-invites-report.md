# E2/E9 — hasła i zaproszenia z Messengera

2026-11-15. Zakres zlecony przez użytkownika; gałąź `fix/password-and-messenger-invites`.

## Zachowanie

- Nowe hasło: 8–128 punktów kodowych Unicode, bez wymuszania wielkich liter, cyfr czy znaków specjalnych. Rejestracja, bootstrap, reset, zmiana i dodawanie hasła korzystają ze wspólnej walidacji. Zachowane spacje, Unicode, Argon2id i limity logowania.
- Nowo tworzone zaproszenia: `/join?token=…`. Formularz odczytuje token z query przed fragmentem, więc dodatkowe parametry oraz usunięcie/zastąpienie fragmentu nie usuwają zaproszenia. Stare `/join#…` nadal działają. Link otwierany z Ingress do publicznego Google również przenosi zaproszenie w query.
- Query/fragment są usuwane przez History API po odczycie, bez zapisu w storage. Odświeżenie nadal wymaga ponownego otwarcia pełnego linku. Reset/bootstrap/granty Google nie przyjmują tokenów w query. Zmiana nie wymaga migracji bazy ani rotacji istniejących tokenów.
- Nginx już pomija URL w access logs i wysyła no-referrer/no-store; API nie prowadzi access logs. Dodana meta no-referrer chroni też otwieranie strony poza Nginx pakietu. Zewnętrzne proxy nie powinno logować query zaproszeń; instrukcja operatora opisuje tę różnicę.

Komunikat braku tokenu dodatkowo wyjaśnia, że w Messengerze można skopiować pełny link z wiadomości i wkleić go do Safari lub Chrome. Wskazówka dotyczy oryginalnej wiadomości, a nie już oczyszczonego adresu strony.

## Diagnoza i granice

Użytkownik potwierdził, że ten sam pełny link działa po skopiowaniu do przeglądarki, a w Messengerze pojawia się brak tokenu. Nie uzyskano faktycznego zmodyfikowanego URL ani dostępu do fizycznego Messengera. Test wykazał, że samo query `fbclid` przed istniejącym fragmentem nie psuje dotychczasowego formularza; opóźniony fragment też jest obsługiwany. Nie przypisujemy więc Messengerowi udowodnionej konkretnej modyfikacji. Zmieniony transport zaproszenia usuwa zależność od zachowania fragmentu w pośredniej przeglądarce. Regresja dla query z zastąpionym fragmentem najpierw nie przeszła, po zmianie przeszła.

## Wykonane sprawdzenia

- PostgreSQL 14.24, osobno utworzona lokalna baza `volleycrew_access_fix_test`, bez użycia development/produkcji. `test_auth.py`, `test_password_auth.py`, `test_google_registration.py`, `test_auth_protection.py`: **48 zaliczonych**. Rejestracja, zmiana/reset i logowanie hasłem 8 znaków, unieważnienie zaproszeń, powiązania Google i ochrona dostępu.
- Pełny Vitest: **15 zaliczonych**; query/stary fragment, parametry śledzące, opóźniony fragment, ignorowanie query dla grantów oraz Unicode i długości haseł.
- Po dodaniu wskazówki Messenger ponowiono `auth-links.spec.ts`: **9 zaliczonych** w trzech projektach.
- Playwright `auth-links.spec.ts`, `auth.spec.ts`: **12 zaliczonych** w Chromium desktop, Chromium mobile i WebKit iPhone. Testy używają osobnego API i powyższej testowej bazy po zakończeniu backendu. Pełna rejestracja i reset hasłem 8 znaków, logowanie, blokada, cofnięte zaproszenie, stary i nowy format, czyszczenie adresu/brak tokenu w storage, odświeżenie. Przeglądarki uruchamiane lokalnie; emulacja nie zastępuje fizycznego iPhone.
- `npm run lint`, `npm run typecheck`, `npm run api:generate`, `npm run api:check`, `npm run build`, `git diff --check`: zaliczone. Kontrakt OpenAPI pozostaje bez zmiany pól (minimum nowego hasła jest walidatorem modelu).

Na etapie weryfikacji lokalnej nie wykonano obrazów HA (Docker niedostępny), wdrożenia ani fizycznego testu Messengera. Wyniki GitHub CI są dostępne w PR. Wersja pakietu pozostaje bez zmian. Po wdrożeniu należy utworzyć nowy link zaproszenia z query i sprawdzić jego bezpośrednie otwarcie z Messengera na telefonie.
