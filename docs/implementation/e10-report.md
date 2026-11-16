# E10 - Home Assistant package for self-installation

Date: 2026-11-07. Scope as per last command: package and statement in repository and local verification. The user himself publishes/adds the repository, generates a token and installs the application. No installations, updates, or changes were made to the target HA, tunnel, or production PostgreSQL. The code remains local, without commit/push and release.

## Items provided

- `repository.yaml`, `volleycrew/config.yaml`, `build.yaml`, Dockerfile and `.dockerignore`. Package version **0.1.0**, `aarch64`/`amd64`, local build via Supervisor, without `image` with pre-built Volleycrew image. `host_network`, HA configuration mapping and HA API/Supervisor/Docker permissions are missing. `/data` is durable.
- Multi-stage build: Node 24 for build only, static frontend, Python/FastAPI and Nginx with s6 in runtime. Runtime Debian base **9.3.0**, images of both architectures and default multiarch index pinned to verified digests; Node 24 also after digest. The backend installs hashed `requirements.lock`, exported from `uv.lock` without development dependencies. CI checks export compliance.
- Validated options `/data/options.json` → private s6 environment files (600), without `eval` and writing out the DB connection. Passwords with special characters are encoded by SQLAlchemy URL. The public HTTPS URL is origin without a path. Trusted proxy addresses are validated, `0.0.0.0/0`/`::/0` rejected.
- Start: Nginx configuration and check → limited waiting for DB → backup before changing version/schema → migrations → bootstrap → API and Nginx. Incorrect configuration does not trigger migration. An initialization or process failure stops the container; there is no deleting the database as a repair. Blocked migration leaves the API stuck.
- `BOOTSTRAP_TOKEN` in options allows first administrator profile without SSH. Random URL-safe token, at least 32 characters; grant valid for 30 minutes. Restart does not extend the validity, a new token can replace the old one only before creating an administrator. Existing admin permanently closes bootstrap. The PIN is set by the user himself to `/setup#token`; the token does not go to the logs.
- [Installation, options, update, backup and restore instructions](../../volleycrew/DOCS.md), application README and changelog. The Root README describes the build and reproducible tests of the package.

## HTTP inputs and privacy

| Element                           | Implementation                                                                                                                                                                 |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Entrance to your own tunnel/proxy | Nginx `8200`, configurable HA host mapping                                                                                                                                     |
| Ingress                           | Nginx `8099`, **no host mapping**, ACL only `172.30.32.2`                                                                                                                      |
| Backend                           | `127.0.0.1:8000` inside container                                                                                                                                              |
| Prefix                            | Validated `X-Ingress-Path` only on Supervisor input; HTML injected `<base>`, router basename, API client, manifest and assets run under variable prefix                        |
| Identity                          | Custom profiles/PIN and Volleycrew roles; HA identity headers do not grant permissions                                                                                         |
| Cookies                           | Separate direct/ingress names and paths; `Secure`, session `HttpOnly`, `SameSite=Lax`. HTTPS also required for HA                                                              |
| CSRF                              | Token and explicit origins; origin HA in `ADDITIONAL_ORIGINS`; no wide CORS                                                                                                    |
| Proxy                             | Public Ingress headers are ignored; XFF/proto trust only from configured peers. Backend context accepted only from local Nginx                                                 |
| Logs                              | Access log Nginx without URI/query/body/cookies, Uvicorn without access log, production exceptions without tracebacks/driver parameters; init/backup log steps and error types |
| Health                            | process liveness and readiness with the DB and the current revision; loss of DB after startup gives 503 readiness, after return it regains readiness                           |

The package adds CSP, no-referrer and nosniff. `.mjs` modules have an explicit JavaScript type - production PDF testing found this mapping missing from Nginx default types. PDF.js and worker also run locally in Ingress. PDF fonts can be loaded from local blob/data, without CDN.

Base image scripts for banner/log level/timezone do not require Supervisor calls: replaced s6 helper actions with neutral scripts. We read the application configuration ourselves from `/data/options.json`. This allows the actual package to also run outside of HA; domain scheduler and copies use `Europe/Warsaw` explicitly. Removed unnecessary `with-contenv` nesting in DB initialization. We note amd64 emulation separately from native execution.

## Backup and restore

`app.backup` and the operator command `volleycrew-backup` create a private archive: custom `pg_dump`, version/schema and SHA-256 metadata, effective key and options. Saving via temporary file and atomic renaming; staging/partial disabled from HA copy. No automatic deletion of old copies. The archive is not self-encrypted.

- Locally every day at the indicated time in Warsaw; error gives one retry after an hour and an open log.
- Before updating version or schema: copy required, then migration; the lack of a copy blocks the launch of the new version.
- `backup_pre` HA creates a current dump of the external DB before copying the application files. The user must enable HA copies and **off-host encrypted target** and retain the recovery key. The agent has not configured such a place.
- Restore requires explicit `VOLLEYCREW_RESTORE_DATABASE_URL` and `--confirm-empty-target`; refuses to overwrite non-empty database, checks archive and totals, rejects paths/symlinks/duplicates. `pg_restore` runs in one transaction. It saves the source options separately as `restored-options.json`, without redirecting the connection back to the old server.
- By default, sessions are invalidated; optional behavior requires a matching key. Accounts and PINs, history, places, attendance, lineups, results and points remain. Rolling back the code requires either schema compatibility or re-creation of the entire compliant set, without automatic downgrade.

The test recreated a copy **on a second PostgreSQL container/instance**, comparing counts and full row fingerprints of 13 domain tables: profiles, schedule, meetings, enrollments and events, attendance and history, lineups, results, points, and audit. The source database and session still work; target sessions are invalidated. This is a local restore, not a test of downloading from a target off-host storage or recovering the entire HA host.

## Fix first migration

The new, completely empty PostgreSQL 17 showed a backfill error in `0006_room`: `ORDER BY sequence` referenced a column that did not exist in `enrollment_events`. Corrected order to `enrollment_events.created_at, enrollment_events.id`. Added a test that removes only the explicit one-time database schema `_test` and traverses the entire chain from scratch. No new revision added; database files already on `0007_results` do not change their data due to this patch. There was no prior HA release of this migration.

## Local verification

Mac arm64, dedicated Colima `volleycrew` profile (Linux ARM64, 2 CPU/4 GiB), separate test networks, containers and volumes. Production images built for `linux/arm64` and `linux/amd64`; amd64 runs under QEMU emulation, not on a physical x86 or Pi machine. Python runtime **3.13.5**, Nginx **1.26.3**, PostgreSQL client **17.11**. Development code/tests: Python 3.13.18. No production database or maybe-finance was used.

Browsers: Chromium **158.0.8127.18** and WebKit **27.2**; iPhone emulation is not a physical Safari iOS test. The HTTPS fixture certificate is local, self-signed and only omitted in tests. Production still requires valid HTTPS and secure cookies.

| Checking                                                                                                                           | Result                                                                                                                |
| ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `npm run lint`, `npm run typecheck`, `npm run api:check`, `npm run test:frontend`, `npm run build`                                 | Correctly; Vitest 1 test                                                                                              |
| Full backend regression on separate PostgreSQL 17 by `test_container.py --backend-tests`                                           | **115 passes**, 52.69 sec; previous warning Starlette/TestClient                                                      |
| Additionally, `tests/test_deployment.py` after the last refinement of the token alphabet                                           | **7 passed**                                                                                                          |
| Plain E2E Chromium desktop/mobile and WebKit                                                                                       | **32 passed, 1 intentionally skipped** (mobile keyboard geometry on desktop), 2.5 min                                 |
| Build `linux/arm64` and `linux/amd64`                                                                                              | Both completed successfully, local images `volleycrew:e10-arm64` and `volleycrew:e10-amd64`                           |
| Production ARM64 image: startup, errors, prefixes/HTTPS, restart, pre-release copy, full match, DB loss/recovery, restore and logs | **All passed**                                                                                                        |
| Production amd64 image under QEMU: same set                                                                                        | **All passed**, this is not an attempt on physical x86                                                                |
| Playwright on real images: direct + two prefixes, profile/reload/navigation and actually rendered PDF                              | **6/6 ARM64 + 6/6 amd64**, Chromium/WebKit; last runs 8.2 s and 13.8 s                                                |
| Restore on second PostgreSQL                                                                                                       | **Passed on both CPUs**, matching 13 table fingerprints after 5-3 match, separate session invalidation, source intact |
| Alembic `check` on development DB and compatibility of production lockfile export                                                  | `No new upgrade operations detected`; export without differences                                                      |

The emulator built into the initial Colima profile occasionally terminated simple s6 base scripts with signal 11, even after a successful start. Upgrading the **local test environment only** to the official `tonistiigi/binfmt`/QEMU **10.2.3** allowed me to run the full amd64 stack without such crashes. Previous aborted attempts were not considered a success and the application domain was not changed to bypass them. CI pins the verified emulator image after digest. This is still not proof of operation on a physical x86/Pi.

Logs: `.runtime/e10-container-{arm,amd}.log`, `.runtime/e10/{browser-arm,browser-amd,backend-pg17}.log`. The test archive is private and ignored by Git. Containers, networks, and assigned volumes from completed runs have been removed; the environment is not a production deployment.

To be reproduced: `scripts/test_container.py --image <local-image> --platform linux/arm64|linux/amd64`. The test only creates and deletes its own resources. `--backend-tests` additionally runs the entire regression on a separate `regression_test` in PostgreSQL 17, without affecting the source database of the application under test. The results and screenshots are in the ignored `.runtime/e10*` and `volleycrew/frontend/test-results-container/`.

In the original E10 workflow it built/tested both CPUs without publishing the image; remote CI was not started then. A later HA installation attempt showed that build.yaml with digests is discarded and Supervisor overrides the base image with Alpine via BUILD_FROM. Patch 0.1.1 is covered by [HA Compatibility Report](ha-build-fix.md); it replaces the previous build.yaml compatibility assumption.

## User acceptance testing after code publication

- [ ] Code sent to the repository that the user adds; remote CI checked.
- [ ] Installation and re-update/reboot on Pi 4 aarch64, with build time/RAM measurement.
- [ ] Separate production PostgreSQL, correct options, token and own administrator PIN.
- [ ] HTTPS and Ingress domain with its own Volleycrew session, proper origins/proxy.
- [ ] Player entry from a phone outside the LAN, without an HA account; full series of meetings and PDF.
- [ ] Daily off-host backup and restore from there, with HA recovery key.
- [ ] Physical Chrome Android/Safari iOS and accept A vs E9 comparison.

These are consciously delegated activities, production acceptance testing was not performed. The next stage **E11** includes final acceptance testing and release after these tests. We do not announce installation on HA or completion of the entire project based on local build alone.

## Sources checked in E10

- Local `../maybe-finance`: repository manifest, config/build.yaml, Dockerfile, init, Nginx and services. Local build method preserved; no host network, Node process or financial integrations have been moved.
- [HA - Application Configuration](https://contributors.home-assistant.io/apps/reference/configuration/): none `image` means local build, `/data` is persistent, separate Ingress port and copy hook.
- [HA - Ingress](https://contributors.home-assistant.io/apps/guides/ingress/): trusted peer `172.30.32.2`, variable prefix and `X-Ingress-Path`. Custom PIN remains an intentional requirement of Volleycrew, with no role assignments based on HA.
- [HA - Dockerfile/build](https://contributors.home-assistant.io/apps/guides/dockerfile/): default `BUILD_FROM`, compatible with legacy build.yaml and s6.
- [Debian base 9.3.0](https://raw.githubusercontent.com/hassio-addons/app-debian-base/v9.3.0/base/Dockerfile): Debian Trixie/s6. The existence of both manifestos and digesta was checked with GHCR; their accessibility was not requested from the old maybe-finance.

- [Docker - multiarch and emulation](https://docs.docker.com/build/building/multi-platform/): Separate build from run and use official binfmt in local VM.
