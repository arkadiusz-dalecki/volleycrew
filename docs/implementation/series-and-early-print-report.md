# E3/E5/E7/E9 - Removal, Existing Series and Previous Signature List

Date: 2026-11-08. Scope requested by the user: deleting events from the view, editing/deleting existing series, printing the list before leaving home. Local implementation, without changes to the production database and without HA installation.

## Criteria and changes

- „Usuń spotkanie” on tiles and details, also canceled. Dialog with consequences before deletion. The deleted appointment disappears from the calendar, next meeting, direct entry and mutations; does not respawn from the weekly rule or after changing it. Reservations and offers close without new absence entries. Migration `0009_deleted_meetings` adds a deletion marker, preserving history and associations.
- Permanent list of existing series in the calendar, including the default Tuesday series. „Edytuj serię” loads parameters, previews the effects, and changes the future part of this rule. ID and order preserved; changed meeting occurrences require new confirmation. Shortening the range removes missing meeting occurrences. Individual scope exceptions remain, date/time conflicts are rejected.
- „Usuń serię” deletes all its future meeting occurrences, including unpersisted and individually moved ones, leaving the past/played history, other rules and independent additional meetings. We do not restore the default rule in a deleted scope.
- Preview and save series are protected by a global version and a token containing the versions of the affected meetings. Changes are atomic, with a common lock order. An ordinary player is not entitled to these operations.
- D7 changed according to new command: „Lista podpisów” active before meeting. The PDF contains confirmed places for the current date, without waitlists/offers/pending; after confirmation of attendance, it is transferred to those actually present. The UI provides the source, detects data changes and always downloads the current PDF. Attendance draft does not change the enrollments list; export remains a read operation.

## Verification

macOS arm64 environment, PostgreSQL on 127.0.0.1:55432, only isolated database `volleycrew_test`.

- `VOLLEYCREW_TEST_DATABASE_URL=…/volleycrew_test npm run test:backend`: **133 passed** in final full run. The first run of the new test showed an incorrect expectation of zero events after a prior abandonment; we check whether the event count is preserved before/after the series is deleted and the existing opt-out entry remains.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm --prefix volleycrew/frontend run test:e2e`: full run - **59 passed, 3 old calendar selector fails, 1 intentionally skipped**. The old test involved one button on a canceled tile; when added „Usuń spotkanie” explicitly points to the open button. New edit test clarified to the form selector instead of the overly strict select label.
- After corrections and forcing a fresh attendance reading in the PDF preview: `npm --prefix volleycrew/frontend run test:e2e -- calendar.spec.ts series-management.spec.ts`: **9 passed**. A total of **62 active scenarios** have a passing result from a full run or final repeat; no next full pass after changing the selector. Chromium desktop/mobile and WebKit; width 360/390/430/768/1440, accessibility and touch control tests passed in full.
- `npm run lint`, `npm --prefix volleycrew/frontend run build`, `npm --prefix volleycrew/frontend run test` (1 test), `npm run api:check`, `git diff --check`: passed. Build includes TypeScript.
- API tests: deleting and not allowing re-resolve, hiding from reads, closing offers, no new presence events, privacy, future part of series, exceptions, maintaining history and independent meetings, shortening scope, changing rule after single deletion, simultaneous admin changes, conflicts and outdated views.
- PDF: early printing, no side effects, draft/attendance update, waitlist/offer/reconfirmation exclusion, current corrections, permissions check and blocked export of deleted/cancelled appointment.
- A render of a sample printout was reviewed: 14 Polish surnames, one A4 page, table and signature fields without truncations. QA example in `output/pdf/early-signatures-qa.pdf`, outside the repository; generator and fonts remain local.
- Browser tests include deleting a canceled meeting and persistence after refreshing, editing a selected series and deleting it, previewing and downloading PDF before the meeting, as well as previous venue/schedule scenarios.

## Other dependencies

Dev is available under `http://localhost:5173` with local migration 0009 and API 8201. Production update requires a pre-migration copy and separate CI/both images and acceptance testing on the phone/HA. No changes were initiated in production. New npm/Python dependencies are not needed. There is no open decision blocking this scope. Next step: acceptance testing in Dev, then preparing a release/PR according to the user's request.
