"""Private credentials, uniqueness, and sole-organizer password setup."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from alembic import command
from pydantic import ValidationError
from sqlalchemy import func, select

from app.api.auth_schemas import Login, Registration
from app.core.database import migration_config
from app.core.security import token_hash, verify_password
from app.models.auth import BootstrapGrant, Player
from app.runtime import bootstrap as runtime_bootstrap
from tests import test_auth

system = test_auth.system
mutate, group, login, register = (
    test_auth.mutate,
    test_auth.group,
    test_auth.login,
    test_auth.register,
)
PREFIX = test_auth.PREFIX
PASSWORD = "Długa fraza na siatkówkę 2026"


@pytest.mark.parametrize(
    "username", ["ab", "x" * 33, "żółw", "user name", "a/b", "a@b.pl", "_abc", "a\nfoo"]
)
def test_invalid_usernames(username):
    with pytest.raises(ValidationError):
        Login(username=username, password=PASSWORD)


@pytest.mark.parametrize("password", ["123456", "short password", "x" * 129])
def test_new_password_length(password):
    with pytest.raises(ValidationError):
        Registration(
            username="valid-user", password=password, first_name="A", last_name="B", token="secret"
        )


def test_whitespace_unicode_case_and_private_credentials(system):
    device, _, _, _, _, _, _, token = group(system)
    password = "  Siatkówka i pełne spacje!  "
    member = device()
    response = register(member, token, username="  MY.Player  ", password=password)
    assert response.status_code == 200, response.text
    player = response.json()
    assert player["username"] == "my.player"
    assert login(device(), player, password).status_code == 200
    assert login(device(), player, password.strip()).status_code == 401
    assert login(device(), player, password.replace("ó", "o\u0301")).status_code == 401
    assert (
        mutate(device(), "/auth/login", {"username": "MY.PLAYER", "password": password}).status_code
        == 200
    )

    async def inspect():
        async with member.app.state.database.sessions() as db:
            stored = await db.get(Player, player["id"])
            assert stored.password_hash.startswith("$argon2id$")
            assert password not in stored.password_hash
            assert await verify_password(stored.password_hash, password)

    member.portal.call(inspect)
    catalogue = member.get(PREFIX + "/players")
    assert catalogue.status_code == 200
    assert "my.player" not in catalogue.text and "password" not in catalogue.text


def test_username_collision_is_atomic_case_insensitive_and_keeps_invitation(system):
    device, _, _, _, _, _, _, token = group(system)
    clients = [device(), device()]

    def claim(item):
        index, client = item
        return register(client, token, username=["Unique.Name", "unique.name"][index]).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, enumerate(clients))) == [200, 409]
    assert register(device(), token, username="another-name").status_code == 200


def test_uniform_login_errors_limits_and_removed_pin_routes(system):
    device, clock, admin, _, _, player, _, _ = group(system)
    wrong = {"username": player["username"], "password": "wrong"}
    unknown = {"username": "not-an-account", "password": "wrong"}
    assert (
        mutate(device(), "/auth/login", wrong).json()
        == mutate(device(), "/auth/login", unknown).json()
    )
    for _ in range(4):
        assert (
            mutate(
                device(), "/auth/login", {**wrong, "username": player["username"].upper()}
            ).status_code
            == 401
        )
    assert login(device(), player).status_code == 429
    clock.at += timedelta(minutes=15)
    assert login(device(), player).status_code == 200
    assert (
        mutate(admin, f"/admin/players/{player['id']}", {"is_active": False}, "PATCH").status_code
        == 200
    )
    assert login(device(), player).json() == mutate(device(), "/auth/login", unknown).json()
    assert device().get(PREFIX + "/auth/profiles").status_code == 404
    assert (
        mutate(device(), "/auth/login", {"profile_id": player["id"], "pin": "654321"}).status_code
        == 422
    )
    assert mutate(device(), "/auth/reset-pin", {}).status_code == 404
    assert mutate(admin, "/me/pin", {}).status_code == 404
    invalid = register(device(), "bad-token", password="tiny-secret")
    assert invalid.status_code == 422 and "tiny-secret" not in invalid.text


def test_reset_recovers_username_and_keeps_grant_on_collision(system):
    device, _, admin, actor, member, player, _, _ = group(system)
    reset = (
        mutate(admin, f"/admin/players/{player['id']}/password-reset").json()["url"].split("#")[1]
    )
    body = {"token": reset, "username": actor["username"].upper(), "password": PASSWORD}
    assert mutate(device(), "/auth/reset-password", body).status_code == 409
    changed = mutate(device(), "/auth/reset-password", {**body, "username": "recovered-member"})
    assert changed.status_code == 200 and changed.json()["id"] == player["id"]
    assert member.get(PREFIX + "/me").status_code == 401
    assert login(device(), player).status_code == 401
    assert (
        mutate(
            device(), "/auth/login", {"username": "recovered-member", "password": PASSWORD}
        ).status_code
        == 200
    )
    assert (
        mutate(
            device(), "/auth/reset-password", {**body, "username": "recovered-member"}
        ).status_code
        == 400
    )


def test_upgrade_keeps_organizer_and_requires_fresh_operator_setup(system):
    device, _ = system
    owner = device()
    actor = test_auth.bootstrap(owner)
    command.downgrade(migration_config(), "0011_google_login")
    command.upgrade(migration_config(), "head")
    assert owner.get(PREFIX + "/me").status_code == 401
    assert login(device(), actor, "123456").status_code == 401
    fresh = "fresh-operator-setup-token-at-least-32-characters"

    async def prepare():
        database = owner.app.state.database
        await runtime_bootstrap(database, "bootstrap-test-token")
        async with database.sessions() as db:
            grant = await db.get(BootstrapGrant, 1)
            assert grant.used_at is not None
            player = await db.get(Player, actor["id"])
            assert player.username is None and player.password_hash is None
            assert await db.scalar(select(func.count()).select_from(Player)) == 1
        await runtime_bootstrap(database, fresh)
        async with database.sessions() as db:
            grant = await db.get(BootstrapGrant, 1)
            assert grant.token_hash == token_hash(fresh) and grant.used_at is None

    owner.portal.call(prepare)
    body = {
        "token": fresh,
        "username": "my-new-login",
        "password": PASSWORD,
        "first_name": "Ignored",
        "last_name": "Ignored",
    }
    response = mutate(device(), "/auth/bootstrap", body)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == actor["id"]
    assert response.json()["first_name"] == actor["first_name"]
    assert response.json()["role"] == "admin" and response.json()["priority_status"] == "founder"
    assert mutate(device(), "/auth/bootstrap", body).status_code == 400
    assert (
        mutate(
            device(), "/auth/login", {"username": "my-new-login", "password": PASSWORD}
        ).status_code
        == 200
    )
    owner.portal.call(runtime_bootstrap, owner.app.state.database, "another-new-token")
    assert (
        mutate(device(), "/auth/bootstrap", {**body, "token": "another-new-token"}).status_code
        == 400
    )
