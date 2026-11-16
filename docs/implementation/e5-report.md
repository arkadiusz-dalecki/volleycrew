# E5 - Rescheduling and Cancellation

Date: 2026-11-06. Status: Implemented and verified locally. Without committing, publishing and deploying Home Assistant.

D4 remains valid: any change of date requires a new confirmation, maintaining the original order and reservations. In this conversation, the user additionally approved moving meeting occurrences to a new day in the same week (Monday-Sunday), keeping cancellations and keeping individual exceptions. The decision is stored in `decisions.md`.

## Acceptance testing E5

| Criterion                        | Implementation and proof                                                                                                                                                                                                                             |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Preview from selected date       | The admin form shows existing meeting occurrences before/after, the number of new confirmations, saved exceptions and examples of the new rule. Only a separate action confirms the entry                                                            |
| Dual Tab Versions and Protection | ScheduleState.version, Meeting.version and preview fingerprint. Another rule, deadline or enrollments change after preview gives a 409 instead of a silent override. Tests of two simultaneous administrators and an stale tab                       |
| Existing and future occurrences  | The rule changes both persisted meetings and future calculated meeting occurrences. Future superseded rules remain in the DB as superseded, preserving FK; are still not generated                                                                   |
| Stable ID without duplicates     | The original source and Meeting ID remain unchanged. A separate current association with a new rule instance suppresses its virtual counterpart. The old and new key resolve to the same record                                                      |
| Single occurrence                | The administrator selects the date, time and game duration, sees the effects and approves. An individual exception arises; a subsequent change to a permanent rule does not move it                                                                  |
| Reconfirmations                  | Existing seats become reserved/reconfirmed, without automatic timeout. Confirming the current version restores the place without the new reporting time/sequence. The waitlist also confirms the new date; does not automatically reach participants |
| Two more changes                 | Each increments term_version and invalidates the previous confirmation, even if the user has already responded to the previous change. The reverse order confirmation test does not change the order of the list                                     |
| Offers when changing             | Old active grants are revoked. The reservation is waiting under a new grant in a reserved state for the current date. The organizer again proposes a place; acceptance of old ID/version is rejected                                                 |
| Manual release                   | The administrator confirms that the space has been released pending new confirmation. The application is withdrawn; the next person receives a reservation in accordance with D2. No automatic admission or penalty                                  |
| Cancellation                     | A future unstarted meeting remains in the calendar/historical address as cancelled. All allocations/offers are released, declarations and events are retained. There is no no-show or late cancellation                                              |
| UI A on the phone                | Schedule settings, single date panel, old/new dates, new confirmation tab and separate waiting list. Effect confirmations and conflict messages; return to current month                                                                             |

## Model and transactions

Migration `0005_schedule_changes` adds:

- ScheduleState - global version of settings.
- MeetingTermRevision - persistent date revisions with author, time, previous and new interval, and change type.
- meeting.calendar_schedule_id/calendar_source_date - current schedule association, separate from the original identity source; unique in DB.
- Meeting.is_exception and previous dates to the current old/new appointment view.
- Enrollment.reconfirmation_required - Also includes waitlisted players and offers.
- ScheduleVersion.superseded and exclusion of overlapping intervals for non-superseded versions.

Lock order: identity from E2 → schedule state → rule/Meeting. The resolver takes a shared state lock before materializing, so that a skipped record of the old rule is not created during the bulk change. The calendar takes a shared lock to avoid mixing the old rule with already moved records. Mutations of all allocations still apply the Meeting lock from E4.

Preview does not change the DB. On approval it is counted again; token comparison takes into account the request content, versions/status of existing meetings, and applicable rules. In the meantime, a new record or opening of an appointment may change the scope - the administrator receives the conflict and makes a new preview. Participation reconfirmation has the Idempotency-Key and the current term_version as the E4 declarations.

## Limits and collisions

Changing a permanent rule replaces scheduled rules from the selected date, preserving previous history. Saved individual dates are clearly marked in the preview and do not receive a new confirmation request if their date has not actually changed. Cancellations remain canceled even after the postponement resulting from the new rule.

The new day is calculated in the same week Monday–Sunday. If you moved a fixed date before its effective date or into the past, the preview blocks the change and suggests the start of the week or a different range. It does not merge or delete reports. Collisions are also checked with meeting occurrences rules that have not yet been created: the absence of a record in the DB does not mean a free interval. A saved exception from another week cannot duplicate a new virtual meeting.

A non-existent or ambiguous local DST time is explicitly rejected. For a permanent rule, we check the full 400-year calendar cycle according to the installed Europe/Warsaw. Unapproved auto-shift 02:30 not implemented. Normal DST transitions continue to maintain local time; E3 tests remain green. The validity of tzdata and operation on Pi 4 are subject to acceptance testing E10.

The changes apply to future unstarted matches; completed/maintained meetings are not edited with this path. Manually releasing a waiting space also applies to a future date. E6 must take into account the handling of unconfirmed reports during actual presence, without an automatic no-show simply for the lack of a new confirmation.

## API

All endpoints below require an administrator role; also CSRF and Origin mutations.

- `GET /api/v1/admin/schedule` - version and non-superseded rules.
- `POST /admin/schedule/preview` - expected_version, effective_from, weekday (0-6), local_time, duration_minutes, venue; preview and preview_token.
- `POST /admin/schedule/versions` - same content and preview_token; record after re-verification.
- `POST /admin/meetings/{id}/reschedule` - expected_version, local_date, local_time, duration_minutes.
- `POST /admin/meetings/{id}/cancel` - expected_version.
- `POST /admin/meetings/{id}/release-reconfirmation` - expected_version and player_id.

Custom E4 provides needs_reconfirmation. Group details show previous_starts_at/previous_ends_at, is_exception and awaiting_confirmation, without anyone else's priorities or private history. Self-declaration still uses PUT /meetings/{id}/my-declaration with going and the current version of the term; in the case of a waitlist offer, the open acceptance must refer to the new offer.

## Local verification

macOS arm64, Python 3.13.18, PostgreSQL 14.24 on isolated port 55432; tests only in `volleycrew_test`. No dev was used for test data, database maybe-finance or production.

- `npm run lint` - Ruff/ESLint/Prettier correctly.
- `npm run typecheck`, `npm run api:check`, `npm run build` - correct.
- `VOLLEYCREW_TEST_DATABASE_URL=<*_test database> npm run test:backend` - **63 passed**, including 11 E5 cases: single and collective deadline, two postponements, confirmation order, old offers, reservation release, cancellation without absence, exception behavior, future rule/FK override, preview and two admin conflict, DST/scope boundary, and virtual meeting occurrences collisions. One Starlette dependency warning about future TestClient transport change.
- `npm run test:frontend` - **1 Vitest passed**. The main paths are checked by a browser with a real API.
- `VOLLEYCREW_E2E_DATABASE_URL=<*_test database> npm run test:e2e` - **10 passed**: Previous E2-E4 and new scenario of single exception → reconfirmation → new rule preview → exception behavior → another assertion → stale tab denial → calendar cancellation.
- Alembic `check` - `No new upgrade operations detected`.

Chromium 158: desktop 1440 px and phone emulation 390 px; previous scenarios still control 360/390/430 px. New reconfirmation card without horizontal overflow. The mobile old/new date card and the preview layout were visually checked. Screenshots in ignored `volleycrew/frontend/test-results/schedule-single-exception--045e9-anizer-tab-and-cancellation-{desktop,mobile}/`: `schedule-preview.png`, `reconfirmation.png`. No phone/Safari physical test.

## Further dependencies

- E6: attendance, personal history and corrections, teams and court. Cancellation/change events and waiting states cannot become automatic absences.
- E8: still open details of historical lineups and scale of expectations according to D8; they do not block E6.
- CI with PostgreSQL 17, CPU images, HA/Ingress targets, Pi 4 and backup/restore are still waiting for real acceptance testing. We do not declare a production release.
- Migration 0005 refuses to downgrade after saving E5 changes so as not to lose their associations/history. Undoing a deployment requires a compatible database and image backup; procedure and actual restore to E10. No destructive rollback or deletion of user data was performed.

Next ready stage after the order: **E6 - presence and teams**.
