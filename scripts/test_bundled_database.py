#!/usr/bin/env python3
"""Disposable real-image tests for zero-config PostgreSQL, durability and HA snapshot recovery."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from test_container import TOKEN, docker, migration_head, wait


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--platform", required=True)
    args = parser.parse_args()
    name = f"vc-bundled-{os.getpid()}"
    volume = name + "-state"
    names = []
    volumes = [volume, volume + "-restored", volume + "-broken", volume + "-cold"]

    def launch(target, data):
        names.append(target)
        docker(
            "create",
            "--name",
            target,
            "--platform",
            args.platform,
            "-v",
            data + ":/data",
            "-p",
            "127.0.0.1:18201:8200",
            args.image,
        )

    def ready(target):
        wait("http://127.0.0.1:18201/api/v1/health/ready", seconds=240, container=target)

    def sql(target, query):
        return docker(
            "exec",
            target,
            "runuser",
            "-u",
            "postgres",
            "--",
            "psql",
            "-XAt",
            "-h",
            "/run/postgresql",
            "-d",
            "volleycrew",
            "-c",
            query,
        )

    try:
        with tempfile.TemporaryDirectory(prefix="vc-bundled-") as tmp:
            work = Path(tmp)
            config = work / "options.json"
            # Match an existing 0.1.1 installation with blank PostgreSQL options.
            config.write_text(
                json.dumps(
                    {
                        "PUBLIC_URL": "https://bundled.test",
                        "POSTGRES_HOST": "",
                        "POSTGRES_PASSWORD": "",
                        "BOOTSTRAP_TOKEN": TOKEN,
                        "TRUSTED_PROXY_CIDRS": ["127.0.0.1/32"],
                    }
                )
            )
            launch(name, volume)
            docker("cp", str(config), name + ":/data/options.json")
            docker("start", name)
            ready(name)
            assert sql(name, "SELECT rolsuper FROM pg_roles WHERE rolname='volleycrew'") == "f"
            assert sql(name, "SHOW listen_addresses") == "127.0.0.1"
            assert sql(name, "SHOW server_version").startswith("17.")
            assert sql(name, "SELECT version_num FROM alembic_version") == migration_head(name)
            # Real Nginx/API request, loopback fixture trusted only for this test.
            code = """import http.client, json
from http.cookies import SimpleCookie
c=http.client.HTTPConnection('127.0.0.1',8200)
h={'Origin':'https://bundled.test','X-Forwarded-Proto':'https'}
c.request('GET','/api/v1/auth/csrf',headers=h)
r=c.getresponse(); csrf=json.loads(r.read())['token']; cookies=SimpleCookie()
for key,value in r.getheaders():
 if key.lower()=='set-cookie': cookies.load(value)
h['Cookie']='; '.join(k+'='+v.value for k,v in cookies.items())
h['X-CSRF-Token']=csrf; h['Content-Type']='application/json'
c.request('POST','/api/v1/auth/bootstrap',json.dumps({'first_name':'Embedded','last_name':'Testowy','nickname':None,'pin':'123456','token':TOKEN}),h)
r=c.getresponse(); body=json.loads(r.read())
assert r.status==200,(r.status,body.get('code'))
assert body['role']=='admin'
"""
            docker("exec", name, "python", "-c", "TOKEN=" + repr(TOKEN) + "\n" + code)
            fingerprint = sql(name, "SELECT md5(jsonb_agg(to_jsonb(p))::text) FROM players p")
            assert sql(name, "SELECT count(*) FROM players") == "1"
            print(
                "PASS: empty options create private PostgreSQL, migrations and real admin",
                flush=True,
            )
            docker("restart", "-t", "30", name)
            ready(name)
            assert (
                sql(name, "SELECT md5(jsonb_agg(to_jsonb(p))::text) FROM players p") == fingerprint
            )
            docker("kill", "--signal", "KILL", name)
            docker("start", name)
            ready(name)
            assert (
                sql(name, "SELECT md5(jsonb_agg(to_jsonb(p))::text) FROM players p") == fingerprint
            )
            print("PASS: graceful restart and unclean shutdown preserve data", flush=True)
            docker(
                "exec",
                name,
                "python",
                "-c",
                "from pathlib import Path; "
                "Path('/app/VERSION').write_text('bundled-upgrade-fixture')",
            )
            docker("restart", "-t", "30", name)
            ready(name)
            assert sql(name, "SELECT count(*) FROM players") == "1"
            print("PASS: bundled pre-upgrade backup runs before migrations", flush=True)
            docker("exec", name, "/usr/local/bin/volleycrew-backup", "create")
            # Simulate HA hot backup exclusions while the source remains running.
            docker(
                "exec",
                name,
                "tar",
                "-czf",
                "/tmp/ha-state.tgz",
                "--exclude=./postgresql",
                "--exclude=./backups/*.partial",
                "-C",
                "/data",
                ".",
            )
            docker("cp", name + ":/tmp/ha-state.tgz", str(work / "ha-state.tgz"))
            password = docker("exec", name, "cat", "/data/postgres-password")
            docker("stop", "-t", "30", name)
            cold_helper = name + "-cold-helper"
            names.append(cold_helper)
            docker(
                "create",
                "--name",
                cold_helper,
                "--platform",
                args.platform,
                "--entrypoint",
                "sh",
                "-v",
                volume + ":/data:ro",
                args.image,
                "-c",
                "tar -czf /tmp/cold.tgz -C /data .",
            )
            docker("start", "-a", cold_helper)
            docker("cp", cold_helper + ":/tmp/cold.tgz", str(work / "cold.tgz"))
            cold_extract = name + "-cold-extract-helper"
            names.append(cold_extract)
            docker(
                "create",
                "--name",
                cold_extract,
                "--platform",
                args.platform,
                "--entrypoint",
                "sh",
                "-v",
                volumes[3] + ":/data",
                args.image,
                "-c",
                "tar -xzf /tmp/cold.tgz -C /data",
            )
            docker("cp", str(work / "cold.tgz"), cold_extract + ":/tmp/cold.tgz")
            docker("start", "-a", cold_extract)
            cold = name + "-cold"
            launch(cold, volumes[3])
            docker("start", cold)
            ready(cold)
            assert (
                sql(cold, "SELECT md5(jsonb_agg(to_jsonb(p))::text) FROM players p") == fingerprint
            )
            docker("stop", "-t", "30", cold)
            print("PASS: stopped HA backup restores the complete PostgreSQL cluster", flush=True)
            for suffix, destination in [("restored", volumes[1]), ("broken", volumes[2])]:
                target = name + "-" + suffix
                # A disposable helper extracts the simulated HA snapshot into a new volume.
                helper = target + "-helper"
                names.append(helper)
                docker(
                    "create",
                    "--name",
                    helper,
                    "--platform",
                    args.platform,
                    "--entrypoint",
                    "sh",
                    "-v",
                    destination + ":/data",
                    args.image,
                    "-c",
                    "tar -xzf /tmp/ha-state.tgz -C /data",
                )
                docker("cp", str(work / "ha-state.tgz"), helper + ":/tmp/ha-state.tgz")
                docker("start", "-a", helper)
                if suffix == "broken":
                    # No recovery archive must fail closed instead of silently resetting data.
                    helper2 = target + "-remove"
                    names.append(helper2)
                    docker(
                        "run",
                        "--name",
                        helper2,
                        "--platform",
                        args.platform,
                        "--entrypoint",
                        "rm",
                        "-v",
                        destination + ":/data",
                        args.image,
                        "/data/postgres-recovery.tar.gz",
                    )
                launch(target, destination)
                docker("start", target)
                if suffix == "restored":
                    ready(target)
                    assert (
                        sql(target, "SELECT md5(jsonb_agg(to_jsonb(p))::text) FROM players p")
                        == fingerprint
                    )
                    assert (
                        sql(target, "SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL")
                        == "1"
                    )
                    docker("restart", "-t", "30", target)
                    ready(target)
                    assert sql(target, "SELECT count(*) FROM players") == "1"
                    print(
                        "PASS: portable snapshot restores identity and sessions",
                        flush=True,
                    )
                    docker("stop", "-t", "30", target)
                else:
                    import time

                    for _ in range(80):
                        if docker("inspect", "-f", "{{.State.Status}}", target) == "exited":
                            break
                        time.sleep(1)
                    assert docker("inspect", "-f", "{{.State.Status}}", target) == "exited"
                    assert "Uvicorn running" not in docker("logs", target)
                    print(
                        "PASS: incomplete HA recovery refuses an empty replacement database",
                        flush=True,
                    )
            logs = "\n".join(
                docker("logs", target)
                for target in names
                if "-helper" not in target and "-remove" not in target
            )
            assert TOKEN not in logs and password not in logs
            output = Path(".runtime/bundled")
            output.mkdir(parents=True, exist_ok=True)
            (output / "container.log").write_text(logs)
    finally:
        for target in reversed(names):
            docker("rm", "-f", target, check=False)
        for data in volumes:
            docker("volume", "rm", data, check=False)


if __name__ == "__main__":
    main()
