# Admin Calendar - E3/E5/E9 Report

Scope ordered on 2026-11-08; local implementation, no publication or installation in HA.

## Criteria met

- The date replaces the tagline as the main card heading; time and place remain below. Desktop/mobile screenshots control.
- Side menu retrieves the actual next appointment from the API, regardless of the open appointment; refreshing and error/missing deadline handling.
- Schedule management moved from settings to calendar and visible only to the administrator. Single meeting and weekly series forms with preview before signing up.
- You can select an empty calendar day and add an appointment. The backend protects access, version, future date, DST and collisions with persistent and calculated appointments.
- The from-to series replaces the schedule in the specified range, with an optional end. UI treats the last day inclusive; The API uses an exclusive date. Eventually, the previous rules return, and later persisted meetings retain IDs, dates and enrollments.
- The postponement of a single meeting remains in the details, available from the calendar. Previous reconfirmations, ordering, cancellations and exceptions retained. The new single match does not move when changing the series.
- Migration 0008 adds `Meeting.is_additional`, defaults to false for existing data. The new additional occurrence has a persistent record and an inactive source rule; without infinite record generation.

## Verification

Local environment macOS arm64, Python 3.13.18, PostgreSQL 14.24 (Homebrew) on 127.0.0.1:55432, only database `volleycrew_test`.

- `VOLLEYCREW_TEST_DATABASE_URL=…/volleycrew_test npm run test:backend`: **122 passed**. After adding night collision checks on the series boundary: `python3 scripts/dev.py test tests/test_schedule_changes.py`: **15 passed**.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm run test:e2e -- schedule.spec.ts calendar.spec.ts`: **9 passes** - desktop Chromium 1440, mobile Chromium 390 (calendar also 360/430), mobile WebKit 390. Adding a single appointment, series with end, previous rule return, offsets, reconfirmations, second tab conflict and cancellation.
- `npm run lint`, `npm run build`, `npm run test:frontend`, `npm run api:check`, `git diff --check`: passed.
- Playwright Screenshots: `volleycrew/frontend/test-results/schedule-calendar-organize-4bce4-and-a-bounded-weekly-series-{desktop,mobile,webkit}/{calendar-admin,meeting-date}.png`. Files generated, outside the repository; desktop/mobile views reviewed.

## Dependencies and further acceptance testing

No blocking decision for the implemented scope. Behavior adopted for a series: replacing the current schedule in the selected period, with the previous rule returning at the end. Multiple parallel weekly series have not been added; additional single meeting occurrences are independent. Standard backup and migration required before HA upgrade; installation is performed by the user. Appearance acceptance and testing on a physical phone in accordance with E9 remain; we do not replace them with emulation. Next step: acceptance testing of these changes by the user, then E11 according to the plan index.

## Addendum - two preview profiles

At the user's request, added `npm run dev:preview`: idempotent seed Admin Demo/User Demo in the local database `*_dev`, without deleting existing data. The login screen and application body show two buttons toggle the real session via API. The function requires Vite DEV and an explicit VITE_LOCAL_PREVIEW; production build removes buttons and demo account IDs. Checked the Admin → User → Admin transition in Chromium, proper calendar permissions, width 390 px without overflow, typecheck, lint and build. Local preview started on port 5173.

## Complementary - Calendar tile actions

The user ordered two buttons directly on the tile: „Zmień termin” and „Odwołaj”. The common MeetingActions component and existing API were used, without changing domain rules. The form expands on the tile; cancellation and registration of a new date require previous confirmations. The calculated date is saved only after selecting the action; there is no redirection to details. When the date changes, the filter/month is updated, and after saving, the calendar and the next meeting are refreshed. Actions are not visible to the player, completed and canceled matches.

Verification: typecheck, lint, build and 12 E2E calendar/schedule in desktop Chromium, mobile Chromium and WebKit. The new path checks the change of the generated date with the active date filter, remaining in the calendar, canceling and confirming the cancellation, persistence after refreshing, hiding the action for the player and no overflow. Screenshots `calendar-card-actions.png` in Playwright results.

### Fourteen local profiles

At the user's request, the seed of the local preview was expanded to include 12 players with names and surnames and the nickname „Podgląd lokalny”. Together with Admin Demo and User Demo there are 14 profiles. All new accounts have the player role and PIN 123456. Deterministic IDs prevent duplicates after the next seed run. Existing profiles, PINs and declarations remain preserved. Checked the seed restart and the number of 14 profiles in the DB/API.

### Calendar column alignment

Added a „Wybierz dzień” header above the month tab and aligned the height and spacing of both column headers. The month card and the first encounter tile start at the same height. Moved sticky positioning to the entire month column, excluding narrow screens. Geometry in Chromium 1440 px (difference in the position of the top edges ≤1 px), visual screenshot and no overflow at 360/390/430 px were checked. Typecheck and lint passed.

### Neutral declaration button

Before the declaration is saved, the „Będę” button has a neutral appearance like „Nie będę”, without a check mark. The confirmed status remains in the card header („Masz miejsce na boisku”) and icon after the server responds. Removed visual suggestion of previous selection; the recording and confirmation rules have not changed.

At another user request, the first declaration buttons received pastel backgrounds: light green „Będę” and light red „Nie będę”, without a check mark. Only visual change; the confirmed participation still results from the API response and card header.

### Eight people in a meeting and declaration icons

At the user's request, eight demo players were registered for the local meeting on 2026-11-24 (ID 0361387e-3365-556c-ad62-890b36ecd99e), using the declaration service and the local database `*_dev`. The meeting has 8 participants and 6 available seats; previous enrollments retained. Following another request, ✓ has been added to „Będę” and × to „Nie będę”, keeping the pastel colors. Typecheck and lint passed; the browser confirmed 8 names and both icons.

### Unlock approval in attendance test

After changing the local time of the match, the API returned `can_confirm=true`, but all 9 people had `draft_state=unknown`; The UI blocked the commit correctly, but did not indicate the missing step. Added messages explaining the need to tag people and save the draft. At the user's request, only a local draft of the test meeting was prepared: unmarked people were set as present via the save_attendance service, retaining the existing markings and without confirming presence. The browser confirmed the active button and the opening of the commit summary. Typecheck, lint and diff-check passed.

### Court adjusted to the number of players

Removed the solid six cells and empty dots. Teams of 1-6 have their own deployment; three people are set up 1 at the net + 2 at the back, four in 2×2, five in 2+3. The formations are mirrored across the net, also in the vertical mobile arrangement. The seventh person is still included in the rotation, and player swaps and lineup saves work with the same IDs. The changes include a common Court used by the organizer and players, with no backend changes.

Verification: typecheck and lint; browser control of 1-7 people in each half at 1440/390 px, exact number of players with no empty cells, 1+2 and 2x2 geometry relative to the net, seventh person rotation and no horizontal overflow. Visual variants controlled on the replaced read response, without saving fictitious lineups to the local database.

E2E venue result: **3/3 passed**. Full venue track tests: conversion at 7:7, saving and publishing lineups, PDF and presence corrections in Chromium desktop/mobile and WebKit. The desktop audit also revealed too light date/time text in the side panel of the next meeting; it was darkened for AA contrast.

### Centering unequal teams

Fixed geometry at 4:5: the outer halves of the court shared a common height, but the inner four-man arrangement kept its own, lower height and stayed at the top edge. Half is now a grid container extending the formation to the full height available, with even rows. Browser control 4:5, 5:4, 4:6 and 6:4 at 1440/390 px checks the centers of both formations and the average centers of the four players relative to half (1 px tolerance), without saving lineups to the database. Lint and diff-check passed.

## Final PR verification / version 0.3.0

Branch `feat/calendar-management-and-court-layouts`, based on `origin/main` after PR #3. HA application version upgraded to 0.3.0, changelog updated in English.

- `npm run lint`, `npm run typecheck`, `npm run api:check`, `npm run test:frontend` (1 test), `npm run build`, `git diff --check`: passed.
- `VOLLEYCREW_TEST_DATABASE_URL=…/volleycrew_test npm run test:backend`: **123 passed**, local PostgreSQL 14.24.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm run test:e2e`: **41 passed, 1 intentionally skipped** (mobile keyboard on desktop), Chromium desktop/mobile and WebKit.
- New persistent test `e2e/court.spec.ts` checks layouts 1-7, grid direction, rotation and centering 4:5, 5:4, 4:6, 6:4 in three browser projects.
- Checked for missing preview buttons, demo account IDs and route `/preview/login` in production JavaScript. Accounts and test attendance/appointment operations were local only; migration does not create demo data or bypass timing rules.
- Screenshots for review: [calendar actions](images/calendar-meeting-actions.png), [court before patch](images/court-unequal-before.png), [court after patch](images/court-unequal-after.png).

CI GitHub will additionally check PostgreSQL 17 and production images of both CPUs; local results do not replace these attempts. The physical installation of HA and acceptance testing of the phone remain with the user.

### CI fix after creating PR #4

Check package amd64 built the image and passed UI/Ingress attempts, but ended with a restore assertion pending hardcoded `0007_results`; the restored database correctly had `0008_additional_meetings`. The same stale expectation was in the bundled PostgreSQL test. Both tests now compare the database to `expected_revision()` running inside the image under test - the same version source the application uses. Control still requires exact compliance, without manually updating the number after each migration.
