"""Private portable DB/config snapshots. Restore only into an explicitly empty target."""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings
from app.core.security import load_auth_key
from app.deployment import Options, load_environment, private_write

log = logging.getLogger("volleycrew.backup")


def pg_env(settings: Settings) -> dict[str, str]:
    url = make_url(settings.database_url.get_secret_value())
    # Never put passwords into argv or printed connection strings.
    return {
        **os.environ,
        "PGHOST": url.host or "",
        "PGPORT": str(url.port or 5432),
        "PGDATABASE": url.database or "",
        "PGUSER": url.username or "",
        "PGPASSWORD": url.password or "",
        "PGSSLMODE": url.query.get("ssl", "prefer"),
        "PGCONNECT_TIMEOUT": "5",
    }


def pg_run(settings: Settings, args: list[str]) -> bytes:
    result = subprocess.run(args, env=pg_env(settings), capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed; inspect database connectivity/version/permissions")
    return result.stdout


def sql(settings: Settings, query: str) -> str:
    return (
        pg_run(settings, ["psql", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", query])
        .decode()
        .strip()
    )


def create_backup(settings: Settings, reason: str = "manual") -> Path:
    folder = settings.state_dir / "backups"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    with tempfile.TemporaryDirectory(dir=folder, prefix=".snapshot-") as tmp:
        work = Path(tmp)
        dump = work / "database.dump"
        pg_run(
            settings, ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(dump)]
        )
        key = load_auth_key(settings)
        private_write(work / "auth.key", key)
        options_file = settings.state_dir / "options.json"
        if options_file.exists():
            private_write(work / "options.json", options_file.read_bytes())
        with dump.open("rb") as stream:
            dump_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        private_write(
            work / "manifest.json",
            json.dumps(
                {
                    "format": 1,
                    "created_at": datetime.now(UTC).isoformat(),
                    "reason": reason,
                    "schema": sql(settings, "SELECT version_num FROM alembic_version"),
                    "app_version": (settings.state_dir / "installed-version").read_text().strip()
                    if (settings.state_dir / "installed-version").exists()
                    else "unknown",
                    "database_sha256": dump_hash,
                    "auth_key_sha256": hashlib.sha256(key).hexdigest(),
                }
            ),
        )
        name = datetime.now(UTC).strftime("volleycrew-%Y%m%dT%H%M%S%fZ.tar.gz")
        target = folder / name
        partial = folder / (name + ".partial")
        try:
            private_write(partial, b"")
            with tarfile.open(partial, "w:gz") as archive:
                for file in work.iterdir():
                    archive.add(file, arcname=file.name)
            with partial.open("rb") as stream:
                os.fsync(stream.fileno())
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    mode = settings.state_dir / "database-mode"
    if mode.exists() and mode.read_text().strip() == "embedded":
        recovery = settings.state_dir / "postgres-recovery.tar.gz"
        # A fixed, atomically replaced archive avoids a pointer to a file that
        # HA's concurrent directory traversal might not have captured.
        with tempfile.NamedTemporaryFile(
            dir=settings.state_dir, prefix=".recovery-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            try:
                with target.open("rb") as source:
                    shutil.copyfileobj(source, stream)
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        temporary.replace(recovery)
    log.info("Backup completed: %s; copy it outside this host", target.name)
    # Retention is intentionally manual until the off-host destination/policy is chosen.
    return target


def restore(
    settings: Settings, archive_path: Path, *, confirm_empty: bool, retain_sessions: bool = False
) -> None:
    if not confirm_empty:
        raise ValueError("Explicit --confirm-empty-target required")
    if sql(settings, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") != "0":
        raise ValueError("Target database is not empty; restore does not drop existing data")
    allowed = {"database.dump", "auth.key", "manifest.json", "options.json"}
    with tempfile.TemporaryDirectory(prefix="volleycrew-restore-") as tmp:
        work = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as archive:
            seen = set()
            for member in archive:
                if member.name not in allowed or not member.isfile() or member.name in seen:
                    raise ValueError("Invalid backup member")
                seen.add(member.name)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("Invalid backup file")
                with source, (work / member.name).open("wb") as dest:
                    import shutil

                    shutil.copyfileobj(source, dest)
        if not {"database.dump", "manifest.json", "auth.key"} <= seen:
            raise ValueError("Incomplete backup")
        manifest = json.loads((work / "manifest.json").read_text())
        with (work / "database.dump").open("rb") as dump:
            checksum = hashlib.file_digest(dump, "sha256").hexdigest()
        key = (work / "auth.key").read_bytes()
        if (
            manifest.get("format") != 1
            or checksum != manifest["database_sha256"]
            or hashlib.sha256(key).hexdigest() != manifest["auth_key_sha256"]
        ):
            raise ValueError("Backup checksum/format mismatch")
        if (
            retain_sessions
            and settings.session_secret
            and settings.session_secret.get_secret_value().encode() != key
        ):
            raise ValueError("Configured SESSION_SECRET differs from the backup")
        pg_run(
            settings,
            [
                "pg_restore",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
                "--dbname",
                pg_env(settings)["PGDATABASE"],
                str(work / "database.dump"),
            ],
        )
        if retain_sessions:
            private_write(settings.state_dir / "auth.key", key)
        else:
            sql(
                settings,
                "UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE revoked_at IS NULL",
            )
        # Never overwrite current DB connection options with the source's production address.
        if (work / "options.json").exists():
            private_write(
                settings.state_dir / "restored-options.json", (work / "options.json").read_bytes()
            )
    log.info(
        "Restore complete; verify options and use the image matching schema %s", manifest["schema"]
    )


def schedule() -> None:
    settings = get_settings()
    zone = ZoneInfo("Europe/Warsaw")
    while True:
        opts = Options.model_validate_json((settings.state_dir / "options.json").read_bytes())
        now = datetime.now(zone)
        due = now.replace(hour=opts.BACKUP_HOUR, minute=0, second=0, microsecond=0)
        if due <= now:
            due += timedelta(days=1)
        # Timestamp difference handles DST; the next due date is recomputed after each run.
        time.sleep(max(1, due.timestamp() - now.timestamp()))
        try:
            create_backup(settings, "daily")
        except Exception as exc:
            log.error("Daily backup failed (%s); retry in one hour", type(exc).__name__)
            time.sleep(3600)
            try:
                create_backup(settings, "daily-retry")
            except Exception as retry:
                log.error("Daily retry failed (%s); operator action required", type(retry).__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[volleycrew] %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create", "restore", "schedule"])
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--confirm-empty-target", action="store_true")
    parser.add_argument("--retain-sessions", action="store_true")
    args = parser.parse_args()
    try:
        load_environment()
        get_settings.cache_clear()
        if args.command == "schedule":
            schedule()
        elif args.command == "create":
            print(create_backup(get_settings()))
        elif args.archive:
            target = os.environ.get("VOLLEYCREW_RESTORE_DATABASE_URL")
            if not target:
                raise ValueError("Set an explicit VOLLEYCREW_RESTORE_DATABASE_URL")
            values = {**get_settings().model_dump(), "database_url": target}
            restore(
                Settings(_env_file=None, **values),
                args.archive,
                confirm_empty=args.confirm_empty_target,
                retain_sessions=args.retain_sessions,
            )
        else:
            parser.error("Restore requires an archive")
    except Exception as exc:
        log.error(
            "Backup/restore failed (%s); existing target is never automatically cleared",
            type(exc).__name__,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
