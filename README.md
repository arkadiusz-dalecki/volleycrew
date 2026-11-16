> From 0.2.0, the Home Assistant package includes bundled PostgreSQL 17. For a regular installation, leave DATABASE_MODE=auto and empty POSTGRES_HOST; server, database and access data will be created automatically. Development and tests continue to use separate databases.

# Volleycrew

An application for organizing volleyball meetings, designed for installation as a Home Assistant app built locally in HA, like maybe-finance.

Project documentation is in English. The application interface is in Polish; quoted button and field labels retain their actual Polish wording.

## Current status

E1 provides a runnable foundation: React/TypeScript/Vite in the accepted layout A, FastAPI API, PostgreSQL, migrations, OpenAPI contract and tests. E2 adds invitation registration, logins and passwords, persistent sessions, reset and access blocking. E3 adds a calendar with a schedule, the next meeting and persistent meeting details. E4 adds enrollments, private priorities, a waitlist and seat offers. E5 adds a schedule from the selected date, individual postponements, cancellations and new confirmations of participation. E6 adds attendance, private history and corrections, and teams on the variant A court. E7 adds administrative preview and PDF signature list download. E8 adds results, ELO ranking, point history and full corrections with recalculation of subsequent matches. E9 refines accessibility and phone support, dialogs, network/session loss and adds a manifest. Local Chromium/WebKit checks have passed; acceptance testing on physical phones and approval of the UI comparison remain open.

[Implementation Plan](docs/implementation/README.md) · [E1 Report and Constraints](docs/implementation/e1-report.md) · [Product Decisions](docs/implementation/decisions.md) · [E2 Report](docs/implementation/e2-report.md) · [E3 Report](docs/implementation/e3-report.md) · [E4 Report](docs/implementation/e4-report.md) · [Report E5](docs/implementation/e5-report.md) · [Report E6](docs/implementation/e6-report.md) · [Report E7](docs/implementation/e7-report.md) · [Report E8](docs/implementation/e8-report.md) · [Report E9 and UI Comparison](docs/implementation/e9-report.md) · [HA Package - E10](docs/implementation/e10-report.md)

## Development setup

Requirements: Node 24 LTS (26 also allowed), npm, Python 3.9+ to run the script and Docker Compose for local PostgreSQL 17. The backend runs on Python 3.13, downloaded via uv. If uv is not available, setup installs it to the ignored `.tools/`. First installation requires internet.

```sh
npm run setup
npm run db:up
npm run dev
```

Setup installs dependencies from lockfile and creates `.env` from `.env.example` if the file does not already exist. Dev applies migrations before starting the API, then starts both servers. Ctrl+C stops the frontend and API; stop the database separately with `npm run db:stop` (without deleting the volume).

- Application: http://localhost:5173
- API / OpenAPI: http://127.0.0.1:8201/docs
- Liveness: http://127.0.0.1:8201/api/v1/health/live
- Readiness: http://127.0.0.1:8201/api/v1/health/ready

Readiness requires an available database and a current Alembic schema. The 503 response is correct when the database or migration is not ready; liveness may still return 200.

The local database has port 55432 and name `volleycrew_dev`. Data in `.env.example` and Compose is for development purposes only. An existing PostgreSQL server can be connected via `VOLLEYCREW_DATABASE_URL` in `.env`; use a separate database, not related to production or maybe-finance. Format: `postgresql+asyncpg://user:password@host:port/database`. Local development was also checked on isolated PostgreSQL 14.24; full regression on PostgreSQL 17 and production images of both architectures verified in E10.

## First organizer and access

After starting the local servers, generate an initialization link:

```sh
npm run auth:bootstrap
```

Open the listed address `/setup#…` in your browser and set the login and password yourself (8-128 characters). The link works once for 30 minutes. When it expires, `npm run auth:bootstrap -- --rotate` will invalidate the old one and generate a new one. After creating an administrator, the command refuses to reinitialize. There is no default password or production account seeded with test data.

In „Mój profil” → „Ustawienia ekipy”, the organizer creates an invitation link, revokes it, issues one-time password reset links, changes private priority status, and blocks access. A new profile is always a guest; another device requires entering a login and password. We only show the link in its entirety once it has been created - please copy it before leaving the view. When changing/resetting the password, other devices lose their sessions.

Local settings: `VOLLEYCREW_PUBLIC_URL=http://localhost:5173`, `VOLLEYCREW_COOKIE_SECURE=false`. Apart from localhost, HTTPS is required and default Secure=true. The CSRF signing secret is generated in `.runtime/auth.key` with rights 0600; save it between reboots or specify `VOLLEYCREW_SESSION_SECRET` (min. 32 characters) via the environment. Don't add it to the repository. Proxy traffic is untrusted by default; `VOLLEYCREW_TRUSTED_PROXY_CIDRS` and `VOLLEYCREW_ADDITIONAL_ORIGINS` are explicit JSON lists for configuration and checking in E10. Uvicorn works with `--no-proxy-headers`, verification is performed by the application.

## Calendar and meeting occurrences

After logging in, the next meeting is fetched from the schedule. In the calendar, select the month with the arrows or the „Miesiąc” field, then open the meeting. The details URL works after a refresh. Opening it does not enroll you; declare your participation using the separate „Będę”/„Nie będę”. The organizer changes the schedule in the settings or a single date in the meeting details. The default rule is Tuesday 18:00–20:00, I LO in Gdańsk, Europe/Warsaw. History contains only persisted meetings.

Changing a recurring rule requires a preview and separate confirmation. It moves existing occurrences within the same week, preserves individual exceptions and cancellations, and includes future meetings that have not yet been materialized. After a date change, confirm participation again: your existing seat remains reserved without an automatic timeout. The organizer can release it manually. Old waitlist offers become invalid; a new offer requires explicit acceptance.

When the list is full, you are placed on the waitlist. The vacant place is reserved for the first person in the queue, and the organizer activates the offer and manually notifies you on Messenger. Only „Przyjmuję miejsce” confirms participation. The organizer may pass on the place with confirmation; there is no automatic timeout. The cancellation shows information about the 24-hour limit and possible late offer exception. Locking your profile frees up future spots and reservations, preserving your history.

## Managing a meeting at the venue (E6)

In the meeting details, the organizer marks attendance and records the draft, then separately approves the verified list. The approval is available from the start of the game. Absentees receive a private history entry, and their places are transferred to waitlist management. The physically present recipient of the reservation can be confirmed at the venue. Adding another existing profile requires free, unreserved space; returning a previously marked absentee requires corrections with the reason.

After confirming attendance, choose random or balanced teams. On the court, tap a player and then a player from the other team to swap them - including when both teams have seven players. The seventh player appears in the rotation area below the court. Save manual corrections and confirm lineups; only then will the team see them. Opening for correction requires a reason. The split supports 2–14 attendees, at most 7 per side and a difference of at most 1 player. It uses current ELO ratings. The PDF list is available after attendance confirmation, and the next panel step records the result.

Your own private history is in your profile, and the organizer opens another player's history from the team settings or attendance list. Corrections retain the source entry, author, date, and reason. Version conflict does not overwrite changes from another tab. On loss of response, use „Ponów tę operację” - repeating does not create another commit or draw.

## PDF Signature List (E7)

After confirming your attendance, select „Lista podpisów” in the organizer panel. You will see a PDF preview for the school and a „Pobierz aktualny PDF” button. The download always reads the current attendance, even after correction in another tab. Only people actually present are included in the list; there are no waitlists, nicknames, statuses or histories. Print on A4 paper at 100% scale. The usual list of 14 people fits on a page; extremely long names move to the next page without being cut off.

PDF is created locally by ReportLab with included Noto Sans fonts and license in `backend/app/assets/fonts/`. PDF.js renders the preview on the phone without an external service/CDN. Poppler is only used for visual control during development and is not a runtime dependency of the application. No new database migration is needed.

## ELO Score and Ranking (E8)

After confirming the teams, go to „03 Wynik”, enter the A/B sets, show the points preview and confirm the save separately. The result 0-0 ends the match with no sets played and no points for this match. Each team member, including the player in rotation, receives the same delta. K=32, expectation scale 400; the proportion of sets and the strength of the teams are important, so in a special case, a win below expectations may reduce the points.

„Ranking” shows all players, points and match history. Clicking on a name opens the history before → change → after. Values are shown to one decimal place, but calculations and database are not rounded this way.

„Skoryguj wynik lub składy” requires a reason and a new preview. Historical actual attendance can also be corrected: each person added/removed requires a separate private attendance correction with a reason. Old results/lineups are retained and the ranking is recalculated by match start and fixed ID, also for later matches. Reasons and attendance history are not public to the group. There is no need to save consecutive results in date order.

Migration `0007_results` adds results versions and ranking materialization; ELO snapshots use Numeric. Execute `npm run db:migrate` before running the new API. Downgrade after saving the results is blocked so as not to delete the history; backup/restore and update are described in the HA manual and the E10 report.

## Checks

```sh
npm run lint
npm run typecheck
npm run api:check
npm run test:backend
npm run test:frontend
npm run build
```

Without `VOLLEYCREW_TEST_DATABASE_URL`, backend tests skip PostgreSQL integration checks. To run them locally with Compose, create a test database once:

```sh
docker compose -f compose.dev.yaml exec db createdb -U volleycrew volleycrew_test
VOLLEYCREW_TEST_DATABASE_URL=postgresql+asyncpg://volleycrew:volleycrew_dev@127.0.0.1:55432/volleycrew_test npm run test:backend
```

Integration tests require a database name ending in `_test`, perform migration, remove test identity data, and check that the schema is current. Use only the dedicated test database. Never provide a production connection string.

Browser tests with a working local database (on port 55432 by default):

```sh
npm --prefix volleycrew/frontend exec -- playwright install chromium webkit
VOLLEYCREW_E2E_DATABASE_URL=postgresql+asyncpg://volleycrew:volleycrew_dev@127.0.0.1:55432/volleycrew_test npm run test:e2e
```

Playwright starts a separate API on port 8202 and Vite on port 5175, without reusing development servers. Requires explicit `VOLLEYCREW_E2E_DATABASE_URL` ending with `_test`. Seeder deletes the identity and calendar data of ONLY this database and creates a dummy admin, invitation, default rule, canceled date and full test lists for waitlist checking, and separate ongoing meetings for attendance and full teams. Do not run backend and E2E tests simultaneously on the same database. The tests cover registration, session remembering, masked login, profile editing, reset, lock, desktop/mobile navigation and calendar and waitlist flow, schedule preview, reconfirmations, exception behavior and conflicts from a stale organizer tab, attendance confirmation, 7:7 split with rotation replacement, retry after loss of response, court publication and private history and correction, as well as PDF preview, downloading the list for 14 people, redownloading for 13 after correction and recovery after a network error, as well as saving/retrying the result, ranking, point history, full historical correction and closing 0:0. E9 adds controls for axe-core, touch targets and width, network/session loss, unsaved field retention, and mobile keyboard geometry. Projects `desktop` and `mobile` use Chromium, `webkit` the WebKit engine; this does not replace physical Android/iOS testing. Registration scenarios have isolated limit counters in the test database, without changing application limits. Results and screenshots: `volleycrew/frontend/test-results/` (ignored in git). `PLAYWRIGHT_BROWSERS_PATH` can point to browsers' own location; use the same setting for installation and testing.

## API contract and formatting

After changing endpoints or DTO:

```sh
npm run api:generate
npm run api:check
```

The exporter imports the application without starting the database. The source of the contract is FastAPI; commit includes `frontend/openapi.json` and generated `src/lib/api/schema.d.ts`. The frontend uses the openapi-fetch client and these types. Do not edit the generated files manually.

`npm run format` formats Python and frontend code. Node is used for building, the target runtime will serve static `frontend/dist` via Nginx. `npm --prefix volleycrew/frontend run preview` shows only static build; production API proxy and HA package provided by E10.

## CI and Home Assistant

`.github/workflows/checks.yml` defines installation with lockfile, lint, types, contract API, backend tests with PostgreSQL 17, frontend tests, build and E2E Chromium/WebKit. It does not publish the image or deploy the application. The workflow needs to actually run after the code is pushed; local testing does not mean green CI.

E10 provides an installable HA manifest, Dockerfile/s6/Nginx, Ingress, container startup migrations, and local checking of both architectures. The final acceptance testing requires independent installation on HA, checking physical phones and copies outside the host. Don't store secrets in a repository; production requires separate PostgreSQL and proper HTTPS/proxy configuration.

## Visual prototype

The prototype remains a separate reference with fictitious data. Does not follow full production rules; the source of the findings are the plan documents. Option A was accepted, B/C was retained for comparison.

```sh
npm run prototype
```

- http://localhost:4173/prototype/?variant=A
- http://localhost:4173/prototype/phone.html - interactive preview in the phone frame

In the prototype, changes disappear after refreshing. Don't use a real password. The player/organizer switch is a demonstration, not an authorization mechanism.

## Installing Home Assistant (E10)

The package is in `volleycrew/`, the repository manifest is in `repository.yaml`. Home Assistant builds the application locally with Dockerfile, just like maybe-finance; A prebuilt Volleycrew image in GHCR is not required. [Installation, options, administrator token and backup/restore instructions](volleycrew/DOCS.md). The user publishes/adds the repository and installs the application himself; Code that exists only locally is not available in the HA store.

Local production build on ARM64:

```sh
docker build --platform linux/arm64 --build-arg BUILD_ARCH=aarch64 -t volleycrew:e10-arm64 volleycrew
```

For `amd64`, select `--platform linux/amd64 --build-arg BUILD_ARCH=amd64`. The Debian base image in Dockerfile is pinned to the multiarch index digest; Docker chooses the right architecture. Since 0.1.1 there is no `build.yaml`, and `BUILD_FROM` passed by Supervisor does not change the base image. CI builds with the Alpine fallback parameter from the HA log to check resistance to this replacement.

Production image test (requires Docker, `openssl`, Node and Playwright browsers; creates/deletes only its own test containers, network and volumes):

```sh
python3 scripts/test_container.py --image volleycrew:e10-arm64 --platform linux/arm64
```

The test reserves local ports 18200, 18099, 18443 and 18543 and a separate test network. Checks for starting from empty PostgreSQL 17, misconfiguration/DB/migration, HTTPS, two Ingress prefixes, cookies/CSRF, restart, pre-update backup, full meet cycle, PDF in Chromium/WebKit and restore on the second server. `--backend-tests` adds the entire backend regression on a separate PostgreSQL 17 database in this environment; also requires local `npm run setup`. Do not run two of these tests at the same time. This is not a test of the physical HA/Pi or off-host copy.

Production Python dependencies are additionally exported to hashed `backend/requirements.lock`, used by Dockerfile:

```sh
uv export --project volleycrew/backend --frozen --no-dev --format requirements-txt --no-header --no-annotate --output-file volleycrew/backend/requirements.lock
```

CI verifies compliance of this file with `uv.lock`, builds and tests both CPUs without publishing the image. Simply adding a workflow does not mean remote CI has been completed.

### Local preview of both roles

`npm run dev:preview` creates 14 accounts in the local database `*_dev`: **Admin Demo**, **User Demo** and 12 demo players, with the password `Preview-test-password-123` (logins `admin-demo` and `user-demo` for the switch), and runs the application with the buttons „Wejdź jako Admin” / „Wejdź jako User”. The buttons work on the login screen and above the app content using the regular login API. Seeder fills in missing logins/passwords of known demo accounts after PIN migration, preserving their IDs, data and existing passwords; does not change other profiles. Seeder refuses to work with the database outside of loopback or without the `_dev` suffix; does not delete existing profiles. The regular `npm run dev` and the production build do not show the switch.
