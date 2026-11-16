# Bundled PostgreSQL - Volleycrew 0.2.0

User Decision 2026-11-08 replaces the previous requirement for a separate server. The user does not have PostgreSQL and wants to install the complete application in HA. The agent changes the package and tests the containers; does not modify the running HA or tunnel.

## Implementation

PostgreSQL 17 is part of the Debian/s6 image. Cluster data in /data/postgresql, password generated once in /data/postgres-password (0600), separate application role without superuser, listener only 127.0.0.1:5432. No database port mapping. Memory parameters: shared_buffers 32 MB, max_connections 30, work_mem 2 MB; measurement on the physical Pi remains part of acceptance testing.

DATABASE_MODE=auto and empty host select bundled database; existing host retains external. Changing the fixed mode or missing an existing password blocks the start, it does not create an empty alternative. The PostgreSQL major version is not automatically upgraded. Steps s6: configuration → initialization/start database → backup/migrations/bootstrap → handing PostgreSQL over to the supervised service. A database failure terminates the container.

HA uses cold backup: it stops the application and saves a consistent cluster, even when the application has already been stopped. This adds a short pause for copy time. The daily pg_dump and mandatory pre-update backup remain online. External requires a fresh logical copy before the HA copy or an independent server copy - the application directory itself does not contain the external database.

An additional atomically saved postgres-recovery.tar.gz archive allows for logical recovery on an empty cluster before migrations if the cluster files are not in the migrated set. If the archive is missing or damaged, the start is blocked. A standard HA copy contains the entire cluster and does not require this mechanism. Attempting to migrate an existing database to another mode is a separate operation apart from automatic updating.

## Verification

Locally, using the production ARM64 image, self-start, migrations and real creation of the administrator, restart and SIGKILL, logical restoration on a separate volume and blocking of the missing archive were checked. The final extended attempt also includes a copy of the stopped cluster and an upgrade backup; its result for both architectures is recorded in the PR checks.

External database regression on PostgreSQL 17: 118 backend tests passed; then a secure validation diagnostic test was added. 11 configuration tests passed, lint passed. Full external image scenario: start, incorrect options/DB/migration, HTTPS, two Ingress prefixes, cookies/CSRF, restart, backup before update, enrollments/attendance/teams/PDF/result/ELO, DB loss and restore on a separate instance - passed locally. Includes 6 Chromium/WebKit UI checks.

CI builds both CPUs with a fallback BUILD_FROM, performs the existing external regression and the new scripts/test_bundled_database.py. The remote result requires confirmation in PR. Test copies and passwords do not go to CI artifacts; only logs and UI test materials.

## User acceptance testing

After merging and refreshing the store, install 0.2.0. Keep PUBLIC_URL/token; leave DATABASE_MODE=auto and empty POSTGRES_HOST. There is no need to create a database or password. Check the administrator, HA restart, copy and restore on the target Pi, and copy storage outside the host. Installation and measurement of Pi resources are not declared as performed by the agent.

Sources: [PostgreSQL initdb](https://www.postgresql.org/docs/17/app-initdb.html), [consistent file backup requirements](https://www.postgresql.org/docs/17/backup-file.html), [cold backup in HA](https://contributors.home-assistant.io/apps/reference/configuration/).
