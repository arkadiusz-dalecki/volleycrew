import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.models import (
    Base,
    auth,  # noqa: F401 — register auth metadata
    enrollment,  # noqa: F401 — register allocation metadata
    meetings,  # noqa: F401 — register meeting metadata
    results,  # noqa: F401 — register results/rating metadata
    room,  # noqa: F401 — register room metadata
    schedule,  # noqa: F401 — register schedule change metadata
)

target_metadata = Base.metadata


def run_sync(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    engine = create_async_engine(get_settings().database_url.get_secret_value())
    async with engine.connect() as connection:
        await connection.run_sync(run_sync)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
