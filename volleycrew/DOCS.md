> Patch 0.1.1: Fixes `apt-get: not found` installation error. Once the patch for `main` is available, refresh the repositories in the HA store, check for version 0.1.1 and reinstall. Do not delete the database or configuration. The package no longer uses `build.yaml`; Debian base image is pinned in the Dockerfile and does not depend on `BUILD_FROM` passed by Supervisor.

# Install and operate Volleycrew in Home Assistant

## Installation without SSH

1. From version **0.2.0 Volleycrew includes bundled PostgreSQL 17**. Do not install a separate server: leave `DATABASE_MODE: auto` and `POSTGRES_HOST` and `POSTGRES_PASSWORD` empty. The database, user and random password will be created automatically in the persistent `/data`. The existing host retains external mode.
2. Add `https://github.com/arkadiusz-dalecki/volleycrew` in the HA app store repository settings. The package code must first reside in this repository; local files on Mac are not automatically available in HA. You configure access to the private repo on your side.
3. Refresh the store, select **Volleycrew** and install. HA builds an image on the device. On Pi 4, the first installation may take a while; exact RAM and time need to be measured on your device. There is no `image` field indicating the finished Volleycrew image or the need to publish your own GHCR image.
4. Complete the options below. Prepare your application's own HTTPS address and point the existing tunnel/proxy to port **8200**. Cloudflare configuration is left to you. Do not route the public tunnel to Ingress port **8099**.
5. Generate a random token of at least 32 characters from letters, numbers, `-` and `_`, e.g. in a password manager, and enter it as `BOOTSTRAP_TOKEN`. This is the token of the first admin of **Volleycrew**. Generate a separate string - do not use the GitHub token or Home Assistant API. Don't post it to the chat or put it in the repository.
6. Save the options and run the application. Start order: validation → maximum about 60 seconds of waiting for DB → backup required before update → migrations → API/Nginx. A configuration or migration error stops the startup. The logs do not print the DB token or password.
7. Open `https://your-app.example.com/setup#YOUR_TOKEN`, enter your name, surname, login and your own password (8-128 characters). The token is valid for 30 minutes from the time the grant is created. Restart does not extend the validity period. When it expires, enter a new token in the options and restart.
8. After creating the administrator, remove the `BOOTSTRAP_TOKEN` value from the options. Bootstrap remains locked in the database, even after restart and token change. You invite additional players from the crew settings in Volleycrew.
9. Enable run on HA startup and optionally an item in the side panel. Check the normal domain address and **Open the web interface** via Ingress. Both entry points require the Volleycrew password; HA permissions do not grant the application administrator role.

The app does not ask for access to the HA API, Docker, or home configuration files. Private `/data` is durable; the backend only listens on `127.0.0.1:8000` inside the container. Ingress only accepts traffic from the Supervisor address `172.30.32.2`.

## Options

| Option                         | Value                                                                                                                                                                                                  |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `DATABASE_MODE`                | `auto`: empty host → bundled database, given host → external. Also `embedded` and `external`. Changing the persisted mode requires explicit data migration                                             |
| `POSTGRES_HOST`                | Blank for bundled database. For external: address of the server reachable from HA                                                                                                                      |
| `POSTGRES_PORT`                | External database only, usually `5432`; own uses private 5432                                                                                                                                          |
| `POSTGRES_DB`, `POSTGRES_USER` | External options. Bundled database uses `volleycrew` and the role without superuser                                                                                                                    |
| `POSTGRES_PASSWORD`            | Blank for bundled database: persistent password is generated automatically. In external mode, user password                                                                                            |
| `POSTGRES_SSL`                 | `prefer` default; `require` requires encryption, `verify-full` additionally verifies the certificate and hostname. `disable` only for deliberately selected local connection                           |
| `PUBLIC_URL`                   | Volleycrew HTTPS address, without path, query and fragment, e.g. `https://volleycrew.example.pl`                                                                                                       |
| `ADDITIONAL_ORIGINS`           | List of additional **origins**, e.g. `["https://ha.example.pl"]`. Enter the HA address if you are using Ingress. Without path and trailing `/`                                                         |
| `TRUSTED_PROXY_CIDRS`          | Only the address/CIDR of the actual tunnel/proxy reaching port 8200, e.g. its single address `/32`. By default, there are no trusted proxies. Do not enter the entire Internet or all private networks |
| `SESSION_SECRET`               | You can leave it blank: a permanent random key `/data/auth.key` will be created. The custom value must be at least 32 ASCII characters excluding spaces; keep it in a backup                           |
| `BOOTSTRAP_TOKEN`              | Random first administrator token: at least 32 letters, digits, `-` or `_`; remove it from the options after registration                                                                               |
| `BACKUP_HOUR`                  | Daily local backup time, default `3`, by `Europe/Warsaw`                                                                                                                                               |

With `verify-full`, provide the client with a trusted DB server CA certificate according to the PostgreSQL configuration. The package does not include access to the `/ssl` HA folder or automatic copying of certificates from other applications.

HTTPS is also required for the HA page opening Ingress: cookies are `Secure`. The public address and HA address can be different origins; both must be explicitly allowed. Their sessions have different names and cookie paths, so that entries on the same origin do not conflict.

If you don't know the address of your proxy, initially leave the trust list empty, open the site through a tunnel and check the source address in the application's Nginx log. Then add only the correct address/CIDR. Only a trusted peer can provide `X-Forwarded-For` and HTTPS information. `X-Ingress-Path` headers from public input are ignored. The access log contains method, status and address; skips paths, queries, cookies and form content.

## Backup

The package saves consistent `pg_dump` in custom format, metadata, key and options in a private archive `/data/backups/volleycrew-….tar.gz` with permissions 600. The key and configuration are sensitive - the archive is not self-encrypted.

In bundled database mode, PostgreSQL only listens on `127.0.0.1:5432` in the container; port is not published. `/data/postgresql` contains a persistent cluster. `/data/postgres-password` contains a random password with permissions 0600. Do not delete these files to repair the boot.

Each valid backup also atomically saves `/data/postgres-recovery.tar.gz`: a complete logical archive to be restored by HA. HA stops the application for the duration of its backup (cold backup) and saves full, consistent cluster files. Standard HA restore recreates this cluster. If the restored set contains only a logical recovery archive, the cluster is recreated and the data is restored before migrations and APIs. Profiles, passwords and sessions are retained. An incomplete archive blocks the start instead of replacing the data with an empty database. The major version of PostgreSQL remains 17; changing it requires explicit migration.

Copies are created:

- daily at `BACKUP_HOUR`; after an error there is one retry an hour later;
- before changing the application or schema version, before the API starts; a failed copy blocks the update;
- HA creates a separate copy of the application when it is stopped: includes consistent bundled PostgreSQL cluster and configuration. The external database is not located in the application directory - for external, additionally perform a fresh logical backup before the HA copy or use a backup of an external server.

Enable automatic HA copies including Volleycrew and configure **encrypted storage outside this host** in HA. Keep your HA backup recovery key. You do this step yourself; the mere existence of `/data/backups` is not a copy outside the host. Don't delete the only valid copy. In external mode, the HA copy itself does not replace the database server copy.

Retention is manual: the package does not delete copies automatically. Check the execution log and space. For updates, also make a manual HA copy before pressing **Update** so that you have the previous version of the options and the complete set to recover. Before the update, the lack of a correct logical copy blocks the launch of the new version.

Additional operator command inside a running container:

```sh
volleycrew-backup create
```

This command is not needed for regular installation or HA copy.

## Update and rollback

A new release updates `version` in `config.yaml`. After publishing the code, refresh the HA store, make a copy and select the update manually. Build takes place during installation/update, not at every restart. After updating, check start, login, enrollments, ranking and PDF. If startup stopped at configuration, connection, copy or migration, correct the cause; do not delete data.

It is only safe to undo an image if the previous code supports the current schema. Otherwise, stop the application and recreate the **compatible set: previous image/code, previous database and configuration**. Do not perform automatic `alembic downgrade` on production data.

## HA restore with the bundled database

Restore a full copy of the application in HA and run a compatible version. The package will recreate the database from the recovery archive without manual server configuration. The copy must contain all application state except the cluster files excluded by the manifest. Testing on real HA remains mandatory post-installation acceptance testing; containers check for an independent empty volume.

## Portable restore to new server

1. Stop the application, recover the `.tar.gz` archive from the HA copy and prepare an empty target database on the selected server, belonging to your own Volleycrew user. Do not overwrite the running database or maybe-finance.
2. Use the image corresponding to the version/schema from the `manifest.json` archive. The operator can build it from the appropriate version of the repository on the Docker machine. The `pg_dump`/`pg_restore` binaries do not need to be installed separately in this image.
3. Prepare the private file `.env.restore` with `VOLLEYCREW_RESTORE_DATABASE_URL=postgresql+asyncpg://…` pointing to **empty target only**. Do not pass the password as a program argument or in the log; set file permissions to 600. The password in the URL must be correctly encoded.
4. Example on the operator's machine with Docker, for the previously built image `volleycrew:0.2.0`:

```sh
mkdir -p restore-data
chmod 700 restore-data
chmod 600 .env.restore
docker run --rm --env-file .env.restore \
  -e VOLLEYCREW_STATE_DIR=/data \
  -v "$PWD/restore-data:/data" -v "$PWD/backup:/restore:ro" \
  --entrypoint python volleycrew:0.2.0 \
  -m app.backup restore /restore/volleycrew-BACKUP.tar.gz --confirm-empty-target
```

The command refuses to restore to a non-empty database, checks the format and checksums of the archive, and does not execute `DROP` on existing data. `pg_restore` runs in one transaction. By default, sessions are invalidated - players log in again with a password. The source database is not modified.

`options.json` from the archive goes to `restored-options.json` for operator viewing; the DB connection is not automatically rolled back to the old server. Set the correct options for the new target in HA and run a compatible image. History, declarations, attendance, lineups, corrections and ELO remain in the restored DB.

Advanced `--retain-sessions` also recreates the key; if you use `SESSION_SECRET` it must match the copy. The standard procedure is to log in again. Do not publish `restored-options.json`, `.env.restore`, key or archive to Git.

After recovery, check the number of accounts, meetings and enrollments, private history, score and ranking, and then PDF. Only after this check, return to normal use and make a new copy off the host.

## Most common problems

- **Does not start:** complete options; check the reachability of a separate DB, password, TLS and owner rights to the bundled database. Do not use `localhost` as the address of another server/application.
- **403 after login in Ingress:** check HTTPS and origin HA in `ADDITIONAL_ORIGINS`, refresh the page. Do not disable CSRF or security cookies.
- **Bootstrap token expired:** enter new random `BOOTSTRAP_TOKEN` and reboot. With an existing admin, bootstrap is closed - use their profile and normal password reset.
- **404 assets or redirection outside Ingress:** check if you are using the web button in HA; point public tunnel to 8200. Do not set a permanent Ingress token/prefix in `PUBLIC_URL`.
- **Backup/Migration Error:** do not proceed with update without a valid backup. Readiness checks the DB and schema, liveness checks the process itself. A temporary lack of DB after startup gives non-readiness without deleting data.

The tests in the repository simulate Supervisor and HTTPS; they do not mean a completed installation on your HA, a Pi 4 RAM measurement, or a non-LAN phone test. The E10 report separates these attempts from local verification.

## Calendar and signature list

The administrator has „Twoje serie spotkań” in the calendar. „Edytuj serię” opens current parameters and previews of future changes; shortening the range removes missing meeting occurrences. „Usuń serię” removes its future meeting occurrences, retaining the played history, other series and single additional meetings. In the „Usuń spotkanie” meeting tile, it also removes the revoked entry from the view and prevents that instance from being recreated.

To print the list before leaving home, open the meeting as an administrator and select „Lista podpisów” in the organizer panel. Before checking attendance, the document contains people with a confirmed place, excluding the waitlist and pending reconfirmations. Select „Pobierz aktualny PDF” and print A4 at 100% scale. The printout does not confirm attendance. After checking and confirming attendance at the venue, the same button downloads the list of those actually present.

## Preliminary teams

Before checking attendance, the meeting details show a court of people with a confirmed place, aligned by ELO by default. After signing up or resigning, the court is refreshed immediately; the rest see changes no later than the next refresh every 30 seconds.

The administrator can draw, switch people by touching players from opposite sides or go back to „Według ELO”. The entire team can see the split, and changing the declaration resets it to the current ELO. At the venue, check and confirm attendance, then select „Użyj wstępnego podziału” in step „Drużyny”. If actual attendance differs from the enrollment list, the application balances the actual attendees again.

## Watching login attempts

In the HA application logs, search for JSON events with the names `auth_failed`, `auth_invalid_link`, `auth_csrf_rejected`, `auth_invalid_input`, `auth_rate_limited`, `auth_burst_limited`, and `auth_succeeded`. The `operation` field indicates login/registration/bootstrap/reset, and `source` is the source HMAC fingerprint allowing you to compare attempts without printing the IP address in these events. The instance key must remain the same so that the fingerprints are comparable after a restart. The separate Nginx access log still contains the address as previously described.

Repeated errors from one source or limits from multiple sources require checking the traffic on the tunnel/proxy. CSRF errors after changing the address may also indicate an incorrect origin/proxy. `security_logs_suppressed` means exceeding 60 security entries/minute/process; subsequent entries are skipped until the end of the window so that traffic does not fill the logs. The number of entries is therefore not the number of all attempts. The logs do not constitute automatic alerts or external monitoring.

An additional request burst limit works before the database: per source, burst of 10 and renewal 30/min, globally burst of 20 and renewal of 4/s, for four input operations. Configure trusted proxy correctly; without this, multiple users may share the limit of one proxy address, and Ingress shares the Supervisor source. HTTP 429 includes the retry delay. Restart only resets the additional limiter in memory; the actual bad password and operation counters remain in PostgreSQL. Changing to multiple workers requires re-selection of protection common to processes. Protection against flooding of the link/connections is configured on the proxy/tunnel.

`#…` links disappear from the address after opening. After refreshing the page, reopen the original link from the message. The old token-in-path format is no longer supported; ask for the current link. Just opening the reset link still doesn't use it up. Don't share links or diagnostic files containing secrets.

## Optional Google login

Google can link an existing profile or register a new one from an active invitation. On the invitation screen, the player selects Join via Google, checks the suggested name/surname, can correct it and confirms joining. There is no need to set a login or password. Regular login and password registration remains available. First connection: login and password → My profile → Google login → reconfirm password → select Google account. After that, „Zaloguj przez Google” is enough. Disconnecting requires a password and invalidates remaining sessions. **A password reset issued by the organizer also disconnects Google** and you will need to reconnect your account once your account is recovered. Changing the password yourself preserves your connection.

Operator configuration:

1. In [Google Cloud Console](https://console.cloud.google.com/), select your project and open **Google Auth Platform**. Complete Branding (name, contact, required domains/pages) and Audience. For private Gmail accounts, the app uses an External audience. Our integration only requests `openid profile`; Google provides an exception to the test users list requirement and a seven-day authorization expiration for basic login. Check current requirements in Audience. Sharing with other players requires the appropriate publication status; follow the requirements shown by Google for your project.
2. In Clients, create an OAuth client of type **Web application**. Register the exact Authorized redirect URI: `https://YOUR-DOMAIN/api/v1/auth/google/callback`. Use a domain with PUBLIC_URL, without dynamic ingress prefix. We do not configure the Android/iOS client or service account here.
3. In the HA application options, set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` together, saved for the same client. Enter the secret only in HA options, not in the repository or chat. Restart the application. Missing both values disables the Google button; an incomplete pair is a configuration error. PUBLIC_URL must point to a working own HTTPS domain and proxy to port 8200.
4. Open PUBLIC_URL on your phone, log in with your password and connect Google in your profile. Log out, use Google and check that the same profile with the same enrollments and role has opened. Also test canceling, disconnecting and re-entering with a password.

The requested scope is `openid profile`, with no access to Gmail, Drive or Calendar. The backend verifies the token and binds the profile by Google ID. The name/surname is a hint for the editable join form; do not update existing profile details when logging in. We do not save email, photo or access tokens. The button works as a full browser redirect. From the HA/Ingress panel, opens the main domain in a new tab; does not automatically log in to the Ingress session and does not grant permissions from the HA account.

Own HTTPS address and outgoing HTTPS to `oauth2.googleapis.com` and `www.googleapis.com` must work. The host time must be correct. After changing your domain, update your PUBLIC_URL, Google client redirect URI and proxy configuration. Error `redirect_uri_mismatch` means address difference in Google; invalid client/secret requires checking the data pair. The „niepołączone” account requires a password and connection on your own profile - the application does not match accounts by name or email.

The callback receives a short-lived code in the query. The package's Nginx omits address/query in the access log, the backend and local runner have access log disabled, and HTTPX logs are limited to WARNING. Keep this protection on your external proxy too; do not log body or query callback. `auth_google_succeeded` and `auth_google_failed` appear in the monitoring, without codes, nonces, Google sub and secrets. Client credentials is transferred in private environment files and covered by the existing configuration copy protection.

Migration `0011_google_login` adds two tables and retains existing profiles. Before updating, make a regular copy. Disabling Google (clearing **both** values) preserves binding and password login; disconnecting the association is a separate action. `VOLLEYCREW_GOOGLE_CLIENT_ID` and `VOLLEYCREW_GOOGLE_CLIENT_SECRET` are used locally, with a separate client/redirect URI for localhost. Automation tests only use an isolated test provider; they don't confirm your Google project setup.

## Switching from PIN to login and password

The change includes the migration of `0012_password_login`. Old PINs do not work as passwords. Sessions and old reset links are invalidated; profiles, enrollments, history and ELO remain in the database. By the user's decision, there is no player migration - only the organizer is currently registered.

After updating, perform a one-time organizer access setup:

1. Before updating, make a copy of the application/database.
2. In HA, type **new**, random `BOOTSTRAP_TOKEN` (minimum 32 characters) and restart Volleycrew. The old token used is not reactivated by restart.
3. Open `PUBLIC_URL/setup#NEW_TOKEN`, choose your own login and password (8-128 characters). The existing admin profile will retain ID, data and history; first/last name fields are for new installation. There is no second administrator created.
4. Check login with login and password; clear BOOTSTRAP_TOKEN in options. Bootstrap closes again after setting the password. If Google was linked to this account, reconnect it in your profile by confirming your new password.

Outside of HA, an alternative is `npm run auth:bootstrap -- --rotate` in a valid application environment. The link is valid for 30 minutes and can be used once. There is no default password, automatic use of the old PIN or deletion of the production database. Login is a separate name of 3-32 characters: ASCII letters, numbers, dot, dash and underscore; usernames are case-insensitive. Passwords preserve spaces and Unicode exactly.

The player registers by invitation via Google or by providing his own login and password. The organizer issues a 30-minute reset link with which you can set your password and recover/replace your login. Changing/resetting your password logs out other devices. A reset from the organizer also disconnects Google. The login does not appear on the participant lists or printouts. The public profile directory and old PIN endpoints have been removed.

Undoing the migration does not recreate PINs or logins. For access rollback, restore a compatible copy of the database and the earlier image. Login changes are available in package 0.3.5.

## Joining via Google

1. The organizer creates a regular invitation link and sends it to the player.
2. The player opens the link and selects **Dołącz przez Google** (Join with Google), without filling out the password form.
3. After selecting your Google account, it returns to **Sprawdź dane i dołącz** (Check your details and join). Name and surname are suggested if Google has provided them; they can be corrected or supplemented at will. The nickname is optional.
4. **Dołączam do gry** (Join the game) creates a guest profile and logs in to the group. Closing the form earlier does not create an account.

A Google-only account does not have a local login/password. In the profile, **Ustaw login i hasło** (Set a username and password) requires a new confirmation of the same Google account. Then both methods are available. Unlinking Google requires a password you have set so as not to cut off your last access method. The organizer may also issue a simple reset link to regain access after losing Google; this reset disconnects the previous Google.

Rejoining with the same Google account opens the existing profile, without changing its name/role and without duplicating it. The app doesn't match accounts by email or name; someone with a previous local account should log in to it and link Google in their profile. The invitation must be active at startup, after returning from Google and after approval. A withdrawn link does not create a new account.

The confirmation form expires 10 minutes after Google starts and is bound to this browser. Refreshing requires reopening the invitation; the secret is not persisted in address/storage. Ingress opens the invitation under the main PUBLIC_URL in a separate tab, without moving the session. At the attempts limit, wait the time shown by the application and click again; in case of a form reading error, there is a retry button.

`0013_google_registration` migration adds one-time confirmations and Google invitation context/flow type. It does not change enrollments, history or ELO. Removes old Google profile associations without data set after switching from PIN; it doesn't retroactively grant them Google-only access. When rolling back the code, restore a compatible backup - earlier versions do not support passwordless accounts. Google client credentials and callback remain the same; in Google Auth Platform, check the base scope declaration `profile`. Real accounts and physical HA/phone/PWA require separate acceptance testing after setup.

### Invitations and Messenger

The new invitations are `/join?token=…`; create and copy new link after update. Older `/join#…` links still work in browsers. The token disappears from the address after reading; Refreshing requires reopening the full link. The application's Nginx does not log addresses and the site disables Referer. With your own proxy/tunnel, do not save query invitations in logs or analytics. Password reset and initialization still use the `#…` fragment.
