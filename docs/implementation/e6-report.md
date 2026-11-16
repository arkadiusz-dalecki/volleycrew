# E6 - presence, private history and teams on court

Date: 2026-11-06. Status: Implemented and verified locally. Without committing, publishing and deploying Home Assistant.

The user has approved a split for 2-14 people, with a maximum of 7 and a maximum size difference of 1; reopening lineups ahead of the result with cause; releasing seats that are absent while maintaining the waitlist, confirming that the recipient of the reservation is physically present and returning the late person by making corrections to the availability of a seat. Decisions are saved in `decisions.md`, rules in `domain-api.md`, interface in `frontend.md`.

## Acceptance testing E6

| Criterion                        | Implementation and proof                                                                                                                                                                                                                                                                                    |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Draft and informed approval      | The draft doesn't make history; unknown persons block the approval. Confirmation only from the start, in a separate confirmed operation. No-show pre-commit and pre-launch lock tests                                                                                                                       |
| History classification           | Regular/Late Cancellation, Late Offer Exception and No-Show are separate. Migration moves previous classified opt-outs out of the EnrollmentEvent; subsequent ones are saved atomically with the source event. Late offer exception does not justify no-show - separate tests of both paths                 |
| Places after checking attendance | Absent loses the allocation without losing the source declaration and history. Rebalancing ignores those who are absent, reserving a place for the next person; does not accept it automatically. An unconfirmed reschedule does not create a no-show                                                       |
| Waitlist support at the venue    | The organizer confirms the physical presence of the recipient of his reservation or forwards it manually. Another profile does not take over this place. No automatic timeouts and absence markings for the reservation itself                                                                              |
| Adding and being late            | Active existing profile, free unreserved space, limit of 14 and audit. Late arrival marked absent requires corrections with the reason. Two independent PostgreSQL sessions trying last place: one accepted, the other version conflict; 14 in total                                                        |
| Private history and corrections  | Your own profile and administrative reading of a given player with pagination. Correction does not overwrite the source, it preserves the author/time/reason. A regular player gets 403 for someone else's history and all administrative mutations. No private fields in public court and participant list |
| Two generators                   | Random with controlled source in tests; balanced combination review minimizing the difference in averages, deterministic tie-break. Tests 2/3/11/12/13/14 people, rejection 0/1/15. In E6 actual starting rating of 1000, no fictitious ranking                                                             |
| Membership and numbers           | Everyone actually present exactly once, no one absent; max.7 per side, difference ≤1. The backend rejects duplicates, missing and invalid people. Split, patches, commits and corrections checked for 11–14                                                                                                 |
| Court variant A                  | Two halves, full names, seventh person in the rotation. On the phone, half vertically; on a wider card horizontally. Switching by touching two people, also both rotating at 7:7. Saving manual corrections before commit, restoring after reload                                                           |
| Draft and publication            | Draft only for the organizer; the group only sees approved teams. Opening with a reason archives the previous lineup and creates a new draft. Changing the actual attendance requires the prior opening of lineups and invalidates their draft; completed match blocks physical presence change until E8    |
| Versions and retries             | Meeting FOR UPDATE, expected_version and persistent Idempotency-Key cover all venue mutations. Attendance retries/lineups and draws have no additional effect. E2E loses response after actual draw save: retry recovers same commit                                                                        |
| Schedule Regression              | Rescheduling/cancellation removes the unapproved draft; the resignation disappears from the current list of candidates. All previous E2–E5 tests remain passed                                                                                                                                              |

## Code and API

Migration `0006_room` adds Attendance, AttendanceEvent, TeamSheet, TeamMember, RoomMutation and venue revisions in Meeting. The current attendance revision is saved from the team draft; validation on commit re-checks the completeness of membership. Previously approved lineups and history entries are not overwritten. Downgrade with attendance/history/lineups data is intentionally blocked; return requires a compatible backup.

Endpoints and schemes: `backend/app/api/room.py`, `room_schemas.py`; transactions: `services/room.py`; clean generator: `domain/teams.py`. All endpoints are under `/api/v1`, administrative ones require an actual role and CSRF. Public for the logged in group, reading `/meetings/{id}/teams` returns the approved lineup or null; the history is never attached to it. The OpenAPI contract and frontend types are generated.

Frontend: `features/room/RoomPanel.tsx`, `Court.tsx`, `HistoryPanel.tsx`, `useRoomAction.ts`. Success only after response, save operation to retries after response loss, refresh after conflict without silently overwriting local patches. Your own profile includes a history; the organizer opens `/admin/players/:playerId/history` from settings or attendance list.

## Checks performed

macOS arm64, Python 3.13.18, PostgreSQL 14.24 on 55432. Data tests only in the dedicated `volleycrew_test`; without database maybe-finance and production. Development migration performed in `volleycrew_dev`.

- `npm run lint` - Ruff, Python, ESLint and Prettier format correctly.
- `npm run typecheck`, `npm run api:check`, `npm run build` - correct.
- `VOLLEYCREW_TEST_DATABASE_URL=<*_test database> npm run test:backend -- -x --tb=short` - **85 passed**, including **22 E6 cases**. One Starlette dependency warning about future TestClient transport change.
- `npm run test:frontend` - **1 Vitest passed**. Browser-verified E6 flows with real API and PostgreSQL.
- `VOLLEYCREW_E2E_DATABASE_URL=<*_test database> npm run test:e2e` - **12 passed**, include previous E2-E5 and venue desktop/mobile scenario: presence → loss of response after split → safe retry → swapping rotators at 7:7 → save/reload → commit/public court → opening with reason → attendance correction → own history and denial of other people's history.
- Alembic `check` on dev and dedicated test database - `No new upgrade operations detected`.

Chromium **158.0.8127.18**: desktop 1440 px, Pixel 7 emulation 390 px and court control at 360/390/430 px, no horizontal overflow. Screenshots and visual reading of full/long Polish surnames and rotations. No physical test was performed on the phone or Safari/iOS. In the E6 scenario, the absence of rendering errors and duplicate React keys was also checked.

Evidence in ignored `volleycrew/frontend/test-results/room-attendance-full-court-fc31b-eams-and-private-correction-{desktop,mobile}/`: `court-1440.png`, `court-360.png`, `court-390.png`, `court-430.png` and close-ups of `court-detail-*.png`. Seeder creates separate ongoing matches only in database `_test`.

## Other dependencies

- **E7 - PDF of actually present** is the next ready stage after the order. D7 already approved.
- **E8 - results and ELO**: connecting points to the generator, results/0:0 and rules for corrections of historical lineups, conversions and scale of expectations. E6 does not save the score, does not change ELO and does not edit the physical presence of a completed match.
- E9 includes final unification of the entire interface and attempts on physical phones.
- CI/PostgreSQL 17, installable HA/Ingress package, both architectures, Pi 4 and actual backup/restore remain until acceptance testing E10. Local green testing does not mean a ready production release.
