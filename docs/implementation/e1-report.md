# E1 — szkielet aplikacji

Data: 2026-11-06. Stan: implementacja gotowa i zweryfikowana lokalnie. Pełny odbiór E1 oczekuje na uruchomienie CI z PostgreSQL 17; build obrazu HA na obu CPU pozostaje niewykonany. Nie wdrożono nic na Home Assistant, nie utworzono produkcyjnej bazy ani nie opublikowano obrazu.

## Zakres wykonany

- FastAPI, walidowane ustawienia, async SQLAlchemy, wstrzykiwany zegar UTC, sesje DB na żądanie i bezpieczny kontrakt błędów.
- Liveness bez wymagania DB oraz readiness sprawdzające połączenie i zgodność `alembic_version` z aktualną migracją.
- Alembic z bazową migracją bez tabel domenowych. Powtórne uruchomienie migracji nie zmienia stanu. Modele profili i spotkań pozostają w E2/E3.
- React/TypeScript/Vite z React Router i TanStack Query, układ A, cztery zakładki, stany puste i wskaźnik połączenia API z loading/błędem/ponowieniem. Fonty dostarczane lokalnie.
- OpenAPI eksportowane z backendu do `frontend/openapi.json`, wygenerowane typy klienta w `src/lib/api/schema.d.ts`, kontrola ich aktualności.
- `npm run setup`, wspólny `npm run dev`, migracje, lint/format, typecheck, testy i build. Lockfile npm oraz uv.
- `compose.dev.yaml`: osobna developerska PostgreSQL 17 na localhost, trwały wolumen, healthcheck. Bez połączeń do maybe-finance.
- CI: `.github/workflows/checks.yml`, usługa PostgreSQL 17 i izolowane testy/build. Workflow nie publikuje i nie wdraża aplikacji.

## Weryfikacja wykonana

Środowisko lokalne: macOS ARM64, Node 26.8.1 (projekt i CI wskazują 24 LTS), Python 3.13.18 pobrany przez uv 0.13.7. Backend z lockfile: FastAPI 0.162.0, SQLAlchemy 2.0.57, Alembic 1.20.1, asyncpg 0.32.0. Frontend: React 19.3.1, Vite 8.3.6; pełne wersje w lockfile.

| Sprawdzenie | Wynik |
| --- | --- |
| `npm run setup` | Powodzenie; instalacja przez lockfile |
| `npm run lint` | Ruff i ESLint/Prettier przechodzą |
| `npm run typecheck` | Przechodzi |
| `npm run api:check` | OpenAPI i wygenerowane typy są aktualne |
| Backend z `VOLLEYCREW_TEST_DATABASE_URL` | 7 testów przechodzi, w tym rzeczywista migracja i nieaktualny schemat |
| `npm run test:frontend` | 1 test przechodzi: błąd gotowości API i powrót po ponowieniu |
| `npm run build` | Przechodzi; statyczny build w `frontend/dist` |
| `npm run test:e2e` | 2 testy Chromium: desktop 1440 × 1000 i mobile 390 × 844; rzeczywiste API, trasy po reloadzie, brak overflow |
| Kontrola wizualna | Obejrzane screenshoty obu wariantów rozmiaru; pliki generowane w ignorowanym `frontend/test-results` |

Testy DB wykonano na **PostgreSQL 14.24**, dostępnej lokalnie, w nowym klastrze `.runtime/postgres` i osobnej bazie `volleycrew_test`. Domyślny Compose i CI nadal używają PostgreSQL 17. Testy 14 nie dowodzą zgodności 17; wynik CI trzeba dopisać po rzeczywistym uruchomieniu. Lokalny klaster jest developerski, tylko localhost:55432, z auth trust, i nie nadaje się do produkcji.

## Pozostałe ograniczenia

- Docker nie jest zainstalowany w tym środowisku. Nie uruchomiono Compose ani nie pobrano/testowano obrazu bazowego HA i manifestów `aarch64/amd64`. Te sprawdzenia pozostają otwarte; s6/Nginx i instalowalny pakiet są zakresem E10.
- Nie wykonano GitHub Actions: repozytorium nie zostało wypchnięte przez agenta. Dodanie workflow nie oznacza zielonego CI.
- TestClient zgłasza deprecjację transportu httpx w aktualnej Starlette; testy działają. Przed E2 sprawdzić migrację transportu testowego, bez wyciszania ostrzeżenia jako substytutu poprawki.
- Brak logowania, danych uczestników, harmonogramu, deklaracji, PDF i ELO w aplikacji produkcyjnej. Zakładki są szkieletem, nie demonstracją zakończonych funkcji.
- Ingress, cookies, CSRF, zaufane proxy i prefiks URL nie są jeszcze zaimplementowane. Aktualny klient działa na wspólnym origin `/api`; obsługa prefiksu wymaga testów E10.

## Handoff

Szkielet jest gotowy do rozpoczęcia E2 po zleceniu przez użytkownika. Najpierw przeczytać `domain-api.md`, `frontend.md` i zatwierdzony D6. Przed implementacją sesji zamknąć ich czas ważności i limity prób wskazane w E0. D8 pozostaje częściowo otwarte, a szczegóły produkcyjnej bazy i backupów wracają przed E10.

Komendy lokalnego uruchomienia i testów są w głównym README; nie tworzyć drugiej, rozbieżnej instrukcji w tym raporcie.
