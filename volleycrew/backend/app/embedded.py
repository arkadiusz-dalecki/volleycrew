"""Private PostgreSQL 17 lifecycle. Only loopback TCP and peer-authenticated admin socket."""

import logging
import os
import pwd
import signal
import subprocess
import sys
from pathlib import Path

from app.deployment import Options, private_write

PG_BIN = Path("/usr/lib/postgresql/17/bin")
STATE = Path("/data")
log = logging.getLogger("volleycrew.postgres")


def pg(args: list[str], *, sql: str | None = None) -> str:
    result = subprocess.run(
        ["runuser", "-u", "postgres", "--", *args],
        input=sql,
        text=True,
        capture_output=True,
        timeout=90,
    )
    if result.returncode:
        raise RuntimeError("Bundled PostgreSQL command failed; check storage/permissions")
    return result.stdout.strip()


def admin(query: str) -> str:
    return pg(
        [
            "psql",
            "-XAt",
            "-h",
            "/run/postgresql",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        sql=query,
    )


def start(state: Path = STATE) -> None:
    cluster = state / "postgresql"
    initialized = state / "postgres-initialized"
    pending = state / "postgres-restore-pending"
    fresh = not (cluster / "PG_VERSION").exists()
    if not fresh and (cluster / "PG_VERSION").read_text().strip() != "17":
        raise RuntimeError("Bundled PostgreSQL major version mismatch; explicit migration required")
    if fresh and initialized.exists():
        private_write(pending, "restore required")
    if pending.exists() and not (state / "postgres-recovery.tar.gz").exists():
        raise RuntimeError(
            "Bundled database files missing without recovery snapshot; refusing empty start"
        )
    account = pwd.getpwnam("postgres")
    os.chmod(state, 0o711)
    socket = Path("/run/postgresql")
    socket.mkdir(exist_ok=True)
    os.chown(socket, account.pw_uid, account.pw_gid)
    os.chmod(socket, 0o700)
    if fresh:
        cluster.mkdir(exist_ok=True)
        os.chown(cluster, account.pw_uid, account.pw_gid)
        os.chmod(cluster, 0o700)
        pg(
            [
                str(PG_BIN / "initdb"),
                "-D",
                str(cluster),
                "--auth-local=peer",
                "--auth-host=scram-sha-256",
                "--encoding=UTF8",
                "--locale=C",
            ]
        )
        # Durable defaults; never rewrite the cluster or rotate credentials on restart.
        with (cluster / "postgresql.conf").open("a") as stream:
            stream.write(
                "\nlisten_addresses='127.0.0.1'\nport=5432\nunix_socket_directories='/run/postgresql'\nshared_buffers=32MB\nmax_connections=30\nwork_mem=2MB\n"
            )
    pg(
        [
            str(PG_BIN / "pg_ctl"),
            "-D",
            str(cluster),
            "-l",
            "/run/postgresql/postgres.log",
            "-w",
            "-t",
            "60",
            "start",
        ]
    )
    secret = (state / "postgres-password").read_text().strip()
    if not admin("SELECT 1 FROM pg_roles WHERE rolname='volleycrew';"):
        # Generated hexadecimal password; no credentials in argv, stdout or logs.
        if len(secret) != 64 or any(c not in "0123456789abcdef" for c in secret):
            raise ValueError("Invalid bundled password file")
        admin(
            f"CREATE ROLE volleycrew LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{secret}';"
        )
    if not admin("SELECT 1 FROM pg_database WHERE datname='volleycrew';"):
        admin("CREATE DATABASE volleycrew OWNER volleycrew;")
    if pending.exists():
        from app.backup import restore

        options = Options.model_validate_json((state / "options.json").read_bytes())
        restore(
            options.settings(state),
            state / "postgres-recovery.tar.gz",
            confirm_empty=True,
            retain_sessions=True,
        )
        pending.unlink()
        log.info("Bundled database restored from portable HA backup snapshot")
    private_write(initialized, "17")
    log.info("Bundled PostgreSQL ready (private loopback listener)")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[volleycrew] %(message)s")
    try:
        if (STATE / "database-mode").read_text().strip() != "embedded":
            if sys.argv[1:] == ["serve"]:
                signal.pause()
            return
        command = sys.argv[1:]
        if command == ["start"]:
            start()
        elif command == ["stop"]:
            if (STATE / "postgresql/postmaster.pid").exists():
                pg(
                    [
                        str(PG_BIN / "pg_ctl"),
                        "-D",
                        str(STATE / "postgresql"),
                        "-w",
                        "-t",
                        "60",
                        "-m",
                        "fast",
                        "stop",
                    ]
                )
        elif command == ["serve"]:
            account = pwd.getpwnam("postgres")
            os.setgroups([])
            os.setgid(account.pw_gid)
            os.setuid(account.pw_uid)
            os.execv(
                str(PG_BIN / "postgres"),
                [str(PG_BIN / "postgres"), "-D", str(STATE / "postgresql")],
            )
        else:
            raise ValueError("Use start, stop or serve")
    except Exception as exc:
        log.error(
            "Bundled database startup failed (%s); existing data retained", type(exc).__name__
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
