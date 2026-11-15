"""Explicit local development accounts for reviewing both application roles."""

import asyncio
from uuid import UUID, uuid5

from sqlalchemy.engine import make_url

from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.database import Database
from app.core.security import hash_password
from app.models.auth import Player

PROFILES = (
    (UUID("d80b3a15-f958-4b52-9d96-9e5fe2200001"), "Admin", "admin", "founder"),
    (UUID("d80b3a15-f958-4b52-9d96-9e5fe2200002"), "User", "player", "player"),
)


DEMO_PLAYERS = (
    ("Anna", "Kowalska"),
    ("Michał", "Nowak"),
    ("Julia", "Wiśniewska"),
    ("Tomasz", "Wójcik"),
    ("Katarzyna", "Kamińska"),
    ("Piotr", "Lewandowski"),
    ("Marta", "Zielińska"),
    ("Paweł", "Szymański"),
    ("Aleksandra", "Woźniak"),
    ("Kamil", "Dąbrowski"),
    ("Agnieszka", "Kozłowska"),
    ("Mateusz", "Jankowski"),
)


async def seed():
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not (url.database or "").endswith(
        "_dev"
    ):
        raise SystemExit("Preview accounts require a loopback database ending in _dev.")
    database = Database(settings.database_url.get_secret_value())
    try:
        async with database.sessions() as db:
            for identifier, name, role, priority in PROFILES:
                if await db.get(Player, identifier) is None:
                    db.add(
                        Player(
                            id=identifier,
                            username=("admin-demo" if role == "admin" else "user-demo"),
                            first_name=name,
                            last_name="Demo",
                            nickname="Podgląd lokalny",
                            role=role,
                            priority_status=priority,
                            password_hash=await hash_password("Preview-test-password-123"),
                            created_at=SystemClock().now(),
                        )
                    )
            password_hash = await hash_password("Preview-test-password-123")
            for first_name, last_name in DEMO_PLAYERS:
                identifier = uuid5(PROFILES[0][0], f"{first_name}:{last_name}")
                if await db.get(Player, identifier) is None:
                    db.add(
                        Player(
                            id=identifier,
                            username="demo-" + identifier.hex[:24],
                            first_name=first_name,
                            last_name=last_name,
                            nickname="Podgląd lokalny",
                            role="player",
                            priority_status="player",
                            password_hash=password_hash,
                            created_at=SystemClock().now(),
                        )
                    )
            await db.commit()
        print(
            "Local preview: admin-demo / user-demo + 12 players; "
            "password Preview-test-password-123."
        )
    finally:
        await database.engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
