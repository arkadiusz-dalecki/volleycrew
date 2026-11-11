#!/usr/bin/env python3
"""Disposable production-image smoke/restore tests. No Home Assistant or user DB access."""

import argparse
import contextlib
import http.cookiejar
import json
import os
import re
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://127.0.0.1:18443"
PREFIX = "/api/hassio_ingress/volleycrew-test-token"
TOKEN = "isolated-e10-bootstrap-token-1234567890"


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(f"Docker {args[0]} failed: {result.stderr[:500]}")
    return (result.stdout + (result.stderr if args[0] == "logs" or not check else "")).strip()


def migration_head(container):
    return docker(
        "exec",
        container,
        "python",
        "-c",
        "from app.core.database import expected_revision; print(expected_revision())",
    )


def wait(url, *, status=200, seconds=100, container=None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if container and docker("inspect", "-f", "{{.State.Status}}", container) == "exited":
            raise RuntimeError("Application exited: " + docker("logs", container))
        try:
            with urllib.request.urlopen(
                url, timeout=5, context=ssl._create_unverified_context()
            ) as r:
                if r.status == status:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeError(f"Readiness did not reach {status}")


class Client:
    def __init__(self):
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
        )

    def call(self, path, method="GET", data=None, prefix="", headers=None):
        request_headers = {"Origin": ORIGIN, **(headers or {})}
        if data is not None:
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            ORIGIN + prefix + path,
            method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers=request_headers,
        )
        try:
            response = self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        body = response.read()
        result = (
            json.loads(body)
            if "application/json" in response.headers.get("Content-Type", "")
            else body
        )
        return response.status, result, response.headers

    def csrf(self, prefix=""):
        status, body, _ = self.call("/api/v1/auth/csrf", prefix=prefix)
        assert status == 200
        return {"X-CSRF-Token": body["token"]}


def signup_occurrence(client, at=None):
    # /meetings/next deliberately includes an ongoing meeting. Enrollment tests
    # need an unstarted occurrence, even when CI runs during Tuesday's game.
    tomorrow = (at or datetime.now(UTC)).astimezone(ZoneInfo("Europe/Warsaw")).date()
    tomorrow += timedelta(days=1)
    end = tomorrow + timedelta(days=14)
    status, calendar, _ = client.call(f"/api/v1/calendar?from={tomorrow}&to={end}")
    assert status == 200, (status, calendar)
    candidates = [item for item in calendar["items"] if item["status"] == "scheduled"]
    assert candidates, "The disposable fixture needs a future scheduled occurrence"
    return min(candidates, key=lambda item: item["starts_at"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="volleycrew:e10-arm64")
    parser.add_argument("--platform", default="linux/arm64")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--backend-tests", action="store_true")
    args = parser.parse_args()
    run = f"vc-e10-{os.getpid()}"
    state = run + "-state"
    containers = []
    network = run + "-network"
    output = ROOT / ".runtime/e10"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vc-container-") as tmp:
        work = Path(tmp)
        try:
            docker("network", "create", "--subnet", "172.30.32.0/24", network)
            containers.append(run + "-db")
            docker(
                "run",
                "-d",
                "--name",
                containers[-1],
                "--network",
                network,
                "--network-alias",
                "db",
                "--ip",
                "172.30.32.20",
                "-p",
                "127.0.0.1:18543:5432",
                "-e",
                "POSTGRES_USER=volleycrew",
                "-e",
                "POSTGRES_PASSWORD=e10-test-only",
                "-e",
                "POSTGRES_DB=volleycrew_test",
                "postgres:17-bookworm",
            )
            for _ in range(60):
                if "accepting connections" in docker(
                    "exec", containers[-1], "pg_isready", "-U", "volleycrew", check=False
                ):
                    break
                time.sleep(1)
            options = {
                "POSTGRES_HOST": "db",
                "POSTGRES_PASSWORD": "e10-test-only",
                "POSTGRES_DB": "volleycrew_test",
                "PUBLIC_URL": ORIGIN,
                "TRUSTED_PROXY_CIDRS": ["172.30.32.2/32"],
                "BOOTSTRAP_TOKEN": TOKEN,
            }
            (work / "options.json").write_text(json.dumps(options))
            app = run + "-app"
            containers.append(app)
            docker("volume", "create", state)
            docker(
                "create",
                "--name",
                app,
                "--network",
                network,
                "--network-alias",
                "app",
                "--ip",
                "172.30.32.10",
                "--platform",
                args.platform,
                "-v",
                state + ":/data",
                "-p",
                "127.0.0.1:18200:8200",
                "-p",
                "127.0.0.1:18099:8099",
                args.image,
            )
            docker("cp", str(work / "options.json"), app + ":/data/options.json")
            docker("start", app)
            wait("http://127.0.0.1:18200/api/v1/health/ready", container=app)
            print("PASS: real image startup, migrations and readiness", flush=True)
            if args.backend_tests:
                docker("exec", containers[0], "createdb", "-U", "volleycrew", "regression_test")
                backend = subprocess.run(
                    ["npm", "run", "test:backend", "--", "-x", "--tb=short"],
                    cwd=ROOT,
                    env={
                        **os.environ,
                        "VOLLEYCREW_TEST_DATABASE_URL": "postgresql+asyncpg://volleycrew:e10-test-only@127.0.0.1:18543/regression_test",
                    },
                    capture_output=True,
                    text=True,
                )
                (output / "backend-pg17.log").write_text(backend.stdout + backend.stderr)
                assert backend.returncode == 0, (
                    "PG17 backend regression failed; see backend-pg17.log"
                )
                print("PASS: complete backend regression on PostgreSQL 17", flush=True)
            # Fail-closed startup scenarios use their own state and never mutate app DB.
            docker("exec", containers[0], "createdb", "-U", "volleycrew", "broken_test")
            docker(
                "exec",
                containers[0],
                "psql",
                "-U",
                "volleycrew",
                "-d",
                "broken_test",
                "-c",
                "CREATE TABLE alembic_version(version_num varchar(32) PRIMARY KEY); "
                "INSERT INTO alembic_version VALUES ('unknown_revision');",
            )
            for label, changes in [
                ("invalid-config", {"PUBLIC_URL": "http://unsafe.example"}),
                ("missing-db", {"POSTGRES_HOST": "not-a-db"}),
                ("migration-error", {"POSTGRES_DB": "broken_test"}),
            ]:
                name = run + "-" + label
                containers.append(name)
                bad_file = work / (label + ".json")
                bad_file.write_text(json.dumps({**options, **changes}))
                docker(
                    "create",
                    "--name",
                    name,
                    "--network",
                    network,
                    "--platform",
                    args.platform,
                    "-e",
                    "VOLLEYCREW_DB_WAIT_SECONDS=2",
                    args.image,
                )
                docker("cp", str(bad_file), name + ":/data/options.json")
                docker("start", name)
                for _ in range(45):
                    if docker("inspect", "-f", "{{.State.Status}}", name) == "exited":
                        break
                    time.sleep(1)
                assert docker("inspect", "-f", "{{.State.Status}}", name) == "exited", label
                output_log = docker("logs", name)
                assert "Uvicorn running" not in output_log
                assert TOKEN not in output_log and "e10-test-only" not in output_log
            print("PASS: invalid config, missing DB and bad migration keep API stopped", flush=True)
            proxy = run + "-supervisor"
            containers.append(proxy)
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-days",
                    "1",
                    "-keyout",
                    str(work / "key.pem"),
                    "-out",
                    str(work / "cert.pem"),
                    "-subj",
                    "/CN=localhost",
                ],
                capture_output=True,
                check=True,
            )
            conf = """events {}
http {
  access_log off;
  server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/cert.pem;
    ssl_certificate_key /etc/nginx/key.pem;
    location /api/hassio_ingress/volleycrew-test-token/ {
      proxy_pass http://app:8099/;
      proxy_set_header X-Ingress-Path /api/hassio_ingress/volleycrew-test-token;
      proxy_set_header Host $http_host;
    }
    location /api/hassio_ingress/another-token/ {
      proxy_pass http://app:8099/;
      proxy_set_header X-Ingress-Path /api/hassio_ingress/another-token;
      proxy_set_header Host $http_host;
    }
    location / {
      proxy_pass http://app:8200;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header X-Forwarded-For $remote_addr;
      proxy_set_header Host $http_host;
    }
  }
}"""
            (work / "nginx.conf").write_text(conf)
            docker(
                "create",
                "--name",
                proxy,
                "--network",
                network,
                "--ip",
                "172.30.32.2",
                "-p",
                "127.0.0.1:18443:443",
                "nginx:stable-bookworm",
            )
            for filename in ["nginx.conf", "key.pem", "cert.pem"]:
                docker("cp", str(work / filename), proxy + ":/etc/nginx/" + filename)
            docker("start", proxy)
            wait(ORIGIN + "/api/v1/health/ready", container=app)
            client = Client()
            status, admin, _ = client.call(
                "/api/v1/auth/bootstrap",
                "POST",
                {
                    "token": TOKEN,
                    "first_name": "Arkadiusz",
                    "last_name": "Testowy",
                    "nickname": "Container",
                    "pin": "123456",
                },
                headers=client.csrf(),
            )
            assert status == 200, (status, admin)
            for base in [PREFIX, "/api/hassio_ingress/another-token"]:
                status, _, _ = client.call(
                    "/api/v1/auth/login",
                    "POST",
                    {"profile_id": admin["id"], "pin": "123456"},
                    prefix=base,
                    headers=client.csrf(base),
                )
                assert status == 200
                assert client.call("/api/v1/me", prefix=base)[0] == 200
                status, html, headers = client.call("/profile", prefix=base)
                assert status == 200 and f'<base href="{base}/"'.encode() in html
                assert "frame-ancestors 'self'" in headers.get("Content-Security-Policy", "")
                asset = re.search(rb'src="\./(assets/[^"]+)"', html).group(1).decode()
                assert client.call("/" + asset, prefix=base)[0] == 200
            status, _, _ = client.call(
                "/api/v1/auth/logout", "POST", {}, prefix=PREFIX, headers=client.csrf(PREFIX)
            )
            assert status == 200 and client.call("/api/v1/me", prefix=PREFIX)[0] == 401
            assert client.call("/api/v1/me")[0] == 200
            headers = client.csrf()
            assert (
                client.call(
                    "/api/v1/me",
                    "PATCH",
                    {"first_name": "Forbidden", "last_name": "Testowy"},
                    headers={**headers, "Origin": "https://evil.test"},
                )[0]
                == 403
            )
            assert (
                client.call(
                    "/api/v1/me", "PATCH", {"first_name": "Forbidden", "last_name": "Testowy"}
                )[0]
                == 403
            )
            with contextlib.suppress(urllib.error.HTTPError):
                urllib.request.urlopen("http://127.0.0.1:18099/api/v1/health/live", timeout=5)
                raise AssertionError("Ingress must reject non-Supervisor traffic")
            status, _, headers = client.call(
                "/api/v1/auth/csrf", headers={"X-Ingress-Path": PREFIX, "X-Volleycrew-Base": PREFIX}
            )
            assert status == 200 and "vc_csrf_ingress" not in headers.get("Set-Cookie", "")
            print(
                "PASS: HTTPS, two dynamic prefixes, cookies, CSRF and listener isolation",
                flush=True,
            )
            docker("restart", app)
            wait(ORIGIN + "/api/v1/health/ready", container=app)
            assert client.call("/api/v1/me")[0] == 200
            assert (
                client.call(
                    "/api/v1/auth/bootstrap",
                    "POST",
                    {"token": TOKEN, "first_name": "Again", "last_name": "Admin", "pin": "123456"},
                    headers=client.csrf(),
                )[0]
                == 400
            )
            print("PASS: restart keeps identity and bootstrap stays closed", flush=True)
            # Simulate a version change: snapshot must precede even a no-op schema upgrade.
            docker(
                "exec",
                app,
                "python",
                "-c",
                "from pathlib import Path; Path('/data/installed-version').write_text('0.0.0')",
            )
            docker("restart", app)
            wait(ORIGIN + "/api/v1/health/ready", container=app)
            archives = docker(
                "exec",
                app,
                "python",
                "-c",
                "from pathlib import Path; "
                "print(len(list(Path('/data/backups').glob('*.tar.gz'))))",
            )
            assert int(archives) >= 1
            assert client.call("/api/v1/me")[0] == 200
            print("PASS: version change makes a pre-upgrade backup before API start", flush=True)

            def mutate(path, data, method="POST", actor=client):
                status, value, _ = actor.call(
                    "/api/v1" + path,
                    method,
                    data,
                    headers={**actor.csrf(), "Idempotency-Key": str(uuid4())},
                )
                assert status == 200, (path, status, value)
                return value

            invite = mutate("/admin/invites", {})["url"].split("#")[1]
            players = [admin["id"]]
            actors = [client]
            for first in ["Agnieszka", "Michał"]:
                actor = Client()
                person = mutate(
                    "/auth/register",
                    {"token": invite, "first_name": first, "last_name": "Nowak", "pin": "654321"},
                    actor=actor,
                )
                players.append(person["id"])
                actors.append(actor)
            upcoming = signup_occurrence(client)
            meeting = mutate(
                "/meetings/resolve",
                {
                    "schedule_version_id": upcoming["schedule_version_id"],
                    "source_date": upcoming["source_date"],
                },
            )
            mid = str(UUID(meeting["id"]))
            for actor in actors:
                mutate(
                    f"/meetings/{mid}/my-declaration",
                    {"declaration": "going", "term_version": meeting["term_version"]},
                    "PUT",
                    actor,
                )
            # The only direct meeting edit is fixture time, just like seed_e2e.py.
            docker(
                "exec",
                containers[0],
                "psql",
                "-U",
                "volleycrew",
                "-d",
                "volleycrew_test",
                "-c",
                "UPDATE meetings SET starts_at=CURRENT_TIMESTAMP-interval '15 minutes', "
                "ends_at=CURRENT_TIMESTAMP+interval '105 minutes', is_exception=true "
                f"WHERE id='{mid}';",
            )

            def room(path, fields=None, method="POST"):
                current = client.call(f"/api/v1/meetings/{mid}")[1]
                return mutate(
                    f"/admin/meetings/{mid}/{path}",
                    {"expected_version": current["version"], **(fields or {})},
                    method,
                )

            room(
                "attendance",
                {"players": [{"player_id": pid, "state": "present"} for pid in players]},
                "PUT",
            )
            room("attendance/confirm")
            room("teams/generate", {"mode": "balanced"})
            room("teams/confirm")
            preview = room("result-preview", {"sets_a": 5, "sets_b": 3})
            room(
                "result",
                {"sets_a": 5, "sets_b": 3, "expected_rating_version": preview["rating_version"]},
            )
            assert client.call(f"/api/v1/admin/meetings/{mid}/signature-list")[0] == 200
            print(
                "PASS: real packaged cycle: signup, presence, teams, PDF, 5:3 and ELO", flush=True
            )
            # Exercise the actual frontend against the packaged Nginx/API, not Vite.
            result = subprocess.run(
                [
                    "npm",
                    "--prefix",
                    "volleycrew/frontend",
                    "run",
                    "test:container",
                ],
                cwd=ROOT,
                env={
                    **os.environ,
                    "VOLLEYCREW_CONTAINER_URL": ORIGIN,
                    "VOLLEYCREW_CONTAINER_MEETING": mid,
                },
                capture_output=True,
                text=True,
            )
            (output / "browser.log").write_text(result.stdout + result.stderr)
            assert result.returncode == 0, (
                "Packaged frontend test failed; see .runtime/e10/browser.log"
            )
            docker("stop", containers[0])
            assert client.call("/api/v1/health/live")[0] == 200
            assert client.call("/api/v1/health/ready")[0] == 503
            docker("start", containers[0])
            wait(ORIGIN + "/api/v1/health/ready", container=app)
            print("PASS: readiness detects DB loss and recovers; process stays live", flush=True)
            bundle = docker("exec", app, "/usr/local/bin/volleycrew-backup", "create").splitlines()[
                -1
            ]
            docker("cp", app + ":" + bundle, str(output / "snapshot.tar.gz"))

            # A separate PostgreSQL instance proves restore isn't a same-server copy.
            restored = run + "-restored-db"
            containers.append(restored)
            docker(
                "run",
                "-d",
                "--name",
                restored,
                "--network",
                network,
                "--network-alias",
                "restored-db",
                "-e",
                "POSTGRES_USER=volleycrew",
                "-e",
                "POSTGRES_PASSWORD=e10-test-only",
                "-e",
                "POSTGRES_DB=restore_test",
                "postgres:17-bookworm",
            )
            for _ in range(60):
                if "accepting connections" in docker(
                    "exec", restored, "pg_isready", "-U", "volleycrew", check=False
                ):
                    break
                time.sleep(1)
            docker(
                "exec",
                "-e",
                "VOLLEYCREW_RESTORE_DATABASE_URL=postgresql+asyncpg://volleycrew:e10-test-only@restored-db/restore_test",
                app,
                "/usr/local/bin/volleycrew-backup",
                "restore",
                bundle,
                "--confirm-empty-target",
            )
            check = docker(
                "exec",
                restored,
                "psql",
                "-U",
                "volleycrew",
                "-d",
                "restore_test",
                "-Atc",
                "SELECT count(*) FROM players; "
                "SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL; "
                "SELECT version_num FROM alembic_version;",
            )
            assert check.splitlines() == ["3", "0", migration_head(app)], check
            for table in [
                "players",
                "schedule_versions",
                "meetings",
                "enrollments",
                "enrollment_events",
                "attendance",
                "attendance_events",
                "team_sheets",
                "team_members",
                "result_revisions",
                "rating_entries",
                "player_ratings",
                "audit_events",
            ]:
                query = (
                    f"SELECT count(*), md5(coalesce(jsonb_agg(to_jsonb(t) "
                    f"ORDER BY to_jsonb(t)::text)::text, '[]')) FROM {table} t;"
                )
                before = docker(
                    "exec",
                    containers[0],
                    "psql",
                    "-U",
                    "volleycrew",
                    "-d",
                    "volleycrew_test",
                    "-Atc",
                    query,
                )
                after = docker(
                    "exec",
                    restored,
                    "psql",
                    "-U",
                    "volleycrew",
                    "-d",
                    "restore_test",
                    "-Atc",
                    query,
                )
                assert before == after, table
            assert client.call("/api/v1/me")[0] == 200  # Source DB was never the restore target.
            print(
                "PASS: private backup restored on separate PostgreSQL; sessions revoked", flush=True
            )
            logs = docker("logs", app)
            assert TOKEN not in logs and "e10-test-only" not in logs
            (output / "container.log").write_text(logs)
            print("PASS: no bootstrap token/database password in application logs", flush=True)
            if args.keep:
                print("Keeping disposable test containers and volumes", flush=True)
                input("Press Enter to clean up: ")
        finally:
            volumes = {state}
            for name in reversed(containers):
                raw = docker("inspect", "-f", "{{json .Mounts}}", name, check=False)
                with contextlib.suppress(ValueError):
                    volumes.update(m["Name"] for m in json.loads(raw) if m["Type"] == "volume")
                docker("rm", "-f", name, check=False)
            for volume in volumes:
                docker("volume", "rm", volume, check=False)
            docker("network", "rm", network, check=False)


if __name__ == "__main__":
    main()
