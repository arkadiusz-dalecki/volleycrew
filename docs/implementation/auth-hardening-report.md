# E2/E9 - links, monitoring and abuse resistance

Date: 2026-11-14. Scope requested after login review: point 5 of final priorities. Branch `feat/auth-link-hardening`, PR base `e060c47` (main after merge #9). Local implementation report; the current CI result is in PR. Without deployment.

## Behavior

- Invite, bootstrap and reset links read the fragment into page memory and replace the current history entry with the address without the secret/query. The Ingress prefix and the technical router state are preserved. The token is not stored in localStorage/sessionStorage. Refreshing requires reopening the original link; The UI explains this behavior. Clearing the address uses the History API to not compete with the login transition.
- Old tokens in the path are no longer used for authentication; routes redirect to a blank form with full link information. Current links `#…` still work, opening them does not consume grants.
- HTTP 429 displays `Retry-After` as wait time in seconds. Mutations are not automatically repeated.
- Additional ASGI limiter works before reading body, DB and Argon2 for four input operations. Per-source budget: burst of 10, replenished at 30/min; global budget: burst of 20, replenished at 4/s. Source state is limited to 1024 entries. Other operations, including declarations and health, do not use this gateway. PostgreSQL persistent limits remain unchanged.
- Limited `volleycrew.security` logs record UTC time, result type, operation and source HMAC fingerprint. They do not read/log body, PIN, token, cookies, full URL, profile or name. Maximum of 60 events/min/process and one marker to skip further entries.
- The HA manual explains event interpretation, telemetry limitations, common proxy/ingress source and the need to protect the tunnel from connection flooding.

The DTO and database schema were not changed; no migration. PIN, admin role, login list, session validity and multiple invites are outside this scope. The package version was not upgraded.

## Verification

Environment: macOS arm64, Python 3.13.18, separate temporary PostgreSQL 17.11 on port 59583, database `volleycrew_hardening_test`. Backend and E2E performed sequentially. Node 26.8.1, Playwright Chromium 158.0.8127.18 and WebKit 27.2 browsers, desktop/mobile/webkit projects. No development or production database was used.

- Backend: `.venv/bin/python -m pytest -q` with `VOLLEYCREW_TEST_DATABASE_URL` pointing only to the above database, from the backend directory - **155 passed**. Includes real PostgreSQL, legacy sessions and limits, concurrent resets/bootstrap, and new limiter and telemetry cases.
- After final UTC time change in logs: `pytest tests/test_auth.py tests/test_auth_protection.py tests/test_security.py -q` from backend directory - **18 passed**.
- New timer-controlled tests check for budget renewals, shared multi-source limit, memory limit, no body read/further API call after discard, ingress prefix and log limit. Integration checks the results of operations and the lack of secrets in telemetry.
- `npm run lint`, `npm run typecheck`, `npm run api:check` - passed.
- `npm run test:frontend` - **6 passed**, including valid, missing and invalid Retry-After.
- `npm run build` - passed also after the final History API fix.
- `npm run test:e2e -- auth.spec.ts auth-links.spec.ts` with isolated `VOLLEYCREW_E2E_DATABASE_URL` - **9 passes**: full registration, login, profile, reset, lock, rejected invitation, clean address, no secret in storage, reload and reopen, reject tokens in path in Chromium/WebKit. The first pass revealed a router navigation conflict during a session change; it was corrected using the History API and confirmed with the full path.

- Full `npm run test:e2e` on the same isolated database, after backend testing - **83 passed, 1 intentionally skipped** (mobile keyboard on desktop project), 4.2 min. All desktop/mobile/webkit projects including session races, enrollments, waitlist, attendance, result, schedule, PDF and accessibility.
- `git diff --check` - passed.

Required local range E2/E9 met. Next task: separate acceptance testing E11 on physical phone/HA; other recommendations from the review require a separate order and decision.

## Limits of acceptance testing

No production image test: local Docker daemon is unavailable. The Nginx, s6 and Dockerfile configuration was not changed. The middleware test covers both prefixes, but does not replace acceptance testing of the image or production proxy/HA. During the local verification stage, no tests were performed on a physical phone, HA installation or publication. The PR requested later also runs amd64/aarch64 image tests in GitHub Actions; their current result is in PR. Logs do not send automatic alerts and are sampled at high traffic. The additional limiter assumes a single worker present; restarting only resets its memory, not permanent protection. A stronger admin login, rescue procedure, and change to the invite policy remain separate recommendations from the review.
