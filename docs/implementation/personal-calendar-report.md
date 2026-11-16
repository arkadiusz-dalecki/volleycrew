# E3/E9 - Personal calendar selection

Date: 2026-11-08. User request: button to add an appointment with application selection. Local implementation, without writing to a connected calendar and without HA deployment.

## Criteria met

- „Dodaj do kalendarza” on the next/selected meeting card, after the main declaration. Available to both the player and the administrator. Canceled/deleted/finished/past meeting occurrences are not exported from the UI.
- Dialog available with selection of Google Calendar, Outlook.com, Outlook Microsoft 365, Apple Calendar and other application. Google/Outlook opens a form with a title, start and end date, and location. Apple/other download `.ics`; UI describes import and lack of automatic synchronization. The user himself approves the event in the application.
- Time data exported as absolute UTC, also in summer/winter time. URL parameters encoded by URLSearchParams. ICS has UID, DTSTAMP, DTSTART, DTEND, SEQUENCE, CRLF, text escaping and line folding up to 75 octets without UTF-8 striping.
- No participants, PINs, sessions, invite links or Ingress prefix in export. No new dependencies or migrations for this feature. Exporting does not change the declaration or schedule.

## Verification

- `npm --prefix volleycrew/frontend run test`: **4 passed**, including new cases of winter/summer time, UTC, Polish characters, delimiters and line injection attempts into ICS.
- `VOLLEYCREW_E2E_DATABASE_URL=…/volleycrew_test npm --prefix volleycrew/frontend run test:e2e -- calendar-export.spec.ts`: **3 passed**, Chromium desktop/mobile and WebKit. Selection of providers, link parameters, actual ICS download and its dates, menu without overflow, accessibility audit, focus return and lack of a button for a canceled date.
- Lint, TypeScript/build and `git diff --check`: passed. Viewed mobile screenshot `test-results/calendar-export-*/calendar-choice.png` (generated, outside the repository).
- No save was made to the real Google/Microsoft/Apple account; is an export to a form/import, and the final acceptance testing in native applications on devices remains with the user.

## References and restrictions

[Google Developer Forum](https://discuss.google.dev/t/add-event-to-google-calendar-not-from-ical-files-but-from-urls/73879/3) describes a form with UTC date parameters. [Microsoft](https://learn.microsoft.com/en-us/answers/questions/1008125/is-it-possible-to-launch-the-outlook-app-calendar) describes Outlook form deeplink. The ICS format complies with [RFC 5545](https://www.rfc-editor.org/info/rfc5545/). Apple describes [ICS import on Mac](https://support.apple.com/guide/calendar/import-or-export-calendars-icl1023/mac) and [Import from Mail on iPhone](https://support.apple.com/en-mt/guide/iphone/ipha0d932e96/ios). We do not promise direct recording in Apple Calendar via the website or automatic updating of an already imported event.

Dev: `http://localhost:5173`. No publications, HA installations or production changes. Next step: acceptance testing of menu and import on devices, then release/PR at the user's request.

## Addendum: tiles and bulk export deprecation (2026-11-09)

„Dodaj do kalendarza” is also on the calendar tiles, in the player and admin view. At the latest user request, bulk export, its dialog, range fetch, and multi-VEVENT generator have been removed. What remains is the export of a single meeting, both from the list and from the details. Post-deprecation verification: lint and TypeScript/build passed; 4 unit tests and 6 E2E `calendar-export.spec.ts` passed in Chromium desktop/mobile and WebKit. Confirmed to work with single export and no bulk button.
