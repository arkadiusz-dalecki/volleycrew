# E9 - Option A integration and interface resilience

Date: 2026-11-07. Status: local implementation and verification; full E9 acceptance testing remains open to tests on physical phones and visual comparison acceptance. No commit, publication or HA deployment.

## Changes

- Preserved variant A: light background, green header, tabs, four tabs on the phone and side navigation on the desktop. Improved contrast of descriptions, navigation, court and canceled meeting. Common text, surface, focus, and safe-bottom tokens; local DM Sans/Manrope fonts with Polish characters.
- Mobile header has more space for text. The calendar at 360 px accommodates 44 px touch targets. Selection controls also have the correct height in WebKit, while maintaining the native option selector.
- Common native `ConfirmDialog` for cancellation, offer transfer, profile lock and appointment change/cancellation. Named Dialog, Inactive Background, Escape/Cancel, Focus Return, Low View Scroll. Opening with a button also sets focus in WebKit; when the button is removed, the focus returns to the main content. Canceling the reschedule preview preserves the form.
- Court retains full names and rotation. The accessible name of the button is output from the content along with the nickname; decorative initials and arrows are not read. Route transitions set the document title and content focus; the nested points history keeps the ranking tab active.
- A temporary session check error preserves the open screen and form data instead of dismantling the application. The attendance panel, result editor, history with corrections and schedule retain forms when refreshing already downloaded data fails, with a message about outdated reading.
- No network has an explicit message; a failed save retains fields and requires manual retries. The network `TypeError` has a message in Polish. Session refresh error has a retry button. Confirmed session expiration deletes private data; relogging returns to the requested internal route. After logging out of your profile, logging in again also returns you to your profile; entering without a memorized route leads to a meeting.
- Bottom navigation uses safe area. `visualViewport` and the active field control its hiding when the keyboard is detected; fields are 16 px on phone and scroll spacing. The geometry test does not replace attempts with the system keyboard.
- Manifest and local SVG icon for site installation, no service worker, offline queue or private response cache. Icon license included. The installation and icon behavior on specific iOS remains to be verified. The prototype, variant switcher and demo data are not part of `dist/`.

## Acceptance testing

| Criterion                              | Result/proof                                                                                                                                                                                                                                                                             |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Integration of all stages              | Real API/PostgreSQL: registration, sessions, calendar, declarations/waitlist, rescheduling, attendance, teams, PDF, results and corrections ELO                                                                                                                                          |
| Sizes and no horizontal scrolling      | Main screens 360/390/430/768/1440 px; court, ranking and PDF additionally in the full venue path. Measuring document width, control geometry and screenshots                                                                                                                             |
| Accessibility                          | axe-core: main routes, login/registration/reset, dialog, court, PDF and result preview. Keyboard/focus control, 44 × 44 px targets and short dialog view. The axe result applies to the checked states; is not a WCAG certification or a screen reader test                              |
| Network/session                        | Offline when saving a profile: fields remain, no automatic saving occurs when the network returns. Session and result refresh error preserves draft. Actual 401 after deleting cookie → login → return to profile. Loss of response after saving lineups/result checked against real API |
| Comparison with A                      | Prepared below; user acceptance **pending**                                                                                                                                                                                                                                              |
| Physical Chrome Android and Safari iOS | **Not completed**. There is no attempt environment available on physical phones in this session. The emulation below does not close this criterion                                                                                                                                       |
| HA / Ingress / backup                  | E10; without declaration of production readiness                                                                                                                                                                                                                                         |

## Environment and playback

macOS arm64; Python 3.13.18; PostgreSQL 14.24 on port 55432, single-use database `volleycrew_test` only. Without production and maybe-finance. Playwright: Chromium **158.0.8127.18**, desktop and Pixel 7 profile; WebKit **27.2**, iPhone 13 profile. Emulation profiles do not represent physical devices or Safari test running a specific iOS version.

Playwright has three projects: `desktop`, `mobile`, `webkit`. CI installs Chromium and WebKit; remote CI launch still not done. Seeder provides separate matches for projects and schedule changes have separate years. Registration scenarios only reset `auth_throttles` in the database ending with `_test` so that a common proxy IP address does not connect independent attempts. Production limits have not been relaxed; their behavior remains covered by backend testing.

- `npm run lint` - Ruff/format Python, ESLint and Prettier: correct.
- `npm run typecheck`, `npm run api:check`, `npm run build` - correct. Build includes manifest/icon and local fonts, no `prototype/`.
- `npm run test:frontend` - **1 Vitest passed**.
- `VOLLEYCREW_TEST_DATABASE_URL=<jednorazowa baza *_test> npm run test:backend -- -x --tb=short` - **107 passes**, 36.58 sec. One early Starlette/TestClient dependency warning.
- `VOLLEYCREW_E2E_DATABASE_URL=<jednorazowa baza *_test> npm --prefix volleycrew/frontend run test:e2e -- --reporter=line` — **32 passed, 1 intentionally skipped**, 2.4 min. Only the mobile keyboard geometry scenario is omitted in the desktop design; the same scenario goes through in both mobile projects. No failed tests in the final run.
- `e2e-reset-limits` from the URL of the development database without the `_test` extension - expected refusal before connection and data change (exit 1). Protection of new test operation verified.

Backend and E2E tests were performed consecutively, without using the same database at the same time. Current session logs: ignored `.runtime/e9/{e2e-final,backend,build}.log`. No remote CI or HA image was launched. No open product resolution was needed for E9 changes.

## Comparison to overview

The palette, typography, navigation and court layout from variant A have been retained. The differences are due to real-world features: separate draft and presence approval, seventh person rotation, full corrections, priority privacy, error states and real ranking data. The prototype does not serve as a definition of backend rules. Images are derived from fictitious data only.

| View              | Prototype A                                | Working application                                                       |
| ----------------- | ------------------------------------------ | ------------------------------------------------------------------------- |
| Telephone, 390 px | [Reference](assets/e9/reference-phone.png) | [Meeting](assets/e9/app-phone.png)                                        |
| Court, 390 px     | [Reference](assets/e9/reference-court.png) | [14 people with rotation and long surname](assets/e9/app-court-phone.png) |
| Desktop, 1440 px  | `prototype/index.html?variant=A`           | [Meeting](assets/e9/app-desktop.png)                                      |

Application screenshots: Chromium/Pixel 7 and desktop. Number of people, meeting occurrences, nicknames and points are fictitious test data, different from the prototype. Full mobile screenshots also include content below the first screen; bottom navigation is fixed at the current view position. The remaining screenshots (360/430 px, calendar, ranking, PDF, WebKit) are played by E2E in the ignored `volleycrew/frontend/test-results/`.

**User acceptance of this comparison: pending.**

## Test on the phone - to be completed

| Device/system/browser version                        | Result  |
| ---------------------------------------------------- | ------- |
| Android + Chrome (enter model and versions)          | Waiting |
| iPhone + Safari (enter model and iOS/Safari version) | Waiting |

On both devices go: invitation → registration → enrollments and waitlist → re-entry with session; as organizer attendance → split/substitution on court with long name → PDF → result and ranking. Open PIN/nickname/result on the on-screen keyboard, scroll to action, check bottom navigation and safe area vertically/horizontally. Check for low dialog, cancel, network loss, return to application, session expiry, PDF download and add to home screen. Save versions and noticed issues, without PINs, invite links and private histories in the report.

Next implementation scope: **E10 - Home Assistant package**, images, Ingress, migrations/start, Pi 4 aarch64 and backup/restore. Open E9 acceptance testing points remain public when transferred to E10.
