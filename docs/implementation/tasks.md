# Construction stages and tasks for agents

Each stage is a separate, reviewable increment. By default, sequential execution. Separate branches of work are only possible after establishing a common contract and a clear order; the plan itself does not trigger the agents. Don't start a production implementation just because the document exists.

## E0 - foundation closure

Input: entire plan index, `architecture.md`, `decisions.md`, local maybe-finance reference. Dependencies: start command.

- Confirm D1 and the proposed D9 scope: HA host, CPU, domain/TLS, issuance method, PostgreSQL, backup responsibility.
- Verify current HA, Python/FastAPI, React/Vite and base image documentation. Note the supported versions and compatibility `amd64/aarch64`.
- Establish ports without conflict with maybe-finance; database, service and settings names.
- Record decisions: stack from plan or agreed change; login and PIN restriction method; session model and expiration date.
- Complete D2–D6 with examples. If there is no answer yet, mark dependent subtasks; you can build foundations without pretending to have a ready-made policy.

Acceptance testing: the agent can describe the phone's path from the Internet to the API and how to recreate the DB. The registry has decisions or precisely indicated open dependencies. Merely reading the files does not complete E0 if the findings necessary for the selected scope are missing.

## E1 - skeleton and environment

Dependencies: technical scope E0. Read: architecture, verification.

- Create a production structure next to `prototype/`, formatting/linting configuration, lockfile, test configuration and sample settings without secrets.
- Run PostgreSQL development; empty migration and establish the first base tables with the E3 model.
- Backend: health live/ready, configuration, DB sessions, error handling and injected clock dependency.
- Frontend: router, empty AppShell A, design tokens, API client, OpenAPI type generation and basic loading/error states.
- Define the commands: dev, lint, typecheck, backend test, migrations, frontend/e2e test, build. Add CI to run them on isolated services.

Acceptance testing: new checkout starts from README without manually correcting the code; health ready checks DB; frontend reaches API; production build goes through; CI does not touch production.

## E2 - sessions, PIN and invitations

Dependencies: E1, D6 for full profile policy. Read: domain access sections, frontend, verification.

- Player, Invite, Session, PinResetGrant models and persistent restrictions on login attempts.
- One-time bootstrap of Arkadiusz; random, voidable invite link; new registration only with an active link and always with guest status.
- Registration, chooser profile according to D6, login, remembered session, logout, PIN change and reset grant.
- Role authorization in each administrative endpoint; public profile DTO; session invalidation after lock/reset.
- Entry and profile path UI, expired invitation and reset messages.

Acceptance testing: after reopening, the user has a session; new device requires PIN; the player does not gain admin by changing the request; a revoked link does not register new people; attempts and reset limitations have integration tests. D6 left open indicates that the relevant operations are not completed, not tacitly skipped.

## E3 - meeting models and calendar

Dependencies: E1/E2; D6 for blocking operations. Read: model and schedule in the domain, calendar in the frontend.

- ScheduleVersion, Meeting and Enrollment migrations with constraints and indexes.
- Default Tuesday schedule and zone, clean function for generating meeting occurrences, merging occurrences with persistent records.
- Idempotent solution to the Meeting request with mutation.
- Upcoming meeting, details and paginated calendar scope. Public list of players without private data.
- Calendar frontend and details skeleton with API data, empty status and canceled appointment.

Acceptance testing: moving to next month and saving the date is not limited to the next week; two requests create the same Meeting; DST and new day of the week tests; the historical term has a stable identifier.

## E4 - declarations, priorities and waitlist

Dependencies: E2/E3; D2 and D3. Read: write transaction and place rules.

- EnrollmentEvent, SeatOffer and declaration/offer endpoints. One Meeting lock for all allocation changes.
- Three levels of priority (founder > player > guest) and order, pushing out before the border, protecting the place after the border, releasing places.
- Open acceptance/rejection/closing of the offer; seat reservation according to D2. Manual communication via Messenger, without integration.
- Own status card, participants and waitlist. Server messages about conflict, border crossing and offer expiration.
- Accepting a late offer saves the data needed for the opt-out exception.

Acceptance testing: testing on two concurrent DB sessions proves limit 14; repetition does not change the order; the founder displaces only according to the rule of time; waitlist player requires confirmation; someone else's/old offer cannot be accepted. E2E saves the next date and checks the result after refreshing.

## E5 - rescheduling and cancellation

Dependencies: E3/E4; D4. Read: schedule and meeting statuses.

- Preview of changes from the selected date, versioning of the schedule, postponing one meeting and canceling.
- Changing the term version, updating enrollments/offers in accordance with D4, re-confirmation.
- Admin UI with pre-approval scope summary, player UI with old and new deadline.
- Verification of permissions and version conflict on the second admin tab.

Acceptance testing: changing day from date includes existing records and future occurrences; no duplicates; the old confirmation is not current; a canceled appointment is visible in the history and does not create an absence.

## E6 - Attendance and Teams

Dependencies: E4/E5; D5. Read: attendance and teams, organizer panel in the frontend.

- Attendance and private history events, draft and attendance confirmation.
- Cancellation classification and late offer exception; no-show only on commit, according to D5.
- Two lineups generators: random and balanced. ELO by E8 may be base 1000 in real data, without dummy points from the prototype.
- Draft editing, membership/attendance/number verification, approval and controlled rollback.
- Court with full names, rotation and manual replacement of full teams; View approved lineups for players.

Acceptance testing: every person present is in exactly one lineup; absentees do not go to the generator; both modes work for 11-14 people, smaller numbers have explicit validation; 7:7 edition allows you to swap people; history is private also via direct URL/API. Duplicate-free recommit tests.

## E7 - Signature List

Dependencies: E6 and D7.

- PDF generation after confirmation of actual attendance; date, I LO in Gdańsk, number, name/surname, place for signature.
- Authorized preview/download; Polish characters and the provided font, without sending data to an external generator.
- PDF sources are only those actually present. After presence correction, regeneration downloads the current data; do not add an unapproved export variant from the declaration.

Acceptance testing: reading and visual inspection of the generated file for 14 people and long names; A4 print without cropping; changing presence changes the next generated list; an ordinary player does not download an administrative document.

## E8 - results, ELO and corrections

Dependencies: E6, D8.

- Validate pattern simulations and sample increments; save the algorithm version and precision.
- Implement pure meeting rating, ResultRevision, RatingEntry, transactional write and replay protection.
- Implement a 0:0 policy and corrections. When replaying, also check the lineup adjustments and moving the order in history.
- Result form with summary, ranking, match history, details of point changes.

Acceptance testing: mathematical properties met in `verification.md`; the result 5:3 does not count for the second time after the retry; absent has no RatingEntry; correction gives the same ranking as recalculating the history from the beginning; the crash doesn't save half of the match.

## E9 - UI A integration and attempts on the phone

Status: implementation and local control completed; [report and comparison A](e9-report.md). Acceptance testing of physical phones and acceptance of visual comparison remain open.

Dependencies: E2–E8. Read: frontend and verification.

- Check all routes, refreshes, expired sessions, errors/conflicts and network loss recovery.
- Unify CSS tokens and components; remove demo/variant switcher from production build.
- Support keyboard, focus, touch targets and player names on court. Include fonts locally.
- Complete the full participant and organizer scenario in 360/390/430 and desktop sizes. Add manifest/icons if they are within the specified range.

Acceptance testing: accepted comparison with variant A, no horizontal overflow and covered buttons, Chrome Android and Safari iOS support checked with version information. Emulation is a control step, not proof of test on a physical device.

## E10 - Home Assistant Pack

User scope from 2026-11-07: adding the repository, token and installation in HA yourself. The agent prepares the package and checks it locally; does not perform installations or changes to the HA/tunnel. [Report E10](e10-report.md) separates container verification from acceptance testing on Pi.

Dependencies: E0/E1 and running application; D1/D10. An experiment with an empty container can be performed earlier as part of E1, without announcing a ready deployment.

- Repository and application manifest, Dockerfile, s6, both Nginx listeners, configuration options, health, migrations and logs.
- Test the production image with the test DB; check start after missing DB, incorrect configuration and migration.
- Check Ingress under dynamic prefix and direct HTTPS domain; sessions and CSRF in both modes.
- Build/test both CPUs; use D10: local build in HA, missing field `image` with ready Volleycrew image, versioning via `config.yaml`, manual installation/update. Check the build on Pi 4 (RAM/time). Document the addition of the repository, refreshing the store, backup and update. CI can test the build without publishing an image.
- Perform a backup and restore on a separate instance, describe the rollback of the diagram and image.

Acceptance testing: installation and update in the target HA, data durability after restart, correct access from the phone outside the LAN, without an HA account for the player. The result of checking the second architecture described; do not equate compilation with launch.

## E10 - bundled PostgreSQL 0.2.0

Commissioned 2026-11-08. Replaces the requirement for a separate server in a new installation. Bundled database with automatic password and persistent /data; maintaining the existing external; migrations, restart/failure/update, HA backup and restore. Acceptance testing: real start and bootstrap without a separate server, data after restarts, restoration on a new volume, start lock in the absence of copies, checks of both CPUs. The installation is performed by the user.

## E11 - acceptance testing and first release

Dependencies: All required steps, resolved D1-D10, or explicit scope approved by the user.

- Complete the school venue scenario: 14 enrollments, withdrawal, offer, acceptance, attendance control, teams, signings, result and ranking.
- Pass scenario rescheduling, cancellations and corrections according to approved rules.
- Authorization and session audit, no secrets in logs, data recovery, accessibility monitoring and error log.
- Provide administrator instructions: invitation, PIN reset, schedule, waitlist, attendance, result, backup/restore.
- Before publishing/installing, follow the user's authorization; the plan is not a publication order.

Acceptance testing: All release criteria from `verification.md` have proof. The user approves the scope and behavior. The remaining jobs have separate tasks; bugs in quotas, privacy, persistence and ranking block the release.

## Single stage order format

```text
Zrealizuj E<n> z docs/implementation/tasks.md.
Zakres: <konkretne podzadania>.
Rozstrzygnięcia: <ID decyzji i zatwierdzony wariant>.
Przeczytaj wskazane specyfikacje; zweryfikuj zależności w kodzie.
Zakończ dopiero po kryteriach odbioru dla tego zakresu.
Raportuj: zmiany, testy i ich wynik, nierozstrzygnięte zależności,
pozostałe ryzyka oraz następne gotowe zadanie. Zaktualizuj postęp.
```

## Supplement E3/E5/E9 - Admin Calendar

Ordered 2026-11-08: visible date on the card, next meeting in the side panel, planning in the calendar instead of settings, single date and weekly series from-to. Acceptance testing: permissions, no collisions, behavior of enrollments and exceptions, return of previous rule after series, desktop/mobile/WebKit checking. [Report](calendar-management-report.md).

## E2/E9 Supplement - Mobile Fixes and Installation

Ordered 2026-11-08 after screenshots from iPhone: single appointment form without outgoing fields/frame, removal of meeting signature, drop-down account selection with last login memory, administrator/user view switch, button to add applications for iOS and Android. Scope and evidence: [report](mobile-improvements-report.md).

## Supplement E3/E5/E9 - Deletion and Existing Series

Ordered 2026-11-08: „Usuń spotkanie” also for canceled meeting occurrences, without their further presentation and removal from the schedule; visible list of existing series with editing and deleting, also for the current default Tuesday rule. Acceptance testing: permissions, permanence of deletion, scope of series, preserved history of played matches, release of offers/slots without absences, versions/preview and UI mobile/desktop.

## Supplement E3/E9 - Personal Calendar

Ordered 2026-11-08: „Dodaj do kalendarza” with a selection of Google, Outlook, Apple and other applications. Acceptance testing: current date/time/place, correct UTC/DST and Polish characters, no export of canceled/deleted meetings and participant data, ICS file and a clear limitation to one-time export.

Ordered on 2026-11-09 to complete the personal calendar: a button also on the tiles and a collective file for the displayed month or the next 12 months. Verification and import sources in [report](personal-calendar-report.md).

Update 2026-11-09: Monthly/12-month bulk export discontinued at user request. Single term export buttons remain on tiles and in details.

## Supplement E4/E6/E9 - Initial Teams

Ordered 2026-11-09: court with confirmed enrollments before attendance, ELO by default, automatic refresh after declarations and resignations, saved draw/manual replacement of the administrator and use of preview after checking attendance. Acceptance testing: limit of 14 and one place per person, no waitlist/offers, current ELO, list/second tab conflicts, privacy, no presence/ELO effects and mobile view. Scope and results: [report](preliminary-court-report.md).

## Addendum E3/E9 - Meeting Navigation Gestures

Commissioned 2026-11-11: left/right gesture and next/previous meeting buttons on main screen and details. Acceptance testing: chronology also for moved meeting occurrences and month/year boundaries, skipping deleted ones, no declaration during navigation, no collisions with scrolling/forms/touching and read error handling.

### Seamless tile - addition 2026-11-11

Commissioned and implemented: movement of the entire tile with the finger, return after a short/cancelled gesture, directional transition also from buttons, downloading a new term before the animation and limiting movement according to the system settings. Evidence and limitations: [navigation report](meeting-navigation-report.md#seamless-tile---addition-2026-11-11).

Follow-up 2026-11-16: quieter adjacent-date transitions, retained vertical scroll and stable main-screen layout. Remove shell remounting on URL changes while retaining error recovery. Regression: buttons and swipe at a nonzero scroll position, mounted shell, unchanged card top, normal calendar scroll reset, existing navigation errors and reduced motion. [Report](meeting-navigation-report.md#quieter-transitions---2026-11-16).

## Supplement E2/E9 - links, monitoring and abuse resistance

Commissioned 2026-11-14 after login review. Scope: removing the secret from the address after opening the link, discarding tokens in the path, Retry-After support, limited and secretless event logs, and limiting bursts of authentication requests before DB access. Acceptance testing: PostgreSQL tests of permanent limits/resets, controlled clock of the additional limiter, checking the logs for the lack of secrets and E2E registration/reset with a clean address and reopening the link. Without deployment and without changing other login decisions.

## Supplement E2/E9 - Optional Google, 2026-11-15

Ordered: connecting Google to the existing profile after confirming the PIN, logging in using `sub`, disconnecting using the PIN, HA and UI configuration and operator instructions. Acceptance testing: migration, sessions and unique bindings on PostgreSQL; signature/issuer/audience/exp/nonce, PKCE, state binding to browser and connecting session, one-time and expiration, account lockout, provider errors and lack of automatic registration. E2E with a local test provider and separate explicit acceptance testing with a real Google client. PIN and invitation policy remain available; Ingress refers to PUBLIC_URL.

## Supplement E2/E9 - login and password, 2026-11-15

Mandated: separate username and password instead of profile directory/PIN; registration, bootstrap, password change/reset and Google confirmations. The user does not require player migration (the only registered one is the organizer). Acceptance testing: no public directory/endpoint PIN; unique login regardless of case; correct hashing and errors, persistent limits and session expiration; preservation of organizer profile data and one-time configuration; tests of PostgreSQL, browsers and both packages.

## Addendum E2/E9 - Join via Google, 2026-11-15

Requested: registration from an active invitation via Google, hint of an editable name/surname, confirmation and an account without a password. Acceptance testing: linking the grant to the browser/invitation, invalidation of the invitation during the process, expiration/replay/competition, no duplication and escalation of privileges, optional setting of login/password after a new Google ID, protection against disconnection of the last method; PostgreSQL, UI mobile/WebKit and HA images.

## Supplement E2/E9 - passwords and invitations Messenger, 2026-11-15

Recommended: minimum password of 8 characters without forcing character types and opening invitations from Messenger. New invites carry the token in the query, old fragments remain supported. Acceptance testing: UI/API validation, registration/change/reset with short password, deletion of query/fragment without storage, additional parameters and changed fragment, invalidation of invitations and compatibility with the old format. [Report](messenger-invites-report.md).

## Supplement E9 - Modern Web Guidance, 2026-11-15

Requested after review: All six UI fixes described in [report](modern-web-guidance-report.md). Acceptance testing local: registration/reset/profile/Google forms use common compatibility check, invalid field has focus and description, showing password does not change value or autocomplete; dialogs limit scrolling according to engine support; text grows at 200% preference without horizontal scrolling 320-1440 px; footer does not jump through initial viewport when loading data; routes have separate chunks and download error handling. The regression includes Chromium/WebKit, the actual API, and a separate test PostgreSQL. Without changing the backend/DTO, migration, additional API cache and deployment; physical acceptance testing E9/E11 remains open.

Complement 2026-11-16 in the same package 0.3.6: fix missing access data of existing demo accounts after PIN migration and handling of competing unique indexes on term materialization (bug revealed by CI). [Report](modern-web-guidance-report.md#supplements-after-creating-pr---2026-11-16) contains diagnosis, scope and results of 216 backend tests. No migration/change of contract and no change of seat rules.

## Documentation — English translation (2026-11-16)

Completed at the user's request: translate all project documentation, including setup and HA operation, specifications, decisions, backlog and historical reports. Preserve actual Polish UI labels and historical product decisions. Verify local links and heading anchors, Markdown structure, command examples and numerical values. This follow-up changes documentation only; application tests and deployment are outside its scope.
