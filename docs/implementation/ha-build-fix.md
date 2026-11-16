# E10 - HA 0.1.1 installation fix

2026-11-08. Scope: Fixed build error reported during user self-install. No changes to HA, tunnel or production database made by the agent.

## Cause and fix

Supervisor rejected digest reference in build_from due to build.yaml validation. He then passed BUILD_FROM=ghcr.io/home-assistant/base:latest, replacing the default Debian with the Alpine image. There is no apt-get in this image. The previous CI explicitly provided the correct per-arch BUILD_FROM and did not detect this path.

Removed obsolete build.yaml. Runtime FROM points directly to the pinned multiarch index digest Debian base 9.3.0; Docker selects ARM64/amd64. BUILD_FROM is not a Dockerfile argument and cannot change the underlying system. Package version and default BUILD_VERSION: 0.1.1. The data and database schema remain unchanged.

## Verification

- npm run lint: passed.
- npm run test:backend -- tests/test_deployment.py -q: 8 passes, including database selection regression resistant to the Supervisor argument.
- CI matrix builds both CPUs with the same fallback BUILD_FROM=ghcr.io/home-assistant/base:latest as in the installation log. There is no longer a bypass via a valid per-arch argument. After the build, it runs existing HTTPS/Ingress, PDF, backup and restore attempts.
- Remote results of the new matrix require confirmation in PR; the physical HA/Pi test remains on the user's side after merging and refreshing the store.

Source: [HA - Build Image](https://contributors.home-assistant.io/apps/guides/dockerfile/), Build arguments and build.yaml sections; user log. Secrets from the log were not saved in the repository.
