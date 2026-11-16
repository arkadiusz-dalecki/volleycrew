# Volleycrew

An app for a private volleyball group: calendar and enrollments, waitlist, attendance, teams on the court, PDF signature sheets and ELO rankings.

Home Assistant builds the app locally during installation, like maybe-finance. Supported architectures: 64-bit Raspberry Pi (`aarch64`) and `amd64`. Since 0.2.0, it includes PostgreSQL 17 with automatic configuration and persistent data. An HTTPS domain is required. Existing external database configurations remain supported. Players sign in to Volleycrew with a username and password or optional Google login; they do not need HA accounts.

[Installation and configuration](DOCS.md) · [Changelog](CHANGELOG.md)
