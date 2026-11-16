"""Upgrade legacy local demo credentials without overwriting existing profiles."""

from uuid import uuid5

import pytest
from sqlalchemy import func, select

from app.core.security import verify_password
from app.models.auth import Player
from app.seed_preview import DEMO_PLAYERS, PROFILES, _seed_profiles, seed
from tests import test_auth

system = test_auth.system


def test_legacy_preview_profiles_regain_credentials_and_keep_their_identity(system):
    device, clock = system
    client = device()
    real_admin = test_auth.bootstrap(client)
    admin_id, user_id = PROFILES[0][0], PROFILES[1][0]
    first, last = DEMO_PLAYERS[0]
    player_id = uuid5(admin_id, f"{first}:{last}")

    async def prepare_and_seed():
        async with client.app.state.database.sessions() as db:
            for identifier, role, priority in [
                (admin_id, "admin", "founder"),
                (user_id, "player", "player"),
                (player_id, "player", "player"),
            ]:
                db.add(
                    Player(
                        id=identifier,
                        first_name="Zachowane",
                        last_name="Nazwisko",
                        nickname="Własny przydomek",
                        role=role,
                        priority_status=priority,
                        created_at=clock.at,
                    )
                )
            await db.flush()
            await _seed_profiles(db)
            await db.commit()
            admin = await db.get(Player, admin_id)
            original_hash = admin.password_hash
            await _seed_profiles(db)
            await db.commit()
            assert admin.password_hash == original_hash
            assert admin.first_name == "Zachowane" and admin.nickname == "Własny przydomek"
            assert await db.scalar(select(func.count()).select_from(Player)) == 15
            for identifier in [admin_id, user_id, player_id]:
                profile = await db.get(Player, identifier)
                assert await verify_password(profile.password_hash, "Preview-test-password-123")
            assert (await db.get(Player, real_admin["id"])).username == "organizer"

    client.portal.call(prepare_and_seed)
    for username, role in [("admin-demo", "admin"), ("user-demo", "player")]:
        response = test_auth.mutate(
            device(), "/auth/login", {"username": username, "password": "Preview-test-password-123"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == role


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://localhost/volleycrew_test",
        "postgresql+asyncpg://production.example/volleycrew_dev",
    ],
)
async def test_preview_seed_refuses_non_development_databases(monkeypatch, url):
    from app.core.config import Settings

    monkeypatch.setattr("app.seed_preview.get_settings", lambda: Settings(database_url=url))
    with pytest.raises(SystemExit, match="loopback database ending in _dev"):
        await seed()
