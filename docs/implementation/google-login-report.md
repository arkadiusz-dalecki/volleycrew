# E2/E9 - Optional Google Login

Update: Google sign-up by invitation and passwordless account expands the scope described. Final status and results: [Google registration report](google-registration-report.md).

Date: 2026-11-15. Branch `feat/google-login`, base `1962d88` (main after #10). Scope: additional Google for existing profiles, without opening registration. Local results below; current image status and GitHub Actions in PR. Without HA deployment or using real Google accounts.

Update: current PR replaces PIN with login and password; the old evidence below describes the first version of integration. Current Google Confirmations require a password. Final verification and organizer procedure: [login and password report](password-login-report.md).

## Behavior and criteria

| Criterion                          | Implementation and proof                                                                                                                                                                                                                                                                                                                                  |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Connecting your own profile        | Active session and fresh PIN; one-time flow binds the exact session, browser and nonce. After external I/O, the session and profile lock are checked again. PostgreSQL and signed tokens in tests.                                                                                                                                                        |
| Login without duplicating profiles | Only the unique Google `sub` with a valid ID token indicates an already existing player. An unlinked account does not register a profile. The role and priority remain in the DB.                                                                                                                                                                         |
| OIDC and security                  | Authlib authorization code + PKCE S256; PyJWT RS256/JWKS, issuer, aud, exp/iat, azp and nonce. The JWKS cache respects the shorter Cache-Control and is limited to 300 s. One-time state, 10 minutes, associated with the Secure/HttpOnly/Lax cookie with the __Host prefix. Signature, claims, replay, expiration, other browsers and competition tests. |
| No DB lock during Google I/O       | Short flow consumption in the transaction before exchanging the code; after commit, the connection and shared lock are released to external I/O. Re-serialized check before binding/session.                                                                                                                                                              |
| Disconnect and recovery            | Disconnecting requires a PIN, deletes the connection, invalidates sessions/pending connections, and issues a fresh session to the current device. PIN reset from the organizer removes Google; changing the PIN yourself retains it. Real session and reset tests.                                                                                        |
| Interface and HA                   | Google button on entry and own profile section; clear errors, cancellation, connection status, return to desired internal route. Ingress opens PUBLIC_URL in a new tab without moving the session. Ingress isolation tests in API and components.                                                                                                         |
| Configuration and privacy          | Optional pair GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET; lack of pair disables Google, incomplete pair is rejected. Private s6 files with rights 0600. Scope openid; no email storage and access/refresh/ID tokens. We don't show Google sub in API.                                                                                                          |
| Monitoring and abuse               | Start limit 60/source/15 min in PG, existing POST gate and separate callback gate. A rejected callback returns to a blank screen. Result logs are source-fingerprinted and have fixed codes, no secrets. Nginx skips URI/query, access log Uvicorn is also disabled in dev; HTTPX/httpcore have WARNING.                                                  |

Google runs under the constant PUBLIC_URL. Ingress is not an alternative callback; the user can use a separate session under the main domain. The PIN and invites remain available, so simply adding Google does not address the weakness of the admin PIN or override the other recommendations in the review.

## Migration and update

`0011_google_login` migration adds `google_identities` (unique profile and sub binding) and `google_flows` (hashes, linking session, internal return target, dates). Does not change existing profiles/PINs. Regular copy required before upgrading. The fresh migration and downgrade/upgrade test confirms the preservation of profiles and PIN login; downgrade removes google and flow associations. When rolling back an image, the existing compatible schema and backup procedure applies, not just running the old image on the new migration head. The package version was not changed.

The backend uses lock-pinned Authlib 1.9.6, HTTPX 0.28.1 and PyJWT 2.15.1 with cryptography 50.0.2. Production requirements.lock checked against UV export. The frontend uses the local official G icon and Google Sans (2240 ​​byte subset, SIL OFL); sources and license in public/. No external GIS script or fonts downloaded in runtime.

## Local verification

macOS arm64, Python 3.13.18, PostgreSQL 17.11, Node 26.8.1; separate temporary database `volleycrew_google_test` on 127.0.0.1:59643. Backend and E2E kits run sequentially, without database development/production.

- `.venv/bin/python -m pytest -q --tb=short` from backend directory and isolated VOLLEYCREW_TEST_DATABASE_URL - **181 passed**. Includes real PostgreSQL, fresh and return migrations, sessions and competitions, and RSA signed tokens via real Authlib/PyJWT code; only Google's HTTPS transport is replaced.
- `npm run lint`, `npm run typecheck`, `npm run api:generate`, `npm run api:check`, `npm run test:frontend`, `npm run build` - passed; **8 frontend unit tests** including separate ingress links and no session copying.
- Dedicated `npm --prefix volleycrew/frontend run test:google` - Final pass **6 passes** (22.3 sec) in desktop/mobile/WebKit. Screenshots of the login and profile screens were checked visually; are not added to the repository. The test provider signs the RSA, checks the PKCE, and guides the browser through the actual callback/session. The test backend module refuses to operate outside the isolated database *_test and local URL; it doesn't go to the production image and there is no flag to activate it in the application.
- Full `npm run test:e2e` with Google disabled by default - **83 passed, 1 intentionally skipped on desktop**; the final Playwright save has a passed status and an empty failedTests list.
- First CI build revealed no exclusion of new Playwright files in `.dockerignore` (missing common fixtures/config in image context). Added Google exclusions analogous to existing E2E; local build with filtered context confirms the fix.
- Added a dedicated Google test for CI and smoke RS256 with bad audience rejection in real images of both CPUs. Local Docker is unavailable; the result of the images will be in PR.

There are two warnings in the repository about a future HTTPX → HTTPX2 migration (Starlette TestClient and Authlib integration). Warnings and assertions were not disabled. The parameters of the existing PIN protection have not been loosened.

## Sources and operator acceptance testing

- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), [Google discovery](https://accounts.google.com/.well-known/openid-configuration) - reading 2026-11-15 confirmed endpoints, S256 and client_secret_post.
- [Authlib HTTP clients](https://docs.authlib.org/en/stable/oauth2/client/http/index.html), [PyJWT](https://pyjwt.readthedocs.io/en/stable/usage.html), [Google branding](https://developers.google.com/identity/branding-guidelines).
- [Google Operator's Manual](../../volleycrew/DOCS.md#optional-google-login).

All that remains is the configuration of your own Google client (ID and secret entered in HA, registered callback), an attempt with a real account and a physical phone/HA, including the behavior of the installed PWA. Local tests with your own issuer do not constitute Google Console acceptance testing or consent screen publications. Next step: PR/CI review, then independent configuration and operator acceptance testing.
