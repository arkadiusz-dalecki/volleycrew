"""Real PostgreSQL tests. Destructive setup is restricted to a dedicated *_test DB."""

import asyncio
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.core.database import migration_config
from app.core.security import token_hash
from app.main import create_app
from app.models.auth import AuditEvent, Player

ORIGIN = "https://volleycrew.test"
PREFIX = "/api/v1"


class TestClock:
    __test__ = False

    def __init__(self):
        self.at = datetime.now(UTC)

    def now(self):
        return self.at


@pytest.fixture
def system(monkeypatch):
    url = os.environ.get("VOLLEYCREW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set VOLLEYCREW_TEST_DATABASE_URL")
    if not make_url(url).database.endswith("_test"):
        pytest.fail("Auth tests require a database ending in _test")
    monkeypatch.setenv("VOLLEYCREW_DATABASE_URL", url)
    monkeypatch.setenv("VOLLEYCREW_ENV_FILE", "/nonexistent-volleycrew-test.env")
    get_settings.cache_clear()
    command.upgrade(migration_config(), "head")
    clock = TestClock()

    async def prepare():
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("TRUNCATE players, bootstrap_grants, auth_throttles CASCADE")
                )
                await conn.execute(
                    text(
                        "INSERT INTO bootstrap_grants (id,token_hash,created_at,expires_at) "
                        "VALUES (1,:token,:at,:expires)"
                    ),
                    {
                        "token": token_hash("bootstrap-test-token"),
                        "at": clock.at,
                        "expires": clock.at + timedelta(minutes=30),
                    },
                )
        finally:
            await engine.dispose()

    asyncio.run(prepare())
    settings = Settings(database_url=url, public_url=ORIGIN, session_secret="test-only-key-" * 4)
    with ExitStack() as stack:

        def device():
            return stack.enter_context(TestClient(create_app(settings, clock), base_url=ORIGIN))

        yield device, clock
    get_settings.cache_clear()


def mutate(client, path, body=None, method="POST", **extra):
    csrf = client.get(PREFIX + "/auth/csrf").json()["token"]
    return client.request(
        method, PREFIX + path, json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf, **extra}
    )


def bootstrap(client):
    response = mutate(
        client,
        "/auth/bootstrap",
        {
            "token": "bootstrap-test-token",
            "first_name": "Arkadiusz",
            "last_name": "Dalecki",
            "pin": "123456",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def invitation(client):
    response = mutate(client, "/admin/invites")
    assert response.status_code == 200, response.text
    return response.json()


def register(client, token, surname="Nowak", **extras):
    return mutate(
        client,
        "/auth/register",
        {
            "token": token,
            "first_name": "Michał",
            "last_name": surname,
            "nickname": "Misiek",
            "pin": "654321",
            **extras,
        },
    )


def login(client, player, pin="654321", **headers):
    return mutate(client, "/auth/login", {"profile_id": player["id"], "pin": pin}, **headers)


def group(system):
    device, clock = system
    admin, member = device(), device()
    actor = bootstrap(admin)
    invite = invitation(admin)
    token = invite["url"].split("#")[1]
    response = register(member, token)
    assert response.status_code == 200, response.text
    return device, clock, admin, actor, member, response.json(), invite, token


def test_bootstrap_invites_privacy_and_authorization(system):
    device, _, admin, actor, member, player, invite, token = group(system)
    assert actor["role"] == "admin" and actor["priority_status"] == "founder"
    assert player["role"] == "player" and player["priority_status"] == "guest"
    anonymous = device()
    assert anonymous.get(PREFIX + "/me").status_code == 401
    assert member.get(PREFIX + "/admin/players").status_code == 403
    assert mutate(member, "/admin/invites").status_code == 403
    assert register(anonymous, token, role="admin").status_code == 422
    assert register(anonymous, token, priority_status="founder").status_code == 422
    assert (
        mutate(
            member, "/me", {"first_name": "Michał", "last_name": "Nowak", "role": "admin"}, "PATCH"
        ).status_code
        == 422
    )
    assert (
        mutate(
            anonymous,
            "/auth/bootstrap",
            {
                "token": "bootstrap-test-token",
                "first_name": "Intruz",
                "last_name": "Test",
                "pin": "123456",
            },
        ).status_code
        == 400
    )
    for surname, expected in [
        ("Ż", "Ż*****Ż"),
        ("Łą", "Ł*****ą"),
        ("Bardzodługienazwisko", "B*****o"),
    ]:
        user = device()
        response = register(user, token, surname)
        assert response.status_code == 200
        item = next(
            p
            for p in anonymous.get(PREFIX + "/auth/profiles").json()
            if p["profile_id"] == response.json()["id"]
        )
        assert item["masked_last_name"] == expected
        assert set(item) == {"profile_id", "first_name", "masked_last_name", "nickname"}
    catalogue = anonymous.get(PREFIX + "/auth/profiles")
    assert "Nowak" not in catalogue.text and "Dalecki" not in catalogue.text
    assert "priority_status" not in catalogue.text and "pin_hash" not in catalogue.text
    assert catalogue.headers["cache-control"] == "no-store"
    assert mutate(admin, f"/admin/invites/{invite['id']}/revoke").status_code == 200
    assert register(device(), token).status_code == 400
    assert member.get(PREFIX + "/me").status_code == 200
    assert login(device(), player).status_code == 200


def test_csrf_cookie_flags_and_logout(system):
    _, _, admin, _, member, player, _, _ = group(system)
    cookie = member.cookies.get("vc_session")
    csrf = member.get(PREFIX + "/auth/csrf").json()["token"]
    body = {"profile_id": player["id"], "pin": "654321"}
    for headers in [
        {},
        {"Origin": ORIGIN},
        {"Origin": "https://evil.test", "X-CSRF-Token": csrf},
        {"X-CSRF-Token": csrf},
    ]:
        assert member.post(PREFIX + "/auth/login", json=body, headers=headers).status_code == 403
    other_csrf = admin.get(PREFIX + "/auth/csrf").json()["token"]
    member.cookies.set("vc_csrf", other_csrf, domain="volleycrew.test", path="/")
    assert (
        member.post(
            PREFIX + "/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": other_csrf}
        ).status_code
        == 403
    )
    response = login(member, player)
    cookies = response.headers.get_list("set-cookie")
    session_header = next(c for c in cookies if c.startswith("vc_session="))
    assert (
        "HttpOnly" in session_header
        and "Secure" in session_header
        and "SameSite=lax" in session_header
    )
    stolen = member.cookies.get("vc_session")
    assert stolen != cookie
    assert mutate(member, "/auth/logout").status_code == 200
    member.cookies.set("vc_session", stolen, domain="volleycrew.test", path="/")
    assert member.get(PREFIX + "/me").status_code == 401


def test_rate_limit_survives_app_restart_and_ignores_forged_forwarding(system):
    device, clock, _, _, _, player, _, _ = group(system)
    for i in range(5):
        assert (
            login(device(), player, "000000", **{"X-Forwarded-For": f"192.0.2.{i}"}).status_code
            == 401
        )
    response = login(device(), player)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
    clock.at += timedelta(minutes=15)
    assert login(device(), player).status_code == 200
    invalid = login(device(), player, "１２３４５６")
    assert invalid.status_code == 422 and "１２３４５６" not in invalid.text


def test_pin_change_reset_and_block_revoke_other_devices(system):
    device, clock, admin, actor, member, player, _, _ = group(system)
    another = device()
    assert login(another, player).status_code == 200
    assert mutate(member, "/me/pin", {"current_pin": "000000", "pin": "222222"}).status_code == 401
    assert mutate(member, "/me/pin", {"current_pin": "654321", "pin": "222222"}).status_code == 200
    assert another.get(PREFIX + "/me").status_code == 401
    assert member.get(PREFIX + "/me").status_code == 200
    assert login(device(), player).status_code == 401
    assert login(another, player, "222222").status_code == 200
    reset = mutate(admin, f"/admin/players/{player['id']}/pin-reset").json()["url"].split("#")[1]
    clock.at += timedelta(minutes=30)
    assert mutate(device(), "/auth/reset-pin", {"token": reset, "pin": "333333"}).status_code == 400
    old = mutate(admin, f"/admin/players/{player['id']}/pin-reset").json()["url"].split("#")[1]
    fresh = mutate(admin, f"/admin/players/{player['id']}/pin-reset").json()["url"].split("#")[1]
    assert mutate(device(), "/auth/reset-pin", {"token": old, "pin": "333333"}).status_code == 400
    assert mutate(member, "/auth/reset-pin", {"token": fresh, "pin": "333333"}).status_code == 200
    assert mutate(device(), "/auth/reset-pin", {"token": fresh, "pin": "333333"}).status_code == 400
    assert another.get(PREFIX + "/me").status_code == 401
    assert login(another, player, "333333").status_code == 200
    preserved_cookie = another.cookies.get("vc_session")
    assert (
        mutate(admin, f"/admin/players/{actor['id']}", {"is_active": False}, "PATCH").status_code
        == 409
    )
    assert (
        mutate(admin, f"/admin/players/{player['id']}", {"is_active": False}, "PATCH").status_code
        == 200
    )
    assert member.get(PREFIX + "/me").status_code == 401
    assert another.get(PREFIX + "/me").status_code == 401
    assert login(device(), player, "333333").status_code == 401
    assert player["id"] not in str(device().get(PREFIX + "/auth/profiles").json())
    assert (
        mutate(admin, f"/admin/players/{player['id']}", {"is_active": True}, "PATCH").status_code
        == 200
    )
    another.cookies.set("vc_session", preserved_cookie, domain="volleycrew.test", path="/")
    assert another.get(PREFIX + "/me").status_code == 401
    assert login(device(), player, "333333").status_code == 200


def test_idle_and_absolute_session_expiry(system):
    device, clock, _, _, member, player, _, _ = group(system)
    clock.at += timedelta(days=29)
    assert member.get(PREFIX + "/me").status_code == 200
    clock.at += timedelta(days=30)
    assert member.get(PREFIX + "/me").status_code == 401
    assert login(member, player).status_code == 200
    for _ in range(6):
        clock.at += timedelta(days=29)
        assert member.get(PREFIX + "/me").status_code == 200
    clock.at += timedelta(days=6)
    assert member.get(PREFIX + "/me").status_code == 401
    assert login(device(), player).status_code == 200


def test_profile_and_stored_secrets(system):
    _, _, admin, _, member, player, _, token = group(system)
    response = mutate(
        member,
        "/me",
        {"first_name": "Michał", "last_name": "Nowak", "nickname": "Nowy Misiek"},
        "PATCH",
    )
    assert response.json()["id"] == player["id"]
    assert response.json()["nickname"] == "Nowy Misiek"
    assert response.json()["priority_status"] == "guest"

    async def inspect():
        async with member.app.state.database.sessions() as db:
            found = await db.get(Player, player["id"])
            assert found.pin_hash.startswith("$argon2id$")
            for table in ["auth_sessions", "invites", "pin_reset_grants", "bootstrap_grants"]:
                rows = (await db.execute(text(f"SELECT token_hash FROM {table}"))).scalars().all()
                assert all(len(value) == 64 and value != token for value in rows)
            events = (await db.scalars(select(AuditEvent))).all()
            assert events and all(
                "pin" not in str(event.details) and token not in str(event.details)
                for event in events
            )

    member.portal.call(inspect)
    assert admin.get(PREFIX + "/admin/players").status_code == 200


def test_reset_grant_is_atomic_under_concurrent_requests(system):
    device, _, admin, _, _, player, _, _ = group(system)
    token = mutate(admin, f"/admin/players/{player['id']}/pin-reset").json()["url"].split("#")[1]
    clients = [device(), device()]

    def reset(client):
        return mutate(client, "/auth/reset-pin", {"token": token, "pin": "444444"}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(reset, clients)) == [200, 400]


def test_unknown_profile_has_uniform_error(system):
    device, _ = system
    response = mutate(device(), "/auth/login", {"profile_id": str(uuid4()), "pin": "111111"})
    assert response.status_code == 401 and response.json()["code"] == "invalid_credentials"


def test_bootstrap_is_atomic_and_expires(system):
    device, clock = system
    clock.at += timedelta(minutes=30)
    response = mutate(
        device(),
        "/auth/bootstrap",
        {
            "token": "bootstrap-test-token",
            "first_name": "Arkadiusz",
            "last_name": "Dalecki",
            "pin": "123456",
        },
    )
    assert response.status_code == 400
    clock.at -= timedelta(minutes=30)
    clients = [device(), device()]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda client: (
                    mutate(
                        client,
                        "/auth/bootstrap",
                        {
                            "token": "bootstrap-test-token",
                            "first_name": "Arkadiusz",
                            "last_name": "Dalecki",
                            "pin": "123456",
                        },
                    ).status_code
                ),
                clients,
            )
        )
    assert sorted(results) == [200, 400]


def test_operator_rotates_initial_link_and_cannot_replace_admin(system):
    device, _ = system
    result = subprocess.run(
        [sys.executable, "-m", "app.manage", "create-bootstrap", "--rotate"],
        env={**os.environ, "VOLLEYCREW_PUBLIC_URL": ORIGIN},
        capture_output=True,
        text=True,
        check=True,
    )
    token = result.stdout.strip().split("#")[1]
    assert len(token) == 43
    client = device()
    body = {"first_name": "Arkadiusz", "last_name": "Dalecki", "pin": "123456"}
    assert (
        mutate(client, "/auth/bootstrap", {**body, "token": "bootstrap-test-token"}).status_code
        == 400
    )
    assert mutate(client, "/auth/bootstrap", {**body, "token": token}).status_code == 200
    closed = subprocess.run(
        [sys.executable, "-m", "app.manage", "create-bootstrap", "--rotate"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert closed.returncode != 0 and "permanently closed" in closed.stderr
