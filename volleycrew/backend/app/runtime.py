"""Bounded startup: validate -> wait for DB -> backup existing schema -> migrate -> bootstrap."""

import asyncio
import logging
import os
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select, text

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.database import Database
from app.core.security import load_auth_key, token_hash
from app.deployment import Options, prepare, private_write
from app.models.auth import BootstrapGrant, Player
from app.services.auth import auth_lock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("volleycrew.startup")


def read_optional(path: Path) -> str | None:
    return path.read_text().strip() if path.exists() else None


async def bootstrap(database: Database, value: str) -> None:
    if not value:
        return
    async with database.sessions() as db:
        await auth_lock(db)
        if await db.scalar(select(Player.id).where(Player.role == "admin").limit(1)):
            return
        grant = await db.get(BootstrapGrant, 1)
        hashed = token_hash(value)
        if grant and grant.token_hash == hashed:
            return  # Restart never renews the 30-minute grant.
        at = SystemClock().now()
        if grant is None:
            grant = BootstrapGrant(id=1)
            db.add(grant)
        grant.token_hash, grant.created_at = hashed, at
        grant.expires_at, grant.used_at = at + timedelta(minutes=30), None
        await db.commit()
        log.info("Bootstrap ready for 30 minutes; open PUBLIC_URL/setup#your-token")


async def initialize(wait_seconds: float = 60) -> None:
    from app.backup import create_backup

    settings = get_settings()
    database = Database(settings.database_url.get_secret_value())
    deadline = time.monotonic() + wait_seconds
    log.info("Waiting for database (bounded startup)")
    try:
        while True:
            try:
                async with database.engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Database unavailable; check connection options") from None
                await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))
        # Keep migration and pre-upgrade snapshot under an exclusive session lock.
        async with database.engine.connect() as conn:
            await conn.execute(text("SELECT pg_advisory_lock(82471602)"))
            try:
                revision = None
                if await conn.scalar(text("SELECT to_regclass('public.alembic_version')")):
                    revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
                from app.core.database import expected_revision

                load_auth_key(settings)
                image_version = (
                    await asyncio.to_thread(read_optional, Path("/app/VERSION")) or "development"
                )
                installed = await asyncio.to_thread(
                    read_optional, settings.state_dir / "installed-version"
                )
                if revision and (revision != expected_revision() or installed != image_version):
                    log.info("Creating mandatory backup before migration")
                    await asyncio.to_thread(create_backup, settings, "pre-upgrade")
                log.info("Applying database migrations")
                result = await asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    capture_output=True,
                    cwd=BACKEND_ROOT,
                    timeout=180,
                    check=False,
                )
                if result.returncode:
                    raise RuntimeError("Migration failed; API remains stopped")
            finally:
                await conn.execute(text("SELECT pg_advisory_unlock(82471602)"))
        options_file = settings.state_dir / "options.json"
        if options_file.exists():
            options = Options.model_validate_json(options_file.read_bytes())
            await bootstrap(database, options.BOOTSTRAP_TOKEN.get_secret_value())
        await asyncio.to_thread(
            private_write, settings.state_dir / "installed-version", image_version
        )
        log.info("Database schema ready")
    finally:
        await database.engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[volleycrew] %(message)s")
    try:
        if sys.argv[1:] == ["prepare"]:
            prepare()
        elif sys.argv[1:] == ["initialize"]:
            asyncio.run(initialize(float(os.environ.get("VOLLEYCREW_DB_WAIT_SECONDS", "60"))))
        else:
            raise ValueError("Use prepare or initialize")
    except ValidationError as exc:
        # Report field names only: values and validation messages can contain credentials.
        fields = sorted(
            {
                str(error["loc"][0]) if error["loc"] else "options"
                for error in exc.errors(include_input=False, include_url=False)
            }
        )
        log.error("Invalid configuration fields: %s", ", ".join(fields))
        raise SystemExit(1) from None
    except Exception as exc:
        # Driver exceptions and Pydantic errors can contain secrets. Do not print them.
        log.error("Startup failed (%s); verify options, database and schema", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
