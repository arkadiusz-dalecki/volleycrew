# E2 - Sessions, PIN and invitations

Date: 2026-11-06. Status: local implementation, acceptance testing of E2 functions confirmed by tests described below. Without production deployment and without creating an actual Arkadiusz account. The code was not pushed; project files are still local.

## Scope and acceptance testing

| Criterion E2                            | Implementation / proof                                                                                                                                                                                                    |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| First administrator without default PIN | The operator generates a one-time CLI link, the administrator selects the PIN in `/setup#token`; 30 minutes, closing after the first admin account; expiration and concurrent use test                                    |
| Registration only by active invitation  | Multiple random link, invalidation; new profile always guest/player; additional status/role fields are discarded; PostgreSQL and UI integration                                                                           |
| Chooser profile and privacy             | The backend returns only ID, first name, masked last name and nickname; always five stars, also short/Polish surnames; full names don't go into anonymous JSON and DOM                                                    |
| Remembered device and new device        | HttpOnly session cookie, random token, DB hash; 30 days of inactivity / max. 180 days; refresh preserves the session, new device requires PIN                                                                             |
| Change and reset PIN                    | Current PIN required when changing; one-time reset 30 minutes; a newer grant invalidates an older one; all old sessions expire; current device gets new                                                                   |
| Permanently restrict attempts           | 5 incorrect PINs/profile/15 min, then 429 from Retry-After to the end of the window; separately 30/source; API restart test and window retries; without permanent blocking                                                |
| Authorization / blocking                | Each administrative endpoint checks the role; the block invalidates sessions and grants, hides the profile in the directory and prevents login; unlocking does not restore old sessions; account and audit details remain |
| CSRF and no secrets in reading          | origin + signed session token + cookie/header; all mutations, including anonymous ones; token hashes and Argon2id, no-store; tests for bad origin, missing token, different session token and cookie flags                |
| UI A on the phone                       | Registration, login, profile/PIN and administrator settings; access to settings also from the mobile profile; loading/error/retry, block confirmation, copying links                                                      |

`0002_auth` migration creates players, auth_sessions, invites, pin_reset_grants, bootstrap_grants, auth_throttles and audit_events. Identity mutations are serialized with PostgreSQL's transactional advisory lock. This is a consciously simple choice for one small group, and also limits parallel hashing on the Pi. It does not rely on process memory. The status field and administrator permissions remain separated.

## Local verification

Environment: macOS arm64, Python 3.13.18, PostgreSQL 14.24 on isolated port 55432. Only dedicated database `volleycrew_test`; dev remains separate. Chromium 158 (Playwright, desktop 1440×1000 and Pixel 7 emulation 390×844). Emulation does not mean testing on a physical phone or Safari.

- `npm run lint` - correct (Ruff, ESLint, Prettier).
- `npm run typecheck` - correct.
- `npm run api:check` - correct, OpenAPI contract and types compatible.
- `VOLLEYCREW_TEST_DATABASE_URL=<separate *_test database> npm run test:backend` - 20 tests passed including actual PostgreSQL, controlled clock and concurrent bootstrap/reset. One Starlette library warning about future TestClient transport change; no test error.
- `npm run test:frontend` - 1 Vitest passed; E2 root paths are checked by the browser.
- `npm run build` - correct React/Vite production build.
- `VOLLEYCREW_E2E_DATABASE_URL=<separate *_test database> npm run test:e2e` - 4 desktop/mobile tests: full registration, session remembering, login privacy, profile, reset, lock, rejected invitation and navigation and reload. 8202/5175 test servers, without using dev.

Screenshots in the ignored `volleycrew/frontend/test-results/`: `profile.png`, `login.png`, `admin.png`, `meeting.png` in the directories of a given test project. Visually checked the login, profile and organizer settings screen; automatic horizontal overflow control also includes organizer settings. Tests detected a UI refresh error after logout; query memory invalidation has been improved and the path is covered by E2E.

## Other dependencies

- E4 must attach the release of future enrollments, reservations and offers to a profile lock in the same transaction, with a common lock order. Meeting models do not exist yet, so E2 does not declare acceptance testing of the entire D6 in terms of enrollments. Add race test lock/report/accept offer.
- Administrative change of priority status awaits E4: it must recalculate seats according to D3, without circumventing their rules. E2 gives you a private status reading and a safe default guest.
- PostgreSQL 17 in CI/Compose, images of both CPUs and HA installation still not done. CI configuration modified, but local launch is not proof of green workflow.
- E10: origin/proxy configuration, dynamic ingress prefix and cookie in iframe, persistent key in `/data`, Argon2/RAM/time measurement on Pi 4, backup and restore. The user configures the tunnel himself.
- The first real account is created by the user via `npm run auth:bootstrap`. Seeder E2E refuses to work on a database without the `_test` suffix.

Next ready task after the order: **E3 - meeting models and calendar**.
