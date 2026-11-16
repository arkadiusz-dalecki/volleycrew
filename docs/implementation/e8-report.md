# E8 - results, ELO and full corrections

Date: 2026-11-07. Status: Implemented and verified locally. No commit, publication or deployment of Home Assistant.

D8 closed by the user in this conversation: expectation scale 400 with K=32; full correction of historical attendance and lineups with mandatory reasons and version preservation; recalculation by start and fixed meeting ID. Previously approved: starting rating of 1000, set ratio, one delta per team, no rounding for presentation after each match, 0:0 and result corrections with recalculation of later matches. The decisions are in `decisions.md`; contract and precision policy in `domain-api.md`.

## Acceptance testing E8

| Criterion                                    | Implementation and proof                                                                                                                                                                                                                                                                                                  |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pattern and scale                            | elo-sets-v1, K=32, scale 400, team averages and set proportion. Tests 5:0 → ±16, 3:2 and 6:4 → ±3.2, draw equal → 0; a draw for the weaker players gives an increase, an insufficiently high win for the stronger players may reduce the points                                                                           |
| Without presentational rounding in condition | Decimal, 50 significant digits; Numeric without an imposed scale; JSON decimal as string. UI only rounds to 1 place. Playing the same replay gives exactly the same stored values                                                                                                                                         |
| Result from approved lineups                 | The server checks the status, attendance verification, completeness and number of lineups. Sets non-negative integer; bool/fractions/negative are rejected. Preview and separate commit in step 03                                                                                                                        |
| 0:0                                          | Ending with no sets, attendance/lineups preserved, no RatingEntry and no increase in the number of ranking matches. The result remains in history. Correction to/from 0:0 recalculates remaining matches                                                                                                                  |
| One delta per side                           | All actual site participants receive the same delta, including rotating ones. The 6:7 test preserves ±16 per person without forcing the entire group total to zero. Absentee does not receive RatingEntry                                                                                                                 |
| Selection according to actual points         | Generating and saving lineups take the PlayerRating, from starting rating of 1000 for the new profile. Test after 5-0: 1016/984 points lead to equal teams of 1000, without using fixed points from E6                                                                                                                    |
| Retros and conflicts                         | Persistent Idempotency-Key with operation imprint, expected_version Meeting and expected_rating_version. Repetition does not create a second revision or a delta; changed payload under the same key and old preview give 409. E2E loses response after actual write and recovers same revision                           |
| Recalculating Later History                  | Fixed order starts_at/ID. The test appends an older result after a newer result, and then reverses the older result: subsequent averages, deltas, and pre/post scores are updated. The order in which the results are entered does not matter                                                                             |
| Full historical correction                   | New ResultRevision and TeamSheet; old versions/author/time/reason remain. Each added/removed person requires an explicit attendance correction with a separate reason. This updates the Attendance, PDF, actual completed match roster and rankings together; source declarations are not rewritten                       |
| Privacy                                      | Ranking, point history and score do not reveal priority, block flags, reasons or attendance events. The player does not mutate or read the administrative result. Administrator sees historical lineups and reasons; the person has their own attendance correction. Points/historical profiles remain after access lock  |
| Atomicity and concurrency                    | Exclusive RatingState lock before Meeting; point and result reads have a shared state lock. Race testing over HTTP and standalone PostgreSQL sessions outside of identity lock: one write, the other old preview conflict. The injected crash after saving points rolls back the result, ratings and receipt; retry works |
| Frontend on the phone                        | Set form, expectations/deltas preview, public ranking and match history, player points history, score/lineup/attendance correction and 0:0. Desktop and emulation 360/390/430 px; no horizontal overflow                                                                                                                  |

## Implementation and limits

Migration **0007_results** adds ResultRevision, RatingState, PlayerRating, RatingCalculation, RatingEntry and ResultMutation. TeamMember.rating_snapshot is moving to Numeric. Development migration completed; Alembic check shows no differences. Downgrade with saved results is blocked so as not to delete the history. Restoring a compatible backup remains procedure E10.

Pure math: `backend/app/domain/rating.py`; clean replay: `domain/replay.py`. API and transactions: `api/results.py`, `api/result_schemas.py`, `services/results.py`. RatingEntry/RatingCalculation/PlayerRating are the current materialization of the conversion, not adding another delta to the previous materialization. Immutable inputs are ResultRevision and TeamSheet snapshot. The old calculated log values are replaced by the current replay; previous results and lineups remain in source revisions. A separate archive of all historical conversion runs has not been added.

Full replay was chosen instead of reversing old deltas: with one group and weekly meetings, this simplifies correctness and replay after corrections. The inputs are downloaded in groups and the materialization is saved in batches. As the number of groups/stories increases, the cost must be measured and checkpoints considered; a multi-year benchmark of tens of thousands of matches was not performed. The operation does not use a queue or a separate worker process.

50 digits is an explicit finite computational precision, not an infinite power/division theorem. No quantification of points after each match. The frontend uses Number only for presentation; ranking calculations and team selection are server-based.

0-0, like any other result, requires approved lineups in accordance with the accepted contract. Correction of the result does not change the historical start date. The reorder test involves adding an older result and recalculating the order; the unapproved function of moving completed match dates has not been added.

Frontend: `features/results/{ResultEditor,ResultCard,RankingPage,format}.tsx/ts`; step 03 integrated with the organizer panel, public tab in the details of the completed meeting. Changing the score/lineup invalidates the preview; conflict saves fields. Operations after loss of response retry exactly the same payload and key. Private historical reasons and lineups are only available from the administrator endpoint.

## Verification

macOS arm64, Python 3.13.18, PostgreSQL 14.24 on 55432; test data only in isolated `volleycrew_test`. Without database maybe-finance and production.

- `npm run lint` - Ruff, Python, ESLint and Prettier format correctly.
- `npm run typecheck`, `npm run api:check`, `npm run build` - correct.
- `VOLLEYCREW_TEST_DATABASE_URL=<*_test database> npm run test:backend -- -x --tb=short` - **107 passes**, including **16 E8 cases**: math/0:0/aspect, deterministic replay, write/retry, full correction and privacy, legacy result and later calculations, rollback after failure, validation, two HTTP enrollments, direct DB concurrency, behavior of locked profiles, current points in the generator, and unequal teams. One early Starlette dependency warning about TestClient transport.
- `npm run test:frontend` - **1 Vitest passed**; full score/ranking paths checked against real API and DB in E2E.
- `VOLLEYCREW_E2E_DATABASE_URL=<*_test database> npm run test:e2e` - **12 passed**, E2–E7 regression and extended venue track E8: 13 present → split/commit → 5:3 → loss of answer/retry/reload → ranking and match history → full correction to 14 actually present with private reason → point history and own attendance → correction 0:0. The result remains in three revisions.
- Alembic `check` — `No new upgrade operations detected` for development database with migration 0007; the test database undergoes migration in tests.

Chromium **158.0.8127.18**: 1440 px and Pixel 7/390 px emulation and 360/390/430 px control. The result preview and ranking with long Polish surnames were visually checked. Screenshots in ignored `volleycrew/frontend/test-results/room-attendance-court-swap-fbfa0--PDF-and-private-correction-{desktop,mobile}/`: `result-preview.png`, `ranking-*.png`, previous court/PDF. No attempts were made on a physical phone or Safari/iOS.

## Next stage

**E9 - UI A integration and attempts on the phone**. It requires a final walkthrough of the whole thing, accessibility, session/network behavior, comparison with variant A and tests on real devices. E10 still includes CI/PostgreSQL 17, amd64/aarch64 images, Pi 4, HA/Ingress suite and actual backup/restore. We do not declare production release or installation in HA.
