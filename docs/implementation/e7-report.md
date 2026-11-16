# E7 - PDF Signature List

Date: 2026-11-07. Status: Implemented and verified locally. No commit, publication or deployment of Home Assistant. D7 was already approved; stage did not require new user decisions or database migration.

## Acceptance testing

| Criterion                   | Implementation and proof                                                                                                                                                                                                                                                                           |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Only those actually present | Query after Attendance.confirmed_state=present; no declarations, waitlists or absentees. Before confirming presence, API refuses 409; the button is inactive. Referencing also gives 409                                                                                                           |
| Data for school             | Date and local hours of the meeting, I LO in Gdańsk, number of people present; table No., name and surname, signature. Without nicknames, statuses, points and reasons for corrections                                                                                                             |
| Update after correction     | Each GET creates a new PDF from the current attendance snapshot. In E2E, the old preview tab downloads a list of 13 people instead of the previous 14 after correction; the deleted person and private reason do not appear in the document                                                        |
| Privacy and Permissions     | Admin role checked in backend and frontend route. Regular player 403, anonymous 401, unknown encounter 404. Also test for ?download=true. All no-store replies                                                                                                                                     |
| Read consistency            | The same Meeting lock as for corrections/additions; retrieving revisions and names before releasing the lock. Generate from an immutable snapshot in a thread pool. Export does not change the meeting version or presence                                                                         |
| Polish characters and font  | Noto Sans Regular/Bold shipped with backend, OFL license and source/hashes; embedded in PDF. Pypdf reading and visual Poppler inspection: ł, Ł, ś, ć, ń, ó, ą, ę, ż, ź in names without damaged glyphs                                                                                             |
| A4 and long names           | A regular list of 14 people with the surname Brzęczyszczykiewicz-Kowalska fits on one page. Lines min. 14 mm and wide signature column. The extreme test of 80 characters of name + 80 characters of surname for 14 people gives two A4 pages; headline repeated, all names and positions retained |
| Preview and download        | „Lista podpisów” in the header of the organizer panel leads to a separate view. Actual PDF rendered by local PDF.js on canvas, with text for screen readers. Download with a reasonable file name, refresh, separate tab and return to the meeting                                                 |
| Telephone and errors        | Chromium desktop and phone emulation 360/390/430 px, without horizontal overflow. Checked actual rendered canvas, download and network error → refresh → re-preview. We do not rely on the built-in PDF plugin, which displayed an empty frame in phone emulation                                  |
| No external generator       | ReportLab and local fonts. PDF.js and worker in the application build, without CDN. Runtime does not use Poppler or an external service and does not save a PDF archive on disk                                                                                                                    |

## Implementation

- `backend/app/services/signature_list.py`: controlled snapshot and A4 generator; names sorted by surname, name and ID, without ID on the printout. User text is escaped before Paragraph so tags don't become formatting/links. Threadpool rendering serialization protects ReportLab's shared fonts registration; the parallel documents test does not mix names.
- `backend/app/api/documents.py`: `GET /api/v1/admin/meetings/{id}/signature-list`, application/pdf, inline by default or attachment for download=true, `X-Attendance-Revision`, nosniff. Denials are in standard application error format.
- `frontend/src/features/documents/SignatureList.tsx`, `PdfViewer.tsx`: authorized route, current download, preview of all pages, loading/error/retry, warning on other presence revision. Blob URLs are released, download canceled when leaving the page; parser/worker destroyed when document changes. No permanent document cache in the application.
- Dependencies and lockfile: ReportLab **4.5.1**, pypdf **6.21.4** only in dev/test, PDF.js **6.5.438** dynamically loaded only during preview. Fonts from the pinned Noto commit, license and SHA-256 sums in `backend/app/assets/fonts/README.md`.
- OpenAPI contract and client types generated; API, domain, frontend and README updated. No data model/migration changes.

## Tests performed

macOS arm64, Python 3.13.18, PostgreSQL 14.24 on port 55432; tests on isolated `volleycrew_test`. Without production and maybe-finance data.

- `npm run lint` - Ruff, Python, ESLint and Prettier format correctly.
- `npm run typecheck`, `npm run api:check`, `npm run build` - correct. Build emits a separate parser chunk and a local PDF.js worker.
- `VOLLEYCREW_TEST_DATABASE_URL=<*_test database> npm run test:backend -- -x --tb=short` - **91 passes**, including **6 E7 tests**: A4/14 names/font, empty list and literal tags, extreme lengths with pagination, parallel rendering, permissions and presence status, update after correction/source immutability, waitlist/reference/404. The Starlette dependency warning about future TestClient transport remains unchanged.
- `npm run test:frontend` - **1 Vitest passed**; E7 features additionally checked in E2E with real API and PostgreSQL.
- `VOLLEYCREW_E2E_DATABASE_URL=<*_test database> npm run test:e2e` - **12 passes**, E2–E6 regression and extended venue scenario with PDF list, pypdf download/read for 14 and 13 people, player denied, network error and retry. An additional run of `room.spec.ts` itself controls the canvas and screenshots after rendering is completed.
- `npm --prefix volleycrew/frontend audit` and `audit --omit=dev` - **0 reported vulnerabilities** for the current lockfile.

Chromium **158.0.8127.18**, desktop 1440 px and Pixel 7 emulation with 360/390/430 px control. Poppler **26.11.0** was used to rasterize PDF and visually inspect all pages. No physical printing or attempts were made on the actual phone or Safari/iOS.

QA examples with only fictitious names (ignored in git): `output/pdf/e7-lista-podpisow-przyklad.pdf`, `e7-lista-podpisow-skrajne-nazwiska.pdf` and rendered `e7-przyklad-1.png`, `e7-skrajne-{1,2}.png`. Restore: `python3 -c 'import scripts.dev as d; d.run(d.backend("python", "-m", "tests.test_signature_list"))'`.

E2E evidence (ignored in git): `volleycrew/frontend/test-results/room-attendance-court-swap-fbfa0--PDF-and-private-correction-{desktop,mobile}/signature-before.pdf`, `signature-after.pdf`, `signature-preview-{1440,360,390,430}.png`. Screenshots taken after the preview finishes rendering.

## Further dependencies

Next stage after the order: **E8 - results, ELO and corrections**. D8 decisions remain: the scale of expectations, corrections to historical lineups and the order of matches on the same date. K=32, no intermediate rounding, 0:0 and result corrections with recalculation of later matches are already approved. E7 was not extended with these rules.

Trials of physical phones and Safari - E9. CI/PostgreSQL 17, target image with fonts, Pi 4/aarch64, amd64, Ingress with dynamic prefix (also PDF.js worker), backup/restore and HA installation - E10. Green local build does not mean ready deployment.

## Technical sources

- [ReportLab: tables and repeated headings](https://docs.reportlab.com/reportlab/userguide/ch7_tables/).
- [Noto Sans - Pinned Source and License](https://github.com/notofonts/noto-fonts/tree/ffebf8c1ee449e544955a7e813c54f9b73848eac/hinted/ttf/NotoSans).
- [PDF.js - rendering examples](https://mozilla.github.io/pdf.js/examples/) and API types from installed pdfjs-dist.
