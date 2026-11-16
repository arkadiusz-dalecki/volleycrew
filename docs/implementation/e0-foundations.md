> Update 2026-11-08: user requested bundled PostgreSQL in a package. Since 0.2.0, new installations do not require a separate server. Previous findings below are historical; architecture.md and bundled-postgresql.md describe the current behavior.

# E0 - establishing foundations

Date: 2026-11-06. Status: technical part prepared for E1; D2 approved, D3 approved with status privacy; D4 approved (any change requires confirmation, preserves order and reservations, includes offers); D5 approved (corrections, excuses, late arrival, addition without declaration); D6 approved (lock, release future places, preserve history, nickname and masked login list). No installation, connection to HA or production database was performed. The results below are design findings and documentation verification, not container tests.

## User settings

| Area                         | Confirmed                                                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Host                         | Raspberry Pi 4, Home Assistant 64-bit, `aarch64`                                                           |
| Access from outside the home | Cloudflare Tunnel; the user will configure as in maybe-finance. Tunnel configuration outside current scope |
| Database                     | A separate PostgreSQL server, not the server used by maybe-finance                                         |
| First edition                | The complete cycle is described in the plan index, along with PDF list, results and ELO                    |
| Backup                       | Currently none. Ultimately daily and before update, with a copy off the host                               |
| Deployments                  | Manually activated                                                                                         |

The location of a separate PostgreSQL server, its version, address, capacity and backup destination have not yet been determined. Do not ask for passwords in conversation. A Cloudflare domain and specific configuration are not required to start E1.

## Technical choices for the start of E1

- Frontend: UI A accepted, React 19, TypeScript, Vite, React Router, TanStack Query. Pin the exact set of stable versions in the E1 lockfile, without canary.
- Node.js 24 LTS for build and CI; Node missing in application runtime. We do not migrate version 20 from the reference Dockerfile.
- Python 3.13 with current security patch, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, asyncpg. Python 3.13 corresponds to the Debian 13 runtime candidate; The kit's compatibility will be confirmed by E1 installation and testing.
- PostgreSQL 17 as target branch for new server and local tests. Don't assume the server already exists. Exact patch from the current supported branch at the time of installation. Another existing version requires an explicit compatibility check.
- Runtime image: candidate `hassio-addons` Debian base 9.3.0 / Debian 13 with s6. Release visible in the official repository; the image path, digest and manifests of both CPUs must be checked in E1 before pinning. We do not declare a verified multiarch image yet.
- Priority production of `aarch64`; `amd64` remains the second build/test target. Limit RAM: static frontend, one API process, no Redis/Celery. Building frontend assets is not part of the container startup.
- Application slug: `volleycrew`; application folder: `volleycrew/`; database and username: `volleycrew`. Separate password and permissions only for the bundled database, no superuser.
- Proposed ports: Nginx direct `8200/tcp` with host mapping configurable in HA; Ingress `8099` internal only, no mapping; Uvicorn `127.0.0.1:8000`. Port 8199 belongs to the reference maybe-finance. Availability of the host 8200 has not yet been verified; mapping change allowed before installation.

These selections are an implementation foundation, not a claim about the latest versions of all libraries. Exact versions and proof of compliance go to the lockfile and the E1 report.

## Access and configuration

Target path: phone → HTTPS domain in Cloudflare → user-configured Tunnel → Nginx Volleycrew listener → static frontend or `/api/v1` → FastAPI → separate PostgreSQL.

Cloudflare does not replace app login. Users do not need Home Assistant accounts. Proxy headers can only affect HTTPS resolution when connected from a specified trusted peer. The tunnel address/CIDR must be provided during deployment; do not blindly enter all private networks. Removing/masking invite and reset tokens in logs and the Referrer policy are intended to limit URL leaks.

Ingress is an additional path. HA documentation recommends trusted HA identities and no second logins; our plan is to have separate Volleycrew profiles. Therefore, do not enable automatic mapping of the HA account to Arkadiusz. Before completing E10, check cookies and additional login under the Ingress prefix; when proper operation cannot be obtained, present the user with the option of opening a standalone application from the HA panel. The working public access through the Tunnel is the main path for the player.

Settings to be implemented in E1/E10: `DATABASE_URL` locally; HA options `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; `PUBLIC_URL`, `TRUSTED_PROXY_CIDRS`, `SESSION_SECRET`. Secrets outside the repository. Frontend and API have a common origin. Settings that are not yet known have explicit validation requirements instead of guessed production values.

## Sessions and PIN protection - approved in E2

The six-digit PIN and self-registration from the invitation remain product requirements. The technical base is Argon2id, a random session with a token hash in the database and an HttpOnly/Secure cookie. Select Argon2 parameters by measuring them on Raspberry Pi; limit the number of simultaneous costly attempts.

User Approved 2026-11-06: 30 days session idle, hard expire after 180 days; PIN reset valid for 30 minutes, one-time use. After 5 failed attempts per profile in 15 minutes, subsequent attempts are temporarily rejected until the end of the window. No permanent account blocking. Technical source protection: 30 failed PINs/15 minutes. The counters in the DB work after a restart; implementation and evidence in the E2 report.

## Backup and restore

Frequency policy approved; implementation does not exist yet. Before E10, determine the purpose of the off-host copy, retention, schedule, owner and signaling of a failed backup. Proposed retention to be agreed: 14 daily copies. Daily backup means you may lose changes since the last successful copy; recovery time to be agreed, currently not SLA.

Before updating, make a consistent `pg_dump` with a tool compatible with the server and a copy of the necessary configuration/secrets, then transfer the copy outside the host. Encrypt the data where it is stored and limit access. A copy of the file directory of a running PostgreSQL does not replace a logical backup.

Recreating: new empty database → restoring the dump and the necessary configuration → running a compatible image → controlling users, meeting occurrences, history and ELO → possible session invalidation. Perform the test in a separate environment. Backing up the HA application itself does not automatically include a separate DB server.

## Open dependencies and readiness

- E1: you can prepare a skeleton with a local test PostgreSQL after ordering this step. In E1, perform a dependency resolver and a trial runtime build on both CPUs; the absence of such an attempt is not proof of compliance.
- E2: lockdown and its impact on future confirmed seats; nickname distinguishing identical surnames approved, independent edition of nickname in the profile approved; approved login directory: list of names and masked surnames, profile selection, six-digit PIN. Session and limit parameters approved in E2.
- E4: D2 and D3 approved. Waitlist includes manual proposals without timeout, withdrawal after rejection/bypass, new resubmission time and separate reservations for multiple vacancies; rules in domain-api.md.
- E5: D4 approved - each change requires confirmation of the new date, also for proposals from the waitlist; original order and reservations preserved. Places are waiting without timeout, they are released manually by the administrator.
- E6: D5 approved - corrections/excuses with reason and audit, late as present without separate penalty, adding an existing unblocked profile with a free unreserved place and a limit of 14.
- E7: D7 approved - PDF from actually present after inspection, ability to regenerate after corrections.
- E8: K=32 approved with examples 5:0 (+16/−16), 3:2 (+3.2/−3.2) and 3:3 (0/0) for equal teams. Also approved: exact values and presentation to one decimal place, 0:0 without ELO with attendance, corrections of results with reason and recalculation of later matches. Expectation parameters, historical lineup corrections and same-date match schedule remain in D8.
- E10: DB location/version, backup target, trusted proxy and free port remain implementation details. D10 committed: as in maybe-finance, local build by Supervisor from application repository and manual update when manifest version changes. Your own ready-made image in GHCR is not required. The build happens during installation/update, not at every startup. On Pi 4, check RAM and build time.

## Sources checked 2026-11-06

- [HA: configuration](https://contributors.home-assistant.io/apps/reference/configuration/) and [Ingress](https://contributors.home-assistant.io/apps/guides/ingress/): separate direct input, Ingress listener protection, path prefix.
- [Debian base - official releases](https://github.com/hassio-addons/app-debian-base/releases): candidate 9.3.0, Debian 13; release is not proof of downloading the image manifest.
- [Node - Versions](https://nodejs.org/en/about/previous-releases): 24 LTS, 20 EOL branch.
- [Vite - Requirements](https://vite.dev/guide/): Node at least 20.19 / 22.12; supported branch 24 has been selected, exact compatibility will be checked by E1.
- [React Releases](https://react.dev/versions): branch 19.
- [Python Support](https://devguide.python.org/versions/): Python 3.13 through 2029-10 security patches.
- [FastAPI - version pinning](https://fastapi.tiangolo.com/deployment/versions/) and [PostgreSQL - version policy](https://www.postgresql.org/support/versioning/): pinning of tested releases and backup/update compatibility.

Requirements update 2026-11-06: statuses founder > player > guest, guest by default. Private statuses, independent of administrator rights. Nickname to distinguish profiles approved; school PDF without nickname.

## Candidate verification in E10 - 2026-11-07

[Report E10](e10-report.md) confirms availability and digests of Debian base 9.3.0 for both CPUs, local ARM64/amd64 build and tests with PostgreSQL 17. The base image is used by Dockerfile; since 0.1.1 it is pinned directly, without build.yaml. A standalone user installation, proper production server, target proxy, and copy storage are still not proof of deployment on the Pi.
