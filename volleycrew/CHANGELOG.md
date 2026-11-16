# Changelog

## 0.3.6

- Improve modal scroll containment without changing the page scrollbar or scroll position. Safari retains native focus isolation where backdrop containment is not supported.
- Identify mismatched passwords with an accessible field error and native focus handling across registration, reset, profile and Google password setup. Add a password visibility toggle that preserves autocomplete and the entered value.
- Respect larger browser text preferences, opt into OS text scaling where supported, and let controls and headings grow or wrap.
- Reserve space while routes and meeting/ranking data load to avoid the footer jumping through the initial viewport. Load private views on demand and show recovery controls when a view download fails.
- Accept new passwords of 8–128 characters and make invitation links work without preserving a URL fragment, including Messenger browser handoffs. Existing fragment invitations still work; reset/setup/Google grants remain fragment-only. External proxies must not log invitation query parameters.
- No new database migrations compared with 0.3.5. Back up before updating the Home Assistant app normally. Upgrades from 0.3.4 or earlier still require the 0.3.5 login migration and organizer setup described below.

## 0.3.5

- Replace profile selection and PINs with a private username and password. Keep existing profiles, participation history and ELO; old PINs and sessions no longer work.
- Add optional Google login and invite-only Google registration, with editable first/last name suggestions and no password required. Protect the last login method and allow adding a local password after confirming the same Google account again.
- Keep invitation/reset secrets out of request URLs, show retry delays, and add bounded security logs and protection against bursts of authentication requests.
- Apply migrations 0011–0013 on upgrade from 0.3.4. Back up the app/database first. Set a new random BOOTSTRAP_TOKEN in HA, restart, and open PUBLIC_URL/setup#TOKEN to choose the existing organizer's username/password; then clear the token. See [the migration guide](DOCS.md#przejście-z-pin-u-na-login-i-hasło).
- Google remains disabled until both client credentials and the canonical callback are configured. Rollback requires a matching database backup and app version; older versions do not support Google-only accounts.

## 0.3.4

- Move the entire meeting card with the swipe gesture and smoothly return it after a short or cancelled drag.
- Animate next/previous meeting transitions from gestures and buttons; load meeting details before sliding out to avoid a loading-screen flash.
- Keep the current meeting on a loading error and respect the system reduced-motion preference.
- No new database migrations. Update the Home Assistant app normally after taking a backup.

## 0.3.3

- Swipe left or right on the meeting screen to open the next or previous meeting; offer matching navigation buttons.
- Follow calendar order across months and years, including rescheduled and cancelled meetings while skipping deleted entries. Navigating does not change participation declarations.
- Keep the login profile list usable when a private request returns 401 after logout.
- No new database migrations. Update the Home Assistant app normally after taking a backup.

## 0.3.2

- Show preliminary ELO-balanced teams from confirmed enrollments before attendance, with shared administrator random/manual overrides and automatic resets when declarations change.
- Allow using the preliminary split after attendance confirmation; rebalance actual participants when the roster differs.
- Add migration 0010 for preliminary team overrides.
- Add a calendar picker to meeting details and calendar cards for individual events. Support Google Calendar, Outlook, Apple Calendar, and other compatible apps.
- Delete individual meetings, including cancelled entries, without regenerating them from recurring schedules.
- Edit or remove existing recurring series from the calendar, with previews, enrollment protection, and preserved game history.
- Print signature sheets before a meeting from confirmed enrollments; use actual attendance once confirmed.
- Clarify the signup action as “Potwierdzam obecność”.
- Add migration 0009 for hidden deleted-occurrence markers. Back up before updating.

## 0.3.1

- Fix mobile calendar forms, including date and time inputs overflowing their card in Safari.
- Replace login profile cards with a dropdown and remember the last successfully authenticated profile.
- Let administrators switch between administrator and player views on their own account.
- Add an installation button with browser prompts where supported, iPhone and Android instructions, and local app icons.
- Remove the introductory sentence below the next-meeting heading.

## 0.3.0

- Manage single meetings and weekly series directly from the calendar, including an optional end date and restoration of the previous schedule afterward.
- Reschedule or cancel a meeting from its calendar card, with confirmation and enrollment protection.
- Make meeting dates more prominent and show the actual next meeting in the sidebar.
- Clarify declaration buttons and attendance prerequisites. Adapt court formations to 1–6 players, center unequal teams, and keep the seventh player in rotation.
- Add an explicit local preview with 14 demo profiles and role switching; preview controls are excluded from production builds.
- Apply migration 0008 to distinguish additional meetings from recurring occurrences. Back up before updating.

## 0.2.0

Własny PostgreSQL 17: bez osobnego serwera i ręcznego hasła bazy. Pusty host wybiera własną bazę, istniejący zachowuje zewnętrzną. Trwałe dane, prywatny listener, automatyczny backup i restore HA przed migracjami; blokada niejawnej zmiany trybu. Testy kontenerowe obejmują restart, awarię, aktualizację i odtworzenie. Walidacja pokazuje nazwy nieprawidłowych pól bez ich wartości.

## 0.1.1

Naprawa instalacji w Home Assistant: baza Debian jest przypięta bezpośrednio w Dockerfile. Usunięto przestarzały `build.yaml`, którego walidator odrzucał referencje obrazów z digestem. Parametr `BUILD_FROM` przekazywany przez Supervisor nie może już podmienić bazy na Alpine. CI odtwarza ten parametr dla obu architektur.

## 0.1.0

Pierwszy pakiet do samodzielnej instalacji w Home Assistant: lokalny build, statyczny frontend wariantu A, API, migracje, oddzielne wejście Ingress i bezpośrednie, bootstrap administratora z tokenu, backup PostgreSQL i konfiguracji oraz bezpieczne odtwarzanie do pustej bazy.

Nie jest to deklaracja odbioru na docelowym Raspberry Pi ani fizycznych telefonach. Stan weryfikacji jest w `docs/implementation/e10-report.md` w repozytorium.
