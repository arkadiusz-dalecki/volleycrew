# Meeting settlements verification

Settlement follow-up for Home Assistant package 0.3.8, verified on 2026-11-26. PostgreSQL 17 ran in dedicated disposable databases. Browser coverage uses Chromium 158 for desktop and Pixel 7 profiles, and WebKit 27.2 with an iPhone 13 profile.

## Scope delivered

- Series setup includes the total cost of one occurrence. A single occurrence can override its cost and venue. Price-only edits retain the current seat allocations and offers.
- Confirming attendance posts the split in whole grosz. Corrections show the change in shares, preserve payment history and carry confirmed overpayments forward.
- The organizer can save a BLIK number and Revolut.me link. The payment view shows these details to players with a balance due and supports reporting one transfer for several charges. The organizer can confirm or reject a report, or record a payment already received.
- Private reminders use a payable balance above PLN 100 or an open charge more than 30 days old. Pending reports are displayed separately.

Migration `0014_settlements` adds the price, payment details and settlement tables. Existing meetings and series start with a zero cost. The migration creates no historical charges.

## Verification

- PostgreSQL backend suite passed 220 tests, including fresh migrations, the exact 30-day boundary, the PLN 100.00 and 100.01 boundaries, a live seat offer surviving a price-only edit, and retries of payment and attendance corrections. [Settlement backend tests](../../volleycrew/backend/tests/test_settlements.py)
- An upgrade smoke test from `0013_google_registration` preserved a meeting with already confirmed attendance, initialized its cost and the series default to zero, and created no charges.
- Frontend passed 16 unit tests, lint, TypeScript checks, OpenAPI generation checks and the production build.
- The full browser suite passed 131 tests. The existing mobile-keyboard scenario is intentionally skipped on desktop. All eight settlement cases passed on all three profiles, for 24 successful runs. [Playwright scenarios](../../volleycrew/frontend/e2e/settlements.spec.ts) · [Acceptance cases](tasks.md#browser-acceptance-scenarios-for-settlements)
- The isolated Google login browser suite passed all 12 tests.
- Both Home Assistant packages passed the external and bundled PostgreSQL suites, including startup, Ingress, the meeting workflow, backup and restore. The amd64 run used QEMU 10.2.3 after the initial emulator crashed in an s6 startup script.

| Browser case | Verified result |
| --- | --- |
| Series and individual edits | The individual price and venue survive a series price edit. A price-only change preserves the seat. The venue change requires a new declaration for the existing seat. |
| Attendance and exact split | Twelve charges total PLN 200. The absent player has no new charge. A retry after losing the confirmation response leaves the same charges. |
| Free and canceled meetings | Neither creates a charge. |
| One payment for multiple charges | A PLN 70 payment covers the selected positions and leaves PLN 20 due. Review from two tabs produces one receipt. |
| Rejected payment | The charge is due again. The reason is visible to the payer and a fresh report can be submitted. |
| Payment methods and privacy | The copied BLIK number can be pasted. Revolut opens the saved destination. Removing the link removes the action. A second player cannot see the first player's charges or access the dashboard. |
| Reminders | The amount and age thresholds are independent. Pending amounts are excluded. Rejection can restore an age-based reminder. |
| Attendance and price corrections | Adding the fifth attendee changes the share from PLN 50 to PLN 40 and preserves the original receipt and credit. The administrator can preview and apply a separate correction to the venue cost. |

## Layout follow-up

The charges table and five-item navigation were verified on the preview in Chromium at 320 and 1280 px and WebKit at 390 px. All columns fit at these widths, and the payment description and review controls have separate spacing. The targeted settlements, navigation and UI regression passed 41 tests, with one planned desktop skip.

The follow-up keeps the charges table visible and starts with payment history collapsed. The 24 settlement browser runs passed with row selection, the pay-all dialog, cancel confirmation, successful dismissal, and clipboard coverage. The modal was also checked on the preview at 320 and 1280 px. The five settlement backend tests passed, including validation of a payment report with 101 selected charges.

The 24 settlement browser runs passed after limiting the selected-payment action to partial selections. After changing Escape handling, the focused regression passed on desktop Chromium, mobile Chromium, and WebKit. It verified that two Escape presses close the payment dialog, return focus to „Zapłać wszystko”, and allow reopening before changing the selection.

Six focused browser runs passed across desktop Chromium, mobile Chromium and WebKit. They verified that explicit zero and omitted costs produce no charges, and that confirming a payment updates the team totals. The pinned totals row was checked on the preview at 320 and 1280 px.

The payment-details scenario passed on three browser profiles after restricting payment settings to administrators. It verified the administrator form, its absence in player view, the API rejecting player reads and writes, and the payer's access to the organizer's payment methods.

The 0.3.8 release candidate passed 221 backend tests, 16 frontend unit tests, lint, TypeScript, the OpenAPI contract check, and the production build. The ARM64 package built with version 0.3.8 passed the external PostgreSQL and bundled PostgreSQL suites, including Ingress, backup, and restore.

## Remaining acceptance

Confirm the native Revolut handoff and paste into a real bank app on physical iOS and Android devices. Browser tests check the Revolut navigation destination and the clipboard with test data.
