# E3 - Meeting Models and Calendar

Date: 2026-11-06. Status: Implemented and verified locally. Without HA deployment, commit or publication. The stage includes meeting occurrences and reading them; participation declarations and seat allocation belong to E4.

## Acceptance testing E3

| Criterion                            | Implementation and proof                                                                                                                                                                                                                                              |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ScheduleVersion, Meeting, Enrollment | `0003_meetings` Migration: Schedule versions excluding overlapping slots, unique source term, match/player pair, order sequence and indexes. `alembic check` does not detect differences from models                                                                  |
| Default schedule                     | Tuesday 18:00, 120 minutes, Europe/Warsaw, I LO in Gdańsk; limit 14. Migration adds only the rule, without fictitious matches and players                                                                                                                             |
| Enumerate and merge                  | Pure `app/domain/schedule.py` module, local dates converted to UTC. Virtual instances are merged with persistent records. The postponed record replaces the original appointment, the canceled one remains visible                                                    |
| Further months                       | API range 1-366 days with pagination; you can select the month directly and browse further. There is no limit to the next week or year. Tests read 2040/2041 and E2E opens the deadline 10 years after the test month                                                 |
| Idempotent opening                   | UUIDv5 results from the schedule version ID and source date. `POST /meetings/resolve` validates the rule, creates a record via INSERT ON CONFLICT and returns it. Tests of two HTTP requests and two independent DB transactions prove an identical ID and one record |
| DST, day of the week and boundaries  | Tests for March and October time changes, leap year, year transition and change from Tuesday to Thursday/Friday. The version compartments are closed on the left and open on the right                                                                                |
| Stable history                       | The ID and source date remain after the actual start is postponed; reading at the same address works after the deadline. Unmaterialized past meetings do not pretend to be the history of matches played                                                              |
| Privacy                              | Calendar, details, schedule and group list require a session. The participant/player's DTO contains only ID, name, surname and nickname; no priority status, role, PIN and private history data. A blocked profile does not open new records                          |
| UI variant A                         | Monthly calendar and list, month/day selection, cancellation marking, next API date, details and return to the month of the meeting. Empty states, retry error and old data information on refresh error                                                              |

## Contract and behavior

- `GET /api/v1/schedule`: rule versions (Monday=0, Sunday=6).
- `GET /api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD&limit=50&offset=0`: Europe/Warsaw calendar dates, `to` exclusive, maximum 366 days on request. Returns `items`, `total`, and `next_offset`. Query years supported 1970–9998; is the limit of technical representation, without limitation to the nearest meeting occurrences.
- `POST /api/v1/meetings/resolve`: `{schedule_version_id, source_date}`. The opening itself does not declare presence, does not take up space and does not create Enrollment. The new record may refer to a future or ongoing valid occurrence; the past cannot be created. An already written record remains readable and idempotently resolved even after time, rule changes and revocations. E4 declarations must separately check future start and meeting status.
- `GET /api/v1/meetings/next`: the earliest uncancelled and unfinished meeting whose end has not yet passed, also currently in progress; missing term gives `null`.
- `GET /api/v1/meetings/{id}`: persistent deadline and secure attendee lists/waitlists.
- `GET /api/v1/players`: paginated list of active profiles for the logged in group. The anonymous login directory is still a separate, masked DTO from E2.

The default rule source has a start date of 1970-01-01, which does not create historical encounters. We count the duration as the actual interval from the beginning in UTC. No behavior has yet been established for a local time that does not exist or occurs twice during a time change; a pure function explicitly discards such a start instead of moving it silently. Default 18:00 does not have this problem. E5 must validate the proposed rule before writing it and, if time is needed, obtain DST policy resolution.

## Verification

Local environment: macOS arm64, Python 3.13.18, PostgreSQL 14.24 on 127.0.0.1:55432; separate database `volleycrew_test`. Integration tests and the E2E seeder require the `_test` suffix, they do not use dev or maybe-finance.

- `npm run lint` - Ruff, ESLint and Prettier correctly.
- `npm run typecheck` - Correct.
- `npm run api:check` - Current OpenAPI and generated types.
- `VOLLEYCREW_TEST_DATABASE_URL=<*_test database> npm run test:backend` - **35 passed**. One Starlette dependency warning about future TestClient transport change, no test failure.
- `npm run test:frontend` - **1 Vitest passed**.
- `VOLLEYCREW_E2E_DATABASE_URL=<*_test database> npm run test:e2e` - **6 Passes** in Chromium 158: legacy E2 paths, navigation and new full calendar scenario. Overflow control and screenshots 360/390/430/1440 px; network error by aborting browser requests and retrying to the real API.
- `npm run build` - correct production build.
- Alembic `check` on test DB - `No new upgrade operations detected`.

Screenshots (ignored in git): `volleycrew/frontend/test-results/calendar-calendar-future-n-16f7f-sistent-detail-and-recovery-{desktop,mobile}/`, files `calendar-360.png`, `calendar-390.png`, `calendar-430.png`, `calendar-1440.png` and `meeting-detail.png` according to the project. The 360 ​​px calendar and mobile details were visually checked. It's a Chromium emulation, no phone/Safari physical test. The dummy reference only exists in the E2E seed.

## Forward to E4

- Enrollment is a foundation without a write endpoint. E4 implements the entire allocation under the Meeting lock: limit, three priorities, reservations, offers and retries. Opening a date in E3 does not mean that the criteria for registering a player from E4 will be withdrawn.
- `declared_at` and `queue_number` are sorting out reports. Re-registration after withdrawal requires a new time and number; repeating the current declaration must preserve both. Just refreshing the page doesn't change anything.
- The `accepted_late_offer` field must be associated with the actual event/SeatOffer in E4, without the possibility of assigning an exception by the client.
- Only E4 attaches the release of future places/offers to the profile lock and allows the administrator to change the private priority. Maintain the order of locks identity → schedule/meeting to avoid deadlocks; E5 schedule operations work with the rule lock used in the resolver.
- E5 provides editing and referencing from UI/API; the current reading code already correctly includes such records, tested by directly changing the fixture DB.
- PostgreSQL 17/CI, HA suite, Ingress, Pi 4 test and backup/restore are still pending. A local test is not proof of deployment.

The next ready stage after the order: **E4 - declarations, priorities and waitlist**.
