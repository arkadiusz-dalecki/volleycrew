# E4 - declarations, priorities and waitlist

Date: 2026-11-06. Status: Implemented and verified locally. Without commit, publication and HA deployment. Approved D2/D3/D6 and specific meeting time limits apply. No new unapproved product rules.

## Acceptance testing E4

| Criterion                          | Implementation / proof                                                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Declarations and limit 14          | PUT „będę/nie będę”, DELETE withdrawals, separate waitlist and reservations. Any change in allocation blocks the Meeting by SELECT FOR UPDATE. Tests of two HTTP and two independent DB transactions prove 14 places with concurrent enrollments                                                                                                                           |
| Three private statuses             | Founder > player > guest, time and queue number inside the status. Tests all level relationships and independence from admin role. Group DTO does not contain priority                                                                                                                                                                                                     |
| Displacement and the 24 hour limit | A new application or change of status can only recalculate seats before the border. Existing places are protected from the border, you can still register for vacant ones. Right at the border, giving up is normal. The time is read after the lock is obtained, not before waiting                                                                                       |
| Repetitions                        | Idempotency-Key, separate persistent receipts and content fingerprints. Replaying does not change the time, queue number or history and does not reopen the submission after later withdrawal. Explicit re-enrollment after withdrawal gets a new time and number                                                                                                          |
| Reservation of a free place        | The first person in line receives a reservation immediately after a seat becomes available, before the proposal. The new application does not take over the reservation. Several places give separate reservations to different people                                                                                                                                     |
| Explicit offer and acceptance      | The administrator activates the proposal and contacts you manually on Messenger. Only the addressee who accepts the current proposal reaches the participants. No automatic timeout; you cannot accept someone else's proposal, which is closed, old or has a different date                                                                                               |
| Decline / pass to the next player  | A refusal or manual closure for non-response withdraws the application without marking late cancellation/absence. The place is waiting for the next person. Repeated admission/closure does not duplicate the effects                                                                                                                                                      |
| Late Offer Exception               | Acceptance in the last 24 hours saves the flag and event with time/offer ID. A later reported opt-out has an exception; regular late enrollment does not qualify. E6 cannot apply this exception to no-show                                                                                                                                                                |
| Status change and blocking         | The administrator changes the private status in the settings. The conversion preserves the original order and reservations. A lock in the same transaction invalidates sessions/grants, releases all future slots/reservations/offers and handles the queue; past enrollments remain. A race between blocking the account and accepting an offer does not restore the seat |
| Phone UI                           | Participation card above participants, place for waitlist, separate confirmed/free/reserved counters, cancellation confirmation, organizer's offer panel and private status selector. No success before API response; after error/conflict, refresh and message                                                                                                            |

`0004_enrollment` migration adds `reservation_kind` (offer/reconfirmation), SeatOffer, EnrollmentEvent and EnrollmentMutation. Status `reserved` in the offer indicates a protected space before the offer is activated; `pending` indicates a proposal waiting for a response. The final states are accepted/declined/closed/revoked. No automatic “expired after N minutes”, as per D2.

## Important details

Resignation and response to the offer fill the vacancies, retaining the remaining seats. The mere acceptance of the offer does not trigger the re-displacement of the person who has just accepted the reservation. A full recount before the border occurs after a new application and change of status; active reservations remain protected. Tests detected and secured this case.

Late abandonment requires `acknowledge_late=true` if the server calculates true late abandonment. When the boundary between preview and commit has passed, the API discards the unconfirmed late opt-out and the UI refreshes the information before the next confirmation. The normal/late/late_offer_exception/none classification is stored in a private EnrollmentEvent. Haven't created the full AttendanceEvent or history view yet - it's E6 to leverage these sources without duplicating events.

The global transactional identity lock from E2 stays before the Meeting lock, so that profile lock and write/accept also work together across multiple processes. The correctness of the limit does not depend solely on it: tests without this global mechanism use separate DB sessions and a common Meeting lock. Changing the status/blocking of multiple future meeting occurrences fetches them in a stable ID order. After unlocking, old sessions and declarations do not return.

## HTTP contract

All paths under `/api/v1` require a session; mutations also CSRF/Origin.

- `GET /meetings/{id}/my-participation` - self-declaration only, allocation, position, possible offer, normal cancellation deadline and its current classification.
- `PUT /meetings/{id}/my-declaration` - `{declaration: going|not-going, term_version, acknowledge_late?}`.
- `DELETE /meetings/{id}/my-declaration` - `{term_version, acknowledge_late?}`.
- PUT and DELETE require a `Idempotency-Key` header with UUID. The same key within a player/encounter and different content results in a 409. Retry returns the current state, not a historical snapshot of the place.
- `GET /admin/meetings/{id}/offers` - reservations and organizer's proposals.
- `POST /admin/meetings/{id}/offers` - `{player_id, term_version}`; only for an existing reservation, retry of the active proposal returns the same property.
- `POST /offers/{id}/accept` and `/decline` - `{term_version}`; only the addressee.
- `POST /admin/offers/{id}/close` - `{term_version, reason: no-response}`; manual forwarding.
- `PATCH /admin/players/{id}` - `is_active?` and/or `priority_status?`; none of these operations change the administrator's role.

Declaration/response mutations return the current `meeting` and `participation`. Group lists do not contain other people's priorities, opt-out events, or exceptions. Details and calendar additionally show `reserved_count` and `free_count`; 13 participants and 1 reservation means 0 free places, not free registration for the last place.

## Local verification

macOS arm64, Python 3.13.18, PostgreSQL 14.24; isolated `volleycrew_test` on 55432. No test access to dev/maybe-finance. Backend and E2E tests performed sequentially on the same explicit test database.

- `npm run lint` - Ruff, ESLint, Prettier correctly.
- `npm run typecheck` and `npm run build` - correct.
- `npm run api:check` - contract and API-compliant types.
- `VOLLEYCREW_TEST_DATABASE_URL=<*_test database> npm run test:backend` - **52 passed**, including 17 E4 cases: different priorities, limit, last-seat race, simultaneous admissions and new registration, block/acceptance, history preservation, receipts, time limits, late offer exception and waiting for a block until the start. One Starlette library warning for future TestClient transport change, no test failure.
- `npm run test:frontend` - **1 Vitest passed**; E4 behavior is checked by a real browser and API.
- `VOLLEYCREW_E2E_DATABASE_URL=<*_test database> npm run test:e2e` - **8 passed**, previous E2/E3 paths and new registration → further date → waitlist → resignation of the organizer → proposal → explicit acceptance on the second device → refresh with 14 participants → private status change.
- Alembic `check` on test DB - `No new upgrade operations detected`.

One of the E2E runs ended in a timeout after refreshing a canceled meeting in an existing calendar scenario. Full retry without code changes or timeouts passed all 8 tests. The cause has not been recreated; observe this scenario in CI.

Chromium 158, desktop 1440 px and phone emulation 360/390/430 px. No horizontal overflow in new tabs; the 360 ​​px waitlist card and the active proposal mobile panel were visually checked. Screenshots in ignored `volleycrew/frontend/test-results/enrollment-distant-signup--04825-cceptance-on-another-device-{desktop,mobile}/`: `reserve-*.png` and `organizer-offer.png`. The physical phone and Safari are still untested.

## Other dependencies

- E5: date change/cancellation, new D4 confirmations, re-proposals after each change, reservation protection and manual release in the absence of confirmation. `reservation_kind=reconfirmation` is a foundation, not a finished E5 process. E5 must invalidate old grants in the same transaction and maintain order; current endpoints reject the incompatible version.
- E6: private attendance history with corrections and no-shows, using EnrollmentEvent. Do not generate absences for cancellation/refusal of offer/waitlist. The late offer exception does not excuse a no-show.
- E9/E10: physical browsers, PostgreSQL 17/CI, Home Assistant/Ingress, Pi 4 and backup/restore still require real acceptance testing. The current stage is not a production release.

Next ready scope after the order: **E5 - Rescheduling and Cancellation**.
