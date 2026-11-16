# Frontend specification

## Reference

Accepted variant A in `prototype/index.html?variant=A`. `prototype/phone.html` shows it on the phone. Keep the background light, greenery, typography, tab rhythm, desktop side navigation and four mobile tabs. A/B/C switch and fictional scenarios belong to prototype/development only.

Recreate UI as components with real data. Main structure: `AppShell`, `MeetingHeader`, `ParticipationCard`, `ParticipantList`, `Waitlist`, `Calendar`, `Court`, `AttendanceChecklist`, `ResultForm`, `RankingTable`, `ProfileForm`. Match directory names to `architecture.md`.

## Routes and scope

| Route                   | Content                                                                          |
| ----------------------- | -------------------------------------------------------------------------------- |
| `/`                     | Next meeting; empty state when there is no next date                             |
| `/meetings/:id`         | Same screen for selected meeting, return to calendar                             |
| `/calendar`             | Month and list of meeting occurrences, navigation further without limit of weeks |
| `/ranking`              | Ranking and results with link to the match                                       |
| `/profile`              | Data, status, password change and private history                                |
| `/join?token=token`     | Invitation validation, name/surname, login, password and its repetition          |
| `/login`                | Username and password entry, optional Google button                              |
| `/reset-password#token` | Setting a login and a new password via a one-time grant                          |
| `/admin/settings`       | Statuses and locks, invitation link, password reset                              |

Administrative settings are an additional route, not a fifth main tab. The control panel for a specific match remains in its details. Permissions are data from the API; the frontend does not broadcast them through the switch. Before locking the profile, the administrator sees a summary: logging out the player, blocking access and releasing future places/bookings/offers while maintaining history and results. Once approved, the UI downloads the current lists.

Status „założyciel/zawodnik/gość” is not a public label. Participants and ranking in the player view do not show other people's statuses. Your own status stays in your profile and your own summary, and the admin can access the statuses in their view. Precedence rules can be explained in general terms, without specifying who has what status. The new profile receives the status „gość”; The registration form does not offer status selection. The administrator selects one of three levels. Selecting a profile distinguishes identical names and surnames with an additional nickname on the login screen, e.g. „Michał N*****k — Misiek”; the school printout contains only the name and surname. The player sets and changes his own nickname in a separate profile field. The field is independent of name and surname; saving does not change the account's identity or status. Approved 2026-11-06.

## Player meeting

Order: date/place → own state and action → number of places → preliminary court → participants/waitlist → approved teams/result. In the desktop side panel, your own ranking and subsequent meeting occurrences; on the phone, the main declaration stays before additional content.

Separate states of your own card: no declaration, confirmed participation, waitlist with position, active offer, „nie będę”, re-confirmation after changing the date, canceled, completed. The offer status comes from the API, not from position 1 on the waitlist. Each date change shows the old and new date and requires a new confirmation, also for proposals from the waitlist. The old screen with the offer, after the acceptance attempt, informs about the change and downloads the current status; does not show apparent success. When confirming again, the place waits for a response without automatic timeout. The administrator has an explicit action to free up space if there is no response; not present a waiting player as a confirmed participant.

Before opting out, a backend preview or consistently calculated information from API status makes it clear whether it will be a regular withdrawal, late withdrawal or withdrawal covered by an exception. Revalidate on commit - the time limit may have been exceeded. Freezing seat priority does not disable enrollment for free seats.

## Organizer service

1. Attendance: large touch fields next to names; separate draft saving and informed commit. Explain the effect on absence history.
   Mark a latecomer as present; correct the previous incorrect entry with the reason. The action „Dopisz obecną osobę” selects an existing profile and the API checks for free unreserved space and a limit of 14. The justification uses the corrections form while retaining the original entry.
2. Teams: „Losowo” and „Według rankingu”, then the court diagram with the number of people and the average ELO of both sides. Down to six in the half, seventh in the rotation. Spread does not mean athletic position.
3. Touching a player allows for manual transfer; the backend confirms the entire split. For full teams, allow for the replacement of two players or the draft without the intermediate entry of an incorrect lineup. Changing the draft does not change the approved lineup.
4. Commit blocks accidental edits. Returning to edit is an explicit operation under the correction policy, not a redraw in the background.
5. After the game, the result of A/B sets, summary and one confirmation. The score 0-0 closes the match with no sets played and no ELO change, maintaining presence. Correction of the result requires a reason; show the old and new result as well as information about the conversion of later matches. Points and deltas should be presented to one decimal place. The saved result can be seen after re-entering.

The list of signatures has a separate action before the meeting (confirmed enrollments) and after confirmation of actual attendance (current participants): preview and download PDF. After correcting the presence, you can generate it again (D7). Other people's history is available to the administrator in the player's screen, not through the public ranking. Upon entry, the administrator has a correction action with a mandatory reason and a summary of the change. The original post and correction can be seen in the player's private history, along with the date, author and reason; none of these items end up on public lists.

## Accessibility and resilience

- Check the widths of 360, 390, 430, 768 and 1440 px. No horizontal scrolling; court goes vertical at the narrow container. Full names remain legible, even long and repeated ones.
- Touch target at least 44 × 44 px; text of actions and names readable on the phone. Status indicated by word and color. WCAG AA contrast for texts and controls.
- Semantic buttons and labels, keyboard support, visible focus, a dialog focus trap and focus restoration. The court is also available as structured content for screen readers.
- Bottom navigation includes safe area and on-screen keyboard. Dialog longer than the screen scrolls and allows you to get to the action.
- Each data screen has a loading, blank status, retry error, and expired session status. The server error does not clear the entered result or PIN before showing the message; The PIN is not logged or permanently saved.
- Disable repeated clicks while submitting; backend protections still apply. No upbeat „masz miejsce” before reply.
- Refresh after self-mutation, return to tab and reconnect. When the meeting list is visible, polling is proposed every 30 s; after the conflict immediately. WebSocket is not required.
- Saving without connection shows an error and allows you to retry. Do not queue declarations offline. The old list screen clearly indicates a refresh problem.
- Meeting address and active tab work after refresh/direct transition, also under Ingress prefix.
- Fonts and icons provided with the application. Production UI does not require downloading Google Fonts from the Internet.

The web-app manifest and icons can be added without a service worker. The possible cache does not store private history or authorized API responses and cannot serve an old list as the current one.

The login screen does not require you to enter your full name, nor does it provide full names in your page data. Registration by invitation is a separate form that creates a new profile with your full name; doesn't show a selector for existing accounts. After logging in, the group sees the names and surnames of the participants according to the remaining specifications.

## Access in E2

`/setup#token` is a separate first organizer form, without selecting an existing profile. Public login, registration and reset screens do not show private group navigation. When you log out or lose a session, private data from the client's memory is deleted and the view returns to the login. PINs only exist in form fields and the request; are not saved in localStorage. Crew settings are also available on the phone from your own administrator profile. Changing statuses and settling future places on block will come in E4; E2 provides invitations, reset and access lock.

## E3 calendar and meeting

The month is stored in the URL `/calendar?month=YYYY-MM`. You can move with the arrows, select any month using the native field or return to the current one. Grid and list use the same API; selecting a day filters the list. Canceled meetings are labeled in text and marked with a distinct color. Opening a virtual appointment only consolidates the meeting and leads to the stable `/meetings/:id`. It is not a declaration of „będę”. Returning from the details takes you to the month of the current date, even after it has been postponed.

The next meeting retrieves the date, time, location and status from the API. Does not include a permanent restriction to Tuesdays. Details read participants/reserve from secure DTOs. Up to E4 enrollments are not available; no apparent success or fictitious list of players. In E3 there are states of loading, empty range, retry failure and old data on refresh failure.

## Participation and waitlist in E4

The own participation card is valid for the next meeting and the meeting selected from the calendar. „Potwierdzam obecność” on a virtual appointment first resolves it to Meeting, then saves the declaration; success is presented only after the answer. We show the confirmed seat, waitlist position, pre-proposal reservation, active proposal for explicit acceptance/rejection, and „nie będę”. Free and reserved seat counters explain why, for example, with 13 confirmed people there may not be a free seat.

The cancellation has its own confirmation with the current information: regular, late, except for a late accepted offer, or withdrawal of the waitlist itself. After a conflict or API error, we retrieve the current state. Request declaration preserves UUID for retries on network error; after the 4xx response and a new decision, a new key is created. We do not save declarations offline.

The organizer has a detailed booking panel. „Zaproponuj miejsce” activates the proposal and reminds you to send a manual message on Messenger. „Przekaż dalej” requires confirmation of the effect: withdrawal of the application and reservation for the next person. No automatic countdown. The status change in settings is a private admin selector. The lock summary includes future places, bookings and offers, and history retention.

## Schedule and changes in E5

Organizer settings start with a schedule: effective date, day of the week, time, game time and location. „Pokaż podgląd harmonogramu” displays the scope of existing changes, new confirmation requests, saved exceptions, and future rule examples. The entry requires separate approval. Changing any field deletes the old preview; the conflict refreshes the data and requires a new view.

In the meeting details, the administrator changes a single date or cancels the meeting after confirming the effects. When changing, the group sees the previous and current date. „Potwierdzam nowy termin” restores the previous seat; waiting lists are a separate list, not confirmed participants. The organizer may manually release a waiting space, with an explanation of the effect on the queue. Old offers from the waitlist do not offer a place on the new date.

Individual exceptions remain unchanged with the new permanent rule, as decided by the user. The cancellation is visible in the calendar and details. The two organizer tabs don't silently overwrite changes: a version error preserves the form, shows the message, and retrieves the current data. Messenger notifications are still manual.

## Presence, court and private history in E6

In the details of a permanent, uncancelled meeting, the organizer has panel „01 Obecność → 02 Drużyny → 03 Wynik”. The result is the next step E8; there is no apparent form or score record in E6.

Attendance: large „Obecny/a” and „Nieobecny/a” buttons, ability to mark everyone as present, separate draft save and separate confirmation of commit effects. The undetermined state blocks the commit. You can save your draft before starting the game; approval is available from the start of the meeting. Changing confirmed attendance requires a correction with a mandatory reason. Late arrivals are classified as present. Justification preserves the source entry. The drop-down section supports physically present reservation recipients, forwarding the reservation with confirmation and adding an existing active profile when there is a free place.

Teams: drawing or balancing according to ranking, then court of option A. Full names wrap without truncation; nickname helps distinguish people. Each half shows up to six people, the seventh appears in the labeled rotation area below the court. On a narrow screen, the halves are one above the other, on a wide one, side by side (the threshold of the width of the court itself). The player button selects him, touching a person from the opposite team swaps both people. The swap works at full 7:7 and includes rotation. The selected person can also be transferred from a larger to a smaller team. Manual corrections are saved before committing separately. Approved lineups are visible to players; Only the organizer can see the draft. Opening for correction requires a reason and re-approval.

Private history is in „Mój profil”. The organizer opens the player's history from the team settings or approved attendance list (`/admin/players/:playerId/history`). The entry includes the source classification, current value and corrections with reasons, dates and authors. These fields are missing in participant cards and public court. A regular player won't open another person's admin route or API.

Mutations show success after the server responds. Loss of the response preserves the exact operation and its key to explicit retries. Version conflict refreshes the state but does not overwrite local patches: the user sees a warning and a button to load the current list/lineups. Unsaved local fixes are not published and are not used for approval.

## Signature List - E7

In the header of the organizer's panel there is „Lista podpisów”, available before the meeting from confirmed enrollments, and after confirming attendance from those actually present (change D7 from 2026-11-08). Takes you to the administrative route `/admin/meetings/:meetingId/signature-list`, back to a specific meeting. A regular player does not have a button or access to the route/API.

Preview renders the actual PDF locally via PDF.js, also on a phone without a built-in PDF viewer. The parser and its worker are delivered with the application, loaded only during preview; they don't use CDN. All pages are shown in tab width. The text layer for screen readers contains the content of the document. A separate link opens the PDF in a new tab.

„Pobierz aktualny PDF” always executes a new authorized request and takes into account corrections, even if the previous preview was open in another tab. „Odśwież podgląd” is redownloading the document. Comparing the revision with the polled presence allows you to warn about a change in the list. There are generating, rendering, error, retries, and expired session states; preview and download operation are released/cancelled when leaving the page. The PDF does not go to localStorage or the application's persistent cache.

Printout: A4, scale 100%; PDF viewer provides printing. The source of the current list is clearly described in the preview. Before the presence is confirmed, the document is created from the confirmed places and later from the confirmed actual presence.

## Results and ranking - E8

Step „03 Wynik” in the organizer panel is available after confirming lineups. The two large numeric fields show the A/B sets. „Pokaż podgląd punktów” retrieves the calculation from the server; separate „Zapisz wynik i ranking” publishes them together. Changing the fields invalidates the preview. For 0:0 there is an explicit message about closure without sets and without ELO entries for this match. The old version of the match/ranking requires a new view; the error does not delete the fields, and the loss of the response allows you to repeat the same operation with the same key.

After saving, the organizer sees the result, deltas per person, pre-match averages, author/time versions and private history of reasons/lineups. „Skoryguj wynik lub składy” opens a form with a mandatory reason. The lineup is edited by touch on the same court; each change to the set of present requires a separate classification and a private reason. The UI does not add an eighth player to either side and blocks the approval of the incorrect number. During historical editing, it does not show apparent averages for a lineup that has not yet been calculated. After the preview, all corrections are approved separately.

In the details of the completed match, the player has a scorecard and current teams. „Ranking” contains views „Punkty zawodników” and „Historia spotkań”, with pagination and refreshing every 30 seconds. A player without matches has 1000.0 points; points and deltas are presented to one place. Clicking on the name opens `/ranking/players/:id` with before → delta → after history and links to matches. The score 0-0 is in the match history, but not in the points log.

Reasons for result/lineup corrections are visible only to the organizer, and private reasons for presence only to him and the given person in the profile. The public ranking, points history and scorecard do not include priorities, block flags or absence events. There are separate loading, error and retries states. Amendments are not published optimistically.

## E9 Integration

Cancellation, transfer, hold and single change/cancellation confirmations use a common native dialog. Escape and cancel do not save changes; focus returns to the button that opened the dialog and, when removed, to the main content. Canceling the appointment edit preview preserves the form.

On an error refreshing a session with preserved identity, the UI remains open with a warning and a retry. The venue/result and schedule editors and history corrections are not dismantled in the event of a temporary failure to read already downloaded data. Confirmed 401 removes private data and leads to login; after logging in, we return to the desired internal route. Simply entering the login without a memorized route will take you to the meeting after logging in. A failed save is not an offline queue: the user consciously retries it.

The manifest and icon are local, without a service worker. The bottom navigation includes safe area and keyboard detection by visualViewport. Chromium/WebKit and keyboard geometry checking does not constitute acceptance testing of physical phones; the current status is in [report E9](e9-report.md).

## E10 package inputs

Nginx renders `<base>` separately for regular input and the current Ingress prefix. `lib/base.ts` provides the router basename and API client base URL. All new API calls and resources must maintain this context; do not construct the URL from `window.location.origin` alone or the hand-encoded Ingress token. The PDF.js manifest and lazy worker resolve against this base URL. Both entries require their own Volleycrew login, with separate cookie names/paths and proper CSRF. Production image tests are separate from Vite in `container-tests/`.

## Calendar supplement - 2026-11-08

The date (day of the week, day, month, year) is the main heading of the green meeting card; time and place are below. The side menu displays the appointment with `/meetings/next`, refreshed every 30 s and after mutations, also when another appointment is open. Supports loading, missing deadline and retry failure.

Scheduling available only to the administrator in `/calendar`: „Dodaj spotkanie” and „Zaplanuj serię”. You can also select an empty grid day as the date for a new appointment. Adding requires preview and approval. The series includes the day of the week, time, game time, location and from-to range; end in UI is inclusive, optional, after it the previous schedule returns. The preview explains the replacement of an existing rule and reconfirmations. A single change from Tuesday to Wednesday is performed by pressing the „Zmień termin” button on the calendar tile; meeting details retain previous actions. Crew settings include access and players.

### Actions on the tile - 2026-11-08

The future scheduled meeting tile in the calendar has „Zmień termin” and „Odwołaj” buttons for the administrator. The first expands the date, time and game time form on the same tile; The registration still requires preview and confirmation of the effects on the registered users. The second one opens the cancellation confirmation dialog. The view remains in the calendar; after shifting, the active date filter and possibly the month move to the new date. A revoked tile remains in status, with no further change/revocation actions. The player cannot see these buttons.

### Smaller team placement - 2026-11-08

Court adjusts the layout to the number of players in the half rather than displaying six spaces with empty markers. One person is in the middle; two are positioned front/back; three is one at the net and two behind; four is 2+2; five is two at the net and three at the back; six is 3+3. A seventh person remains on the rotation panel. Both teams face the net, also with the vertical court on the phone. This is an illustrative layout, without changing player assignments or split rules.

## Supplement E2/E9 - fixes after trying on iPhone (2026-11-08)

The 2026-11-15 update replaces the profile list with a login and password entry. After success, we only remember the localStorage login; the password only remains in the form and request. Locked localStorage does not prevent login.

The administrator has a „Administrator / Użytkownik” switch above the content, also on the phone. In the user view, it has its own profile and declarations, as well as the usual calendar, approved teams and result views; there are no administrative tools or routes. Switching from route `/admin/…` leads to a meeting. View selection is maintained in sessionStorage per account; server permissions remain unchanged. This is a preview of the interface on your own account, not logging in as another player.

Signature „Dobra ekipa, trochę ruchu i dwie godziny dla siebie.” removed. The single term form does not have a fieldset frame; date and time fields are limited in width in Safari as well, and narrow forms use a single column.

On the access screens and in the application footer it is „Dodaj aplikację do telefonu”. If the browser provides `beforeinstallprompt`, clicking brings up the system window. In other cases, the button opens a dialog with instructions specific to iPhone/iPad, Android or computer. iOS requires using the Share → To Home menu; the site cannot perform this step automatically. When standalone mode or appinstalled event is detected, the button disappears. The manifest contains local PNG 192/512, and iOS gets apple-touch-icon 180. We do not add API cache or offline work. Installation requires an HTTPS target address; physical acceptance testing of installation and entry via HA remains a separate test.

## Management of existing series and printing before the meeting (2026-11-08)

The admin calendar has a permanently visible list of „Twoje serie spotkań” with the actions „Edytuj serię” and „Usuń serię”. Editing loads the selected rule, including the existing Tuesday default, and requires a preview before saving. The scope shortening shows the number of existing meeting occurrences to be removed; other rules are not automatically overwritten. Removing a series requires a dialog with the scope of future encounters and information about retained history. „Zaplanuj serię” remains a separate rule creation.

„Usuń spotkanie” is available on the tile and in the details of the future or canceled date. The dialog explains the disappearance from the calendar, the closing of enrollments/offers, and the behavior of other meeting occurrences. After deleting in detail, we return to the month in the calendar. Action „Odwołaj” still leaves the entry as revoked; „Usuń” allows you to remove it from view.

The „Lista podpisów” button in the organizer panel is also active before the start and confirmation of attendance. The preview shows the source: confirmed enrollments or confirmed actual attendance. Before the meeting, it allows you to download and print an A4 document to collect signatures at the venue. It does not require confirming attendance from home. Changing meeting data after generating a preview shows a warning; download always downloads the current list. This finding replaces the previous restriction of E7/D7 to those actually present.

## Adding an appointment to your personal calendar (2026-11-08)

On the card of the next and selected meeting, after your own declaration, there is „Dodaj do kalendarza”. Available to the administrator and the player, also before signing up for the game. The dialog shows the current date, time and place and the selection: Google Calendar, Outlook.com, Outlook Microsoft 365, Apple Calendar (.ics), other application (.ics). The user approves the entry in the external application himself. Export does not change the declaration.

Google and both Outlook variants open the form in a new tab. Apple/other download ICS file for import; for iPhone UI provides the option of importing from Mail, and for Mac opening in Calendar. The UI explains the lack of automatic synchronization of subsequent changes/references. Canceled, deleted, ended or past meeting occurrences do not have a button. The export contains only the title, date and place; it does not contain a list of participants or an Ingress link/authorization.

### Export from list (2026-11-09)

Each eligible calendar tile has „Dodaj do kalendarza” with the same app selection as the details. Bulk export has been removed at user request: there is no multi-meeting button, month/12 month range, or bulk ICS generation. All that remains is to export one term.

## Preliminary court (2026-11-09)

Above the list of participants for the scheduled meeting is „Wstępne drużyny”, marked with „Z zapisów” and information about unverified attendance. Court uses Variant A layouts, shows names and ELO averages. With fewer than two people, show an empty state explaining the requirement for displaying the court. They can be seen by the administrator and users, as well as the user preview in the administrator account.

Own „Potwierdzam obecność”, resignation and acceptance of the offer refresh the court immediately; on other devices, the reading takes place every 30 seconds and after returning to the card. Admin has „Według ELO”, „Losuj wstępne składy”, swap by touching a person on both sides and transfer from a larger team to a smaller one. The save is shared by the crew; changing the declaration restores the current ELO split. An outdated list/revision needs to be refreshed instead of overwritten. A read error preserves the last split, a loss of write response allows you to retry without a second draw.

Once attendance is confirmed, the preview disappears and step „Drużyny” becomes „Użyj wstępnego podziału”. Usage is explicit; the revised list of those actually present is re-aligned according to ELO. The preview itself does not confirm attendance, teams or score.

## Gesture navigation between meetings - 2026-11-11

On `/` and `/meetings/:id`, swiping left opens the next meeting, and swiping right opens the previous one. The same actions are available through keyboard-accessible buttons with accessible names for screen readers. Order according to current start time and ID, as in the calendar; we skip the deleted ones, we show the canceled ones. No neighbor disables the button. Virtual occurrences are opened using the existing occurrence resolution, without a declaration of participation.

The gesture requires a clear horizontal movement of one finger. Vertical scroll, short flick, multi-finger gesture, and motion initiated on a control/form/dialog do not navigate. Error reading adjacent meeting occurrences has the message and retry, without deleting the current meeting.

## Smooth tile movement - 2026-11-11

The user ordered a graphical transition between meeting occurrences: the entire meeting tile follows the horizontal gesture; short/cancelled gesture returns to the starting position. After the change, the current tile leaves in the direction of the gesture, and the new one enters from the opposite side. The buttons use the same transition. Fetching details precedes the output animation; error preserves the current deadline. The gesture is limited to the tile, retaining scrolling and excluding controls. The reduced-motion preference disables animations.

Update 2026-11-16: adjacent navigation preserves vertical scroll and the main-screen layout, without adding a calendar back-link when browsing from `/`. Direct details opened from the calendar retain the back-link. The application shell remains mounted when the URL changes; the route error boundary resets its error state without rebuilding healthy content. The exit lasts 140 ms with 24 px additional movement and opacity 0.94, followed by a 180 ms entry from 24 px at opacity 0.94. This replaces the previous full-card exit and fade to zero. Reduced motion disables both animations. Other page navigation still resets scroll and focuses main content.

## Access links - supplement E2/E9, 2026-11-14

The invitation reads the token from the query `?token=…` (change 2026-11-15 for Messenger) or from the old fragment `#…`. Bootstrap, reset and Google grants only read the secret from the `#…` fragment. After reading, the browser replaces the current address with the address without the fragment and query, preserving the Ingress base path. The secret remains only in the memory of the mounted form, without localStorage/sessionStorage and without the router's history state. Refreshing requires reopening the full link; the screen explains this situation. Opening another fragment on the same route also works without fully reloading the document. The former `/join/:token` and `/reset-pin/:token` remove the token from the address and show information about reopening the full link, without using the secret from the path. Valid existing `#…` links still work and just opening does not consume a reset. With HTTP 429, the form reports the time `Retry-After` provided by the server, without automatic re-mutation.

## Optional Google - 2026-11-15

Once Google is set up, the entry screen has a locally rendered „Zaloguj przez Google” button with the official icon and local Google Sans. No external script, fonts/CDN in runtime; only a conscious transition to the supplier. Login and password still work. The logged in profile has a Google section: connect or disconnect after password confirmation. The account/role is not selected from Google data; the association is with the current existing profile. Messages include cancellation, invalid flow, provider error, unlinked account, binding conflict, and session loss. The return status is a permanent code in the fragment, removed from the address after reading; no Google token goes to JS/storage. After logging in, we return to the desired internal route. Merging success is visible at the top of the profile; detaching leaves the current fresh session and informs about the invalidation of the remaining ones.

In Ingress or with an origin other than PUBLIC_URL, the button opens the main domain in a new tab with noopener/noreferrer. For connection it indicates `/profile` and requires logging in there with login and password, and for input `/login`. UI explains the separation of sessions. Acceptance testing of real Google and physical Safari/Chrome remains a separate operator test.

## Login and password - updated 2026-11-15

Replaces the previous login/PIN directory rules: two typed Login/Password fields, no profile list or public directory download. The login has autocomplete=username, correction and capitalization disabled; current-password/new-password, without numeric keypad and 6-digit limit. New password and repeat: 8-128 characters, phrases with spaces/Unicode, matching validation before submission. The form retains data on error. Upon success, secrets are cleared; we only remember the username, never the password. The profile shows your own login and password change with confirmation present. Google connects/disconnects by password, messages refer to login and password. Reset allows you to recover your login and password; bootstrap an existing organizer sets new data without changing its profile. Fragments of links are still removed from the address.

## Join via Google - 2026-11-15

On `/join?token=token`, after enabling Google, we show Join via Google regardless of the regular registration fields. In Ingress we open canonical `/join?token=token` with noopener/noreferrer. After OAuth, `/join/google#token` clears the secret from the address and retrieves hints via POST; the form has an editable Name/Surname and an optional nickname, without a login/password. Approval creates a profile and logs in. Missing supplier names allow you to fill in the blanks; read error has retry. Refreshing requires reopening the invitation, without the secret in the storage/query key.

The Google-only profile shows your own data, information about Google as a login method and a button to add an optional login/password. New Google evidence leads to `/profile/password#token`; the form respects the existing login/password policy. Unlinking Google without a password is not offered. After adding a password, the existing password change and disconnection options are available. A known sub, when re-invited, does not show a form that overwrites the existing name. Blocked, session loss, expired/revoked link and HTTP 429 have safe messages; no automatic re-mutation.

Token missing message follow-up (2026-11-15): Messenger advice to copy the full link from the original message and paste it into Safari or Chrome.

## MWG fixes - 2026-11-15

Common access data fields have explicit labels linked by for/id and retain username/current-password/new-password. The „Pokaż hasło” button is an aria-pressed switch with immutable name and specific field context; does not submit the form or change the password. Password repetition uses native constraint validation even after changing the first field. The message and aria-invalid appear after a failed submission attempt, the focus goes to the incorrect field, and editing removes the apparent error. The format hint is above the field.

Text sizes are relative, without overriding the root size. Meta text-scale enables native OS preferences where supported; regular zoom remains available. Layout and controls grow/wrap text. Dialog and backdrop have CSS to limit scroll forwarding; lack of support in Safari is not circumvented by hiding the html/body scrollbar.

The private shell and individual views load on demand. Download error has message and explicit reload; private shell preserves navigation on subpage error. The route area reserves the height of the initial viewport, and static skeletons replace the short loading text to prevent the footer from momentarily appearing in place of future content. We do not add skeleton animations or private API cache.
