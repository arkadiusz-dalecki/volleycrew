"""Prove a brand-new database can apply the entire chain, not just stamp head."""

import asyncio
import os

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.database import expected_revision, migration_config


def test_fresh_migration_chain(monkeypatch):
    url = os.environ.get("VOLLEYCREW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set VOLLEYCREW_TEST_DATABASE_URL")
    if not make_url(url).database.endswith("_test"):
        pytest.fail("Fresh migrations require a disposable *_test DB")
    monkeypatch.setenv("VOLLEYCREW_DATABASE_URL", url)
    monkeypatch.setenv("VOLLEYCREW_ENV_FILE", "/nonexistent-volleycrew-test.env")
    get_settings.cache_clear()

    async def fresh():
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DROP SCHEMA public CASCADE"))
                await conn.execute(text("CREATE SCHEMA public"))
        finally:
            await engine.dispose()

    asyncio.run(fresh())
    command.upgrade(migration_config(), "head")

    async def verify():
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                assert (
                    await conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == expected_revision()
                )
                assert await conn.scalar(text("SELECT count(*) FROM attendance_events")) == 0
        finally:
            await engine.dispose()

    asyncio.run(verify())
    get_settings.cache_clear()
