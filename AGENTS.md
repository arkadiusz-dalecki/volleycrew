# Volleycrew — instructions for Codex

## Project and sources of decisions

Volleycrew organizes volleyball for one private group: profiles and PIN login, a calendar and recurring meeting series, participation declarations, a waitlist and seat offers, actual attendance, teams, a PDF signature list, results, and ELO rankings. The administrator manages the group and meetings; players declare participation and view the data available to them. Participation declarations, checked attendance, and confirmed teams are separate states.

Before implementation, data model changes, or task planning:

1. Read the [implementation plan](docs/implementation/README.md), select a stage or follow-up from the [backlog](docs/implementation/tasks.md), and load its referenced specifications.
2. Check the [decision register](docs/implementation/decisions.md). Implement a dependent rule after recording the user's decision. User instructions take precedence over earlier decisions.
3. For backend and API work, read the [domain rules](docs/implementation/domain-api.md); for UI work, the [interface specification](docs/implementation/frontend.md); for infrastructure changes, the [architecture](docs/implementation/architecture.md).

The selected UI design is **variant A** in `prototype/`. The prototype is a visual and interaction reference; its fictional data and simplified rules are not a backend specification. Progress and current scope are recorded in the plan index. Stage reports identify satisfied acceptance criteria, tests actually run, and remaining dependencies.

## Code and environments

- `volleycrew/frontend/`: React, TypeScript, Vite; a Polish interface designed for phones. Backend OpenAPI is the source of generated client types.
- `volleycrew/backend/`: FastAPI, SQLAlchemy, Alembic, and PostgreSQL. Endpoints use domain services; schema changes require migrations.
- `volleycrew/rootfs/`, `volleycrew/Dockerfile`, `volleycrew/config.yaml`: the Home Assistant package with Nginx, the API, and its own PostgreSQL; an external database is also supported. Installation and updates: [DOCS.md](volleycrew/DOCS.md).
- `scripts/`: development startup and tests of actual images, Ingress, and backup/restore. Check commands and required versions in the [README](README.md), `package.json`, and configuration files.

The target deployment is a Home Assistant app on amd64 and aarch64. Code review, a push, and green CI do not constitute deployment or acceptance on a physical phone or Home Assistant.

Development and tests use separate databases. Backend and E2E tests reset data: point them only at an isolated test database, never a development or production database. When both suites use the same database, run them sequentially. Seed demo data only in an explicitly verified development environment. Keep secrets, PINs, tokens, `.env` files, and production data out of the repository and logs.

Preserve transactional seat allocation rules, status and history privacy, version checks, and idempotency. When changing a DTO, update the backend, contract, and frontend together with `npm run api:generate`; verify with `npm run api:check`.

## Git, GitHub, and PRs

Use `git` and the GitHub CLI `gh` in the repository identified by `git remote -v`. At the start, check the branch, working tree, existing PR, and diff against the current base branch. Preserve the user's existing changes.

When the user requests a PR:

1. Prepare the complete change on a working branch, run the appropriate [local checks](docs/implementation/verification.md), and run `git diff --check`. Match tests to the effects of the change; mocks alone do not replace PostgreSQL or a Home Assistant image test.
2. If a small version bump is requested, increment the patch version in `volleycrew/config.yaml` and update `volleycrew/CHANGELOG.md`. Read the current version from the file. Describe migrations and update requirements.
3. Commit, push the branch, and create or update the PR against the correct base. Write the PR title and description in English. Describe the final problem, resulting behavior, test evidence, and material risks. Pass multiline descriptions through a file with `--body-file`.
4. **After creating the PR and after every subsequent push, wait for GitHub Actions checks to finish for the current commit.** Check every PR check, including the application and both Home Assistant package variants; a green backend or local build is insufficient.
5. When a check fails, read its logs, identify the cause, fix the code or test, and run an appropriate regression check. Commit and push to the same branch and PR, then wait for CI again. **Repeat until all checks pass.** Rerunning without changes only makes sense for an identified transient infrastructure failure; do not disable checks or weaken assertions to hide a failure.
6. Before finishing, compare the PR HEAD with the pushed commit and confirm that the results apply to that exact commit. `queued`, `pending`, `in_progress`, and canceled runs do not count as passing; intentional skips require justification. For a genuine external blocker, report the specific blocking condition and link to the run without claiming readiness.
7. Give the user the PR link, version (if changed), CI result, and remaining limitations. Creating a PR does not authorize merging or deployment; perform those only when requested by the user.

Useful commands (replace the PR number and run ID with values read from GitHub):

```sh
gh pr view <PR> --json url,headRefName,headRefOid,statusCheckRollup
gh pr checks <PR> --watch --interval 30
gh run view <RUN_ID> --log-failed
gh pr create --base main --head <BRANCH> --title '<TITLE>' --body-file /tmp/pr-body.md
gh pr edit <PR> --body-file /tmp/pr-body.md
```

The source of the current CI matrix is [.github/workflows/checks.yml](.github/workflows/checks.yml). ARM64 images and restore tests may take more than ten minutes: keep monitoring and provide brief updates when the status changes materially. After a fix, check the latest runs rather than earlier green results or failures from an older commit.

## Time-dependent tests

The calendar timezone is Europe/Warsaw. Test meeting start boundaries, date changes, and DST with a controlled clock. `/meetings/next` may correctly return an ongoing meeting; signup fixtures must select a future occurrence. Package tests use `signup_occurrence` in `scripts/test_container.py` for this purpose. A test regression does not justify changing a correct production rule.
