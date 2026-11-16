# E2/E9 - Messenger passwords and invites

2026-11-15. Scope requested by the user; branch `fix/password-and-messenger-invites`.

## Behavior

- New password: 8-128 Unicode code points, without forcing uppercase letters, numbers or special characters. Registration, bootstrap, reset, change and add password use common validation. Spaces, Unicode, Argon2id and login limits preserved.
- Newly created invitations: `/join?token=…`. The form reads the token from query before the fragment, so additional parameters and removing/replacing the fragment do not remove the invitation. The old `/join#…` still work. A link opened from Ingress to public Google also transfers the invitation in query.
- Query/fragment are deleted by the History API after reading, without saving to storage. Refreshing still requires reopening the full link. Google reset/bootstrap/grants don't accept tokens in query. The change does not require database migration or rotation of existing tokens.
- Nginx now skips the URL in access logs and sends no-referrer/no-store; The API does not keep access logs. The added no-referrer meta also protects opening the page outside the Nginx package. An external proxy should not log query invites; the operator's manual describes this difference.

The token missing message further explains that in Messenger you can copy the full link from the message and paste it into Safari or Chrome. The hint applies to the original message, not the already sanitized website address.

## Diagnosis and limits

The user confirmed that the same full link works when copied to the browser, but the token is missing in Messenger. No actual modified URL or access to physical Messenger was obtained. The test showed that the query `fbclid` in front of an existing fragment does not break the existing form; delayed fragment is also supported. So we do not attribute any proven specific modification to Messenger. The changed invite transport removes the dependency on fragment behavior in the intermediate browser. The regression for the query with the replaced fragment first did not pass, but after the change it did.

## Checks performed

- PostgreSQL 14.24, separately created local database `volleycrew_access_fix_test`, without the use of development/production. `test_auth.py`, `test_password_auth.py`, `test_google_registration.py`, `test_auth_protection.py`: **48 passed**. Registration, change/reset and 8 character password login, invitation invalidation, Google associations and access protection.
- Full Vitest: **15 passed**; query/old fragment, tracking parameters, delayed fragment, ignoring queries for grants and Unicode and password lengths.
- After adding the Messenger tip, `auth-links.spec.ts` was retried: **9 passes** in three projects.
- Playwright `auth-links.spec.ts`, `auth.spec.ts`: **12 passes** in Chromium desktop, Chromium mobile and WebKit iPhone. The tests use a separate API and the above test database after the backend is finished. Full registration and 8-character password reset, login, lock, invitation withdrawn, old and new format, address clearing/no token in storage, refresh. Locally run browsers; emulation does not replace the physical iPhone.
- `npm run lint`, `npm run typecheck`, `npm run api:generate`, `npm run api:check`, `npm run build`, `git diff --check`: passed. The OpenAPI contract remains unchanged in the fields (at least the new password is the model validator).

At the local verification stage, no HA images (Docker unavailable), deployment or physical test of Messenger were performed. GitHub CI results are available in PR. The package version remains unchanged. After deployment, create a new invitation link with query and check its direct opening from Messenger on the phone.
