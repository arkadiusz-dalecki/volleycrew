import asyncio
import os

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.core.database import expected_revision, migration_config
from app.main import create_app


@pytest.mark.integration
def test_migrations_and_readiness_require_current_schema(monkeypatch):
    url = os.environ.get("VOLLEYCREW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set VOLLEYCREW_TEST_DATABASE_URL to a dedicated PostgreSQL database")
    if not make_url(url).database.endswith("_test"):
        pytest.fail("Integration tests require a database name ending in _test")
    monkeypatch.setenv("VOLLEYCREW_DATABASE_URL", url)
    monkeypatch.setenv("VOLLEYCREW_ENV_FILE", "/nonexistent-volleycrew-test.env")
    get_settings.cache_clear()

    async def set_revision(revision):
        engine = create_async_engine(url)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("UPDATE alembic_version SET version_num=:version"), {"version": revision}
                )
        finally:
            await engine.dispose()

    try:
        command.upgrade(migration_config(), "head")
        command.upgrade(migration_config(), "head")
        with TestClient(create_app(Settings(database_url=url))) as client:
            assert client.get("/api/v1/health/ready").json() == {"status": "ready"}
            try:
                asyncio.run(set_revision("stale_schema"))
                assert client.get("/api/v1/health/ready").status_code == 503
                assert client.get("/api/v1/health/live").status_code == 200
            finally:
                asyncio.run(set_revision(expected_revision()))
            assert client.get("/api/v1/health/ready").status_code == 200
    finally:
        get_settings.cache_clear()
