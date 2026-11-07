"""Operator-only bootstrap. Prints a one-time URL, never chooses or prints a PIN."""

import asyncio
import sys
from datetime import timedelta

from sqlalchemy import select

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.database import Database
from app.core.security import new_token, token_hash
from app.models.auth import BootstrapGrant, Player
from app.services.auth import auth_lock


async def create_bootstrap() -> None:
    settings = get_settings()
    db = Database(settings.database_url.get_secret_value())
    try:
        async with db.sessions() as session:
            await auth_lock(session)
            if await session.scalar(select(Player.id).where(Player.role == "admin").limit(1)):
                raise SystemExit("Administrator already exists; bootstrap is permanently closed.")
            grant = await session.get(BootstrapGrant, 1)
            if grant and "--rotate" not in sys.argv:
                raise SystemExit("A grant already exists. Use --rotate to invalidate the old link.")
            value, at = new_token(), SystemClock().now()
            if grant is None:
                grant = BootstrapGrant(id=1)
                session.add(grant)
            grant.token_hash, grant.created_at = token_hash(value), at
            grant.expires_at, grant.used_at = at + timedelta(minutes=30), None
            await session.commit()
            print(f"{settings.public_url}/setup#{value}")
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "create-bootstrap":
        raise SystemExit("Usage: python -m app.manage create-bootstrap [--rotate]")
    asyncio.run(create_bootstrap())
