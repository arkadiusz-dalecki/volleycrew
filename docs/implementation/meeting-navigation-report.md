# E3/E9 - Gesture navigation between meetings

Commissioned and implemented on 2026-11-11. Branch `feat/meeting-swipe-navigation`.

On the main screen and in details, a gesture to the left goes to the next meeting, to the right to the previous one. „Poprzednie” / „Następne” buttons provide the same action for mouse, keyboard and screen reader. The gesture requires a single finger, a movement of at least 60 px, a horizontal axis advantage and a time of less than a second. Vertical scrolling, controls/forms, dialogs, cancels, and multi-finger gestures do not trigger the transition.

New read `/api/v1/meetings/adjacent` returns nearest neighbors by current start and ID, without month/year limitation. Includes persistent history, references, offsets, deletion markers, and enumerated unfinished meeting occurrences of active series. Does not create meetings; moving to a virtual date uses the existing `resolve`, without declaration of participation. OpenAPI contract and TypeScript client generated together. No new migrations. At the request of the user, the package version was upgraded from 0.3.2 to 0.3.3; standard update after backup.

## Local verification

- PostgreSQL 17: separate temporary instance on port 55439, `volleycrew_swipe_test` only. `pytest volleycrew/backend/tests/test_meetings.py -q`: 9 passed. New cases: both sides, no neighbor, year limit, DST (167 h between Tuesdays), multi-year break, end of series, same start and ID order, reference/delete/move, read without persistence, time zone authorization and validation.
- `npm run test:e2e -- e2e/meeting-navigation.spec.ts e2e/calendar.spec.ts e2e/ui.spec.ts`: 20 passed, 1 intentionally skipped (mobile keyboard on desktop). Chromium desktop/mobile and WebKit: navigation, gestures ignored, no declaration mutations, address refresh, read and retry error, geometry, contrast and touch targets. 360/390/430/768/1440 px width control in existing UI matrix.
- Final repeat `meeting-navigation.spec.ts`: 3 passed, including native Chromium touch events via CDP on mobile project; the remaining cases use TouchEvents in the browser.
- `npm run lint`, `npm run typecheck`, `npm run api:check`, `npm run test:frontend` (4 tests), `npm run build`, `git diff --check`: passed.
- Playwright screenshots in ignored `volleycrew/frontend/test-results/`; mobile view visually checked.

## Other dependencies

Status before PR publication: local inspections passed; remote CI results will be available in PR. Home Assistant installation and gesture acceptance testing have not been performed on a physical iPhone/Android. HA image tests were not run (API/UI change without infrastructure). Another acceptance testing: gestures on physical phones, especially at the edges of the screen where the browser/system can handle its own navigation.

## Test synchronization after first CI

The first CI trace showed that the URL was changing before the new encounter had finished rendering. When the previous screen also had the „Poprzednie” button active, the test sent a return gesture to the old component before new neighbors were downloaded. Added the ID of the displayed meeting on the container and waiting for that specific screen before the next gesture. Assertions of exact addresses and no changes to declarations have been maintained.

## Delayed 401 after logout

The second CI pass revealed an existing race condition: the administrative read 401 response arrived after logging out and mounting the profile list, and the global handler removed the new public query from the cache. The list remained in the loading state despite the 200 response. Added controlled test `auth-races.spec.ts` reproduced the error locally (1 failed before fix). The handler now ignores the event if there is no logged session; clearing the private data of the active session remains unchanged.

Post-fix: `auth-races.spec.ts`, `mobile-improvements.spec.ts` and `meeting-navigation.spec.ts` - 21 passed in Chromium desktop/mobile and WebKit. Lint, types, build and diff-check passed again.

## Seamless tile - addition 2026-11-11

Branch `feat/meeting-card-animation`, continuation of E3/E9 requested by the user. The entire meeting card (date, status, participation and personal calendar) follows your finger. The gesture starts on a card outside the controls; other sections do not start navigation. Short/cancelled gesture returns smoothly to zero; the lack of a neighbor limits the displacement and gives a feeling of resistance. The full gesture and buttons trigger an exit in the navigation direction (220 ms), and a new tile enters from the opposite side (300 ms). Vertical scrolling and previous gesture protections remain.

We fetch the persistent meeting details before the exit animation, even when they are already in the cache. The virtual term still uses resolve. The error preserves the current tab and undoes the swipe. During the transition, the data is cached, so there is no intermediate loading screen. `prefers-reduced-motion: reduce` disables panning and animations. No API changes or migrations. At the request of the user, the package version was upgraded from 0.3.3 to 0.3.4; standard HA update after backup.

Local verification:

- Separate PostgreSQL 17 on 55439, database `volleycrew_swipe_test`; the tests did not use the development or production database.
- `npm run test:e2e -- e2e/meeting-navigation.spec.ts e2e/calendar.spec.ts`: 6 passed (Chromium desktop/mobile and WebKit). Tile position control during movement and after short gesture, native Chromium touch, both directions, buttons, scroll/gestures ignored, detail and neighbor errors, retry, limited motion mode, declaration behavior and no horizontal overflow.
- Lint, typecheck, build, 4 existing frontend tests and `git diff --check`: passed.
- Mobile screenshot during the gesture checked visually; files in ignored `volleycrew/frontend/test-results/`.

PR publication and full CI ordered in the next step; results for the final commit will be available in PR. Home Assistant deployment was not performed. The feel of animations and gestures on a physical iPhone/Android is subject to acceptance testing. No backend or infrastructure changes; their full test suites were not run.
