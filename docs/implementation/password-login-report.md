# E2/E9 - login and password entered

Update: Google sign-up by invitation and passwordless account expands the scope described. Final status and results: [Google registration report](google-registration-report.md).

Date: 2026-11-15. The user replaced the previous profile selection and PIN with a separate username and password. He confirmed that the only profile registered was the organizer; Player migration is not needed. The change extends open PR #11 with Google. Without deployment and without changes to the production database.

## Behavior

- Login 3–32 ASCII characters (letters/numbers, dot, dash, underscore), normalization to lowercase letters and trimming leading and trailing spaces. Uniqueness enforced in PostgreSQL; simultaneous registrations and different capitalization do not create two accounts with the same login.
- New password 15-128 Unicode code points, no truncation, normalization or whitespace removal. Argon2id with random salt and existing parameters. The frontend also counts Unicode for emojis, supports password managers and a full keyboard. Without changing the global validation of other forms.
- Registration and bootstrap require login/password; registration still requires an active invitation and admits a guest. There is no public login/profile directory or list selection.
- Changing your password requires your current password. Organizer reset works via a one-time 30-minute URL snippet; allows you to set a password and recover/replace your login. A name conflict does not consume the grant. Reset disconnects Google; changing the password yourself preserves the association. The changes invalidate previous sessions/grants and leave the current device session fresh.
- Google still indicates existing profile by verified sub. Connection/disconnection requires current password, no PIN. Profiles without a password set after migration also do not log in via the old session/Google.
- Permanent limits of 5 errors/account and 30/source in a 15 minute window; Google confirmations share an account counter. No account and blocked account have the same error and cost to check the replacement hash. Burst protection before DB access, secretless logs, CSRF, Ingress separation and canonical OAuth remain.
- Your own login is visible in the profile and in the account/organizer's responses; it does not go to the group, participant or PDF lists. The browser only remembers the login; passwords are not saved in storage.

## Migration and organizer support

`0012_password_login` changes the PIN column to nullable password_hash, removes old PIN hashes and adds a private unique username with pair and format restrictions. Changes the grants table to password_reset_grants, invalidates old sessions and grants, and deletes pending Google flows. Profile data, history, enrollments and ELO remain. Old PINs are not passwords and there is no player migration endpoint.

For the organizer without new data, a new operator grant setup is available: new random BOOTSTRAP_TOKEN in the HA + restart + PUBLIC_URL/setup#token options. The old used token is not reactivated. Setting data preserves existing ID, role, status, name and history, disconnects previous Google and closes bootstrap again; subsequent tokens do not replace an account with an already set password. Non-HA alternative: npm run auth:bootstrap -- --rotate. Procedure and pre-update copy: [DOCS](../../volleycrew/DOCS.md#switching-from-pin-to-login-and-password).

Downgrade preserves profiles but **does not restore PINs or logins**; is not an access rollback procedure. Rollback requires a compatible image and pre-upgrade copy. The package version remains 0.3.4 (no version change request). Automatic startup backup also detects head migration changes.

## Verification

- Local PostgreSQL 17.11, Python 3.13.18, Node 26.8.1, macOS arm64. Only test database: volleycrew_password_test and a separate volleycrew_password_e2e_test on a temporary loopback cluster. After separating the databases, full backend: **197 passed**, 2 existing HTTPX warnings. The new tests include login format/normalization, password length and accuracy, non-disclosure, login competition, shared limits, login recovery, and transitioning the existing organizer with data preservation and bootstrap closure.
- **10 frontend unit tests** passed, including Unicode/whitespace and Ingress forms. Lint, types, OpenAPI contract and build passed locally.
- Full E2E desktop/mobile/WebKit: **83 passed, 1 intentionally skipped on desktop** (4.3 min). Dedicated Google: **6 passes** (20.5 s), with password connection, login to the same profile and disconnection. The local issuer signs the RSA; callback, PKCE and sessions executes the actual code. Mobile login and profile screenshots checked visually; saved locally outside the repository.
- Docker locally unavailable; actual amd64/aarch64, HTTPS/Ingress and CI backup/restore images for final HEAD PR. PR result; local builds/Google dummy do not replace these tests.

## Limitations of acceptance testing

No Google project or real account setup, no deployment to HA, and no acceptance testing performed on physical phone/PWA. After deployment, the organizer must set the login and password once via a new setup link. Existing sessions/PINs are intentionally invalid. Full player migration and email login are not included in the order.

Length policy basis: [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), read 2026-11-15. The document is not a declaration of complete compliance with NIST/ASVS.
