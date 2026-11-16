# E2/E9 - Mobile fixes, login and installation

Date: 2026-11-08. HA package version: **0.3.1** (fixed after 0.3.0). Scope: four notes with screenshots and admin view switch, without deployment on HA.

## Criteria met

- Single meeting form: removed default fieldset frame, limited control widths and adjusted Safari's native date/time fields; one column on the phone.
- The indicated caption under the heading of the next meeting has been removed.
- Login: native select from „Wybierz użytkownika” on new device. Masking of names and nicknames preserved. The remembered ID comes from a successful authentication or active session; profile disappearance restores an empty option. The PIN does not go to permanent memory.
- „Administrator / Użytkownik” switch also visible on the phone. The preview stays in your own account, shows the usual teams/score and hides the calendar, room, offers and settings management. Administrative routes are also hidden in the preview. Back to administrator is always available. The selection is remembered for the account within the browser session.
- „Dodaj aplikację do telefonu” button on access screens and in the footer after logging in. Uses `beforeinstallprompt` when available; shows other users the platform instructions in the accessible dialog. Hides after `appinstalled` and in standalone mode. The manifest has PNG 192/512 and the local Apple icon 180. The installation does not add data cache or offline enrollments.

## Verification

Local environment macOS arm64; isolated database `volleycrew_test` on 127.0.0.1:55432. Node 26.8.1, Playwright 1.65.0, Chromium desktop/mobile and mobile WebKit.

- `npm --prefix volleycrew/frontend run lint`: passed without warnings.
- `npm --prefix volleycrew/frontend run build`: passed (TypeScript and Vite).
- `npm --prefix volleycrew/frontend run test`: 1 test passed.
- `git diff --check`: passed.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm --prefix volleycrew/frontend run test:e2e`: full check run - 49 passed, 4 failed and 1 intentionally skipped (mobile keyboard on desktop). Three failures were due to the old radio selector in the session expiration test; the fourth detected no focus return after installation instructions in Safari. Selector adapted to select; the install button explicitly receives focus before opening the dialog.
- After fixes `npm --prefix volleycrew/frontend run test:e2e -- mobile-improvements.spec.ts ui.spec.ts`: **26 passed, 1 intentionally skipped**, no errors in all three projects. In total, all 53 active scenarios have a positive result in the full run or final repeat; no further complete run was performed.
- Viewed screenshots of the Chromium/WebKit form, login and installation instructions. The form was checked geometrically at 360/390/430 px; accessibility control and width of other routes also in 768/1440 px. Screenshots: `volleycrew/frontend/test-results/mobile-improvements-*/{calendar-fixed,install-help}.png` (generated, outside the repository).
- New E2E tests: empty/last/deleted profile, failed login without remembering, view switching and route shield, 360/390/430 form geometry, install prompt and button hide, and platform instructions and dialog focus.
- The first run of the preview test had an incorrect button name in the selector; corrected the selector to the existing „Dodaj spotkanie” and started the full set from scratch.

## Dependencies and acceptance testing

No new npm dependencies, migrations, or open decisions for this scope. The actual addition of the icon and booting from it on iPhone/Android requires acceptance testing on devices under the target HTTPS; emulation does not replace physical attempts. iOS does not provide an automatic installation page: the user must select Share → To Home Screen. The behavior follows from [Apple manual](https://support.apple.com/guide/iphone/open-as-web-app-iphea86e5236/27/ios/27); The prompt's accessibility is described by [MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeinstallprompt_event).

Next step: user acceptance testing of appearance and installation; the remaining E9/E10/E11 criteria continue according to the plan index. No publications or installations were performed on HA.

## CI fixes in PR #5

Two CI runs for the 42860cd revealed a left profile card selector in `container-tests/ingress.spec.ts`. Native select is not a clickable tab; tests of both CPUs stopped at logging in, despite successful startup, migration, HTTPS/Ingress, restart, pre-update backup and match cycle. The suite test now selects a profile by the select label and `selectOption`.

In the push process there was also a loss of a new session during login/logout. The new `e2e/auth-races.spec.ts` test delays the anonymous `/me` response until after a successful login. Before the fix, the test deterministically returned to the login (no meeting header after the response was released). Login now cancels previous requests and clears previous account data before publishing a new session, just like registration/reset. The middleware ignores the `401` canceled request and the expiration handler does not clear the session overwritten while waiting for cancellation.

Local lint, unit and build: passed. `auth-races.spec.ts auth.spec.ts mobile-improvements.spec.ts ui.spec.ts`: **32 passed, 1 intentionally skipped**, Chromium desktop/mobile and WebKit. The new CI is the correct evidence for both CPU packages.
