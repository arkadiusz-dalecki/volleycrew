# Preliminary court - 2026-11-09

Scope: E4/E6/E9 supplement requested by the user. HA package version: **0.3.2** (patch after 0.3.1). Implementation on branch `feat/manage-series-and-print-signatures`; no changes to the production database.

## Acceptance testing criteria

- Before checking attendance, meeting details are shown to the court from confirmed locations. The default split minimizes the difference in averages of the current ELO, is deterministic and includes each person exactly once. There is a limit of 14 and a maximum of 7 per side; for 0–1 there is a readable empty state.
- Waitlist, offers, inactive profiles and those waiting for reconfirmation remain out of court. The preview does not save attendance, official teams or rankings.
- Your own subscription/resignation/acceptance of the offer refreshes the preview immediately. Other devices read changes every 30 seconds and after returning to the card. This is not a push transmission.
- Administrator saves common random split, manual swaps or returns to ELO. Changing the declaration, deadline or points invalidates the exception. Returning the same list of people after resignation does not restore the old split.
- Entry token, revision and meeting lock discard stale records and parallel changes (409). The user has a preview without administrative tools; the server checks the role and CSRF. DTO does not disclose private statuses or reasons for corrections.
- After confirming attendance, „Użyj wstępnego podziału” creates an official draft from the preview if the people and points match. Otherwise the balances actually present. Official approval of teams remains a separate step.

## Implementation and migration

Separate service `preliminary_teams.py`, GET public for logged in users and PUT for the administrator. `0010_preliminary_teams` migration after 0009 adds admin exception table; does not transfer attendance or demo data. The default ELO is created when reading without writing to the table. Preview changes do not increase the meeting version, so they do not invalidate the printout or attendance form. The existing backup and migration procedure applies before an HA update. Migration performed locally on the development database.

The frontend uses the same court variant A as the official lineups. Selected people are associated with a fingerprint and revision so as not to be replaced on an outdated list. An error reading indicates the last split; re-saving after losing the response does not perform a second draw.

## Verification

Environment: macOS arm64, Python 3.13.18, local PostgreSQL, isolated database `volleycrew_test`; Chromium 158.0.8127.18 and WebKit Playwright (iPhone emulation, not physical Safari).

- `VOLLEYCREW_TEST_DATABASE_URL=… npm run test:backend`: **144 passed**, including 11 new preview cases. These include 0/1/2/8/14 people, ELO compliance, privacy and no side effects, reserve/offers, rescheduling/points, join-cancel, invalid splits, eligibility and competitive enrollments, and transfer to official teams.
- `npm run lint`, `npm run typecheck`, `npm run api:check`: passed.
- `npm run test:frontend`: **4 passed**; `npm run build`: passed.
- `VOLLEYCREW_E2E_DATABASE_URL=… npm run test:e2e`: **71 passed, 1 intentionally skipped** (desktop mobile keyboard case), full run of 3.7 min on desktop Chromium, mobile Chromium and iPhone/WebKit projects. The new scenario checks common manual replacement, user preview, immediate join/cancel, second tab refresh, no presence validated, accessibility and no horizontal scrolling.
- Local developer preview of November 17: API 200, court visible from current enrollments, screenshot `/tmp/volleycrew-preliminary-local.png`; without changing the declaration during the inspection.
- WebKit 390 px screenshot visual control: pre-court and admin tools fit in a tab; both sides and names are legible.

## Other dependencies

User acceptance testing of appearance, physical phone and HA installation/update remain to be done. The new demo data from November 17 only exists in the local development database. No production deployment or HA image testing was performed in this complement.

## Complement the declaration label

At user request, „Będę” has been replaced with „Potwierdzam obecność”. The action still saves the declaration, and attendance at the venue remains a separate admin approval. Selectors for existing scenarios have been updated. After the change: typecheck and 3 E2E pre-court (desktop/mobile/WebKit) passed; no new dependencies.

## Preparation of PR 0.3.2 - 2026-11-10

HA manifest bumped from 0.3.1 to 0.3.2; changelog contains the entire range of branches. Before publication, lint, typecheck, OpenAPI contract, `git diff --check` and 13 configuration/package tests were passed again. Previous full results of 144 backend / 71 E2E and final 3 E2E after relabeling remain functional evidence. CI will check the current commit and images of both architectures. PR does not deploy applications on HA.

## CI PR Patch #6 - 2026-11-11

Both images built, but the `scripts/test_container.py` scenario tried to declare for the ongoing next meeting. The launch of CI 2026-11-10 at 17:09–17:14 UTC was after the Tuesday start at 18:00 in Warsaw; The API was correctly returning 409 `enrollment_closed`. The endpoint of the next match deliberately takes into account the ongoing match.

Fixture now selects a scheduled appearance from the calendar starting tomorrow in the Europe/Warsaw zone, with a two-week window. The next cycle continues to write declarations through the actual API, and only then moves the test meeting to the venue. No production rules or enrollment limits have been changed. Added 4 regressions on the real API/PostgreSQL: Tuesday before the start, at the start time, during and after the meeting; each solves the future term and effectively saves the declaration. All 4 passed, lint and script compilation passed. Full image tests of both CPUs verified by CI re-run after patch release.
