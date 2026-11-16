# E1 - Application skeleton

Date: 2026-11-06. Status: implementation ready and locally verified. Full acceptance testing E1 awaits CI launch with PostgreSQL 17; HA image build on both CPUs remains undone. Not deployed anything on Home Assistant, no production database created and no image published.

## Scope completed

- FastAPI, validated settings, async SQLAlchemy, injected UTC clock, on-demand DB sessions and secure error contract.
- Liveness without DB requirement and readiness checking the connection and compatibility of `alembic_version` with the current migration.
- Alembic with base migration without domain tables. Rerunning the migration does not change the state. Profile and meeting models remain in E2/E3.
- React/TypeScript/Vite with React Router and TanStack Query, layout A, four tabs, empty states and API connection indicator with loading/error/retry. Fonts delivered locally.
- OpenAPI exported from the backend to `frontend/openapi.json`, generated client types in `src/lib/api/schema.d.ts`, checking their validity.
- `npm run setup`, common `npm run dev`, migrations, lint/format, typecheck, tests and build. Lockfile npm and uv.
- `compose.dev.yaml`: separate PostgreSQL 17 development on localhost, persistent volume, healthcheck. No connections to maybe-finance.
- CI: `.github/workflows/checks.yml`, PostgreSQL 17 service and isolated tests/build. Workflow does not publish or deploy applications.

## Verification completed

Local environment: macOS ARM64, Node 26.8.1 (project and CI indicate 24 LTS), Python 3.13.18 downloaded via uv 0.13.7. Backend with lockfile: FastAPI 0.162.0, SQLAlchemy 2.0.57, Alembic 1.20.1, asyncpg 0.32.0. Frontend: React 19.3.1, Vite 8.3.6; full versions in lockfile.

| Checking                                    | Result                                                                                                 |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `npm run setup`                             | Success; installation via lockfile                                                                     |
| `npm run lint`                              | Ruff and ESLint/Prettier pass                                                                          |
| `npm run typecheck`                         | Passed                                                                                                 |
| `npm run api:check`                         | OpenAPI and generated types are up to date                                                             |
| Backend with `VOLLEYCREW_TEST_DATABASE_URL` | 7 tests pass including actual migration and stale schema                                               |
| `npm run test:frontend`                     | 1 test passes: API ready error and return for retry                                                    |
| `npm run build`                             | It passes; static build in `frontend/dist`                                                             |
| `npm run test:e2e`                          | 2 Chromium tests: desktop 1440 × 1000 and mobile 390 × 844; real API, routes after reload, no overflow |
| Visual inspection                           | Viewed screenshots of both size variants; files generated in ignored `frontend/test-results`           |

DB tests were performed on **PostgreSQL 14.24**, available locally, in the new `.runtime/postgres` cluster and a separate database `volleycrew_test`. Default Compose and CI still use PostgreSQL 17. Tests 14 do not prove compatibility 17; CI result must be added after the actual launch. The local cluster is development, only localhost:55432, with auth trust, and is not suitable for production.

## Other restrictions

- Docker is not installed in this environment. Compose was not started and the HA base image and `aarch64/amd64` manifests were not downloaded/tested. These checks remain open; s6/Nginx and the installable package are scoped to E10.
- GitHub Actions not performed: repository not pushed by agent. Adding workflow does not mean green CI.
- TestClient reports httpx transport deprecation in current Starlette; tests work. Before E2, check for test transport migration, without silencing the warning as a substitute for a fix.
- No login, participant data, schedule, declaration, PDF and ELO in the production application. Tabs are a framework, not a demonstration of completed functions.
- Ingress, cookies, CSRF, trusted proxy and URL prefix are not implemented yet. The current client is running on shared origin `/api`; prefix support requires E10 tests.

## Handoff

The skeleton is ready to start E2 when requested by the user. First read `domain-api.md`, `frontend.md` and approved D6. Before implementing sessions, close their expiration time and attempt limits indicated in E0. D8 remains partially open, and details of the production database and backups return before E10.

Local run and test commands are in the main README; do not create a second, divergent instruction in this report.
