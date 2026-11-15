"""Real PostgreSQL + signed OIDC tokens, with only Google's HTTPS transport substituted."""

import base64
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr
from sqlalchemy import func, select

from app.models.auth import GoogleFlow, GoogleIdentity
from app.services.google_provider import GoogleProvider, GoogleRejected
from tests import test_auth
from tests.test_auth import ORIGIN, PREFIX, group, login, mutate

system = test_auth.system

CLIENT = "isolated-client.apps.googleusercontent.com"
SECRET = "isolated-google-client-secret"


@pytest.fixture(scope="module")
def signing():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key", alg="RS256", use="sig")
    return key, jwk


@pytest.fixture
def google(system, signing):
    device, clock, admin, actor, member, player, invite, token = group(system)
    codes, exchanges = {}, []

    def transport(request):
        if request.url.path == "/oauth2/v3/certs":
            return httpx.Response(200, json={"keys": [signing[1]]})
        assert str(request.url) == "https://oauth2.googleapis.com/token"
        body = parse_qs(request.content.decode())
        assert body["client_id"] == [CLIENT]
        assert body["client_secret"] == [SECRET]
        assert body["redirect_uri"] == [ORIGIN + "/api/v1/auth/google/callback"]
        assert body["grant_type"] == ["authorization_code"]
        code = body["code"][0]
        exchanges.append(code)
        data = codes.get(code)
        if not data:
            return httpx.Response(400, json={"error": "invalid_grant"})
        claims, challenge = data
        verifier = body["code_verifier"][0]
        assert (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
            == challenge
        )
        encoded = jwt.encode(claims, signing[0], algorithm="RS256", headers={"kid": "test-key"})
        return httpx.Response(
            200, json={"id_token": encoded, "token_type": "Bearer", "access_token": "discarded"}
        )

    def enable(client):
        settings = client.app.state.settings
        settings.google_client_id = CLIENT
        settings.google_client_secret = SecretStr(SECRET)
        client.app.state.google_provider = GoogleProvider(
            settings, client.app.state.auth_key, httpx.MockTransport(transport)
        )
        return client

    enable(admin)
    enable(member)

    def new_device():
        return enable(device())

    def begin(
        client, mode="login", password=None, subject="google-subject-1", return_to="/", **claims
    ):
        body = {"mode": mode, "return_to": return_to}
        if password is not None:
            body["password"] = password
        response = mutate(client, "/auth/google/start", body)
        assert response.status_code == 200, response.text
        query = parse_qs(urlsplit(response.json()["url"]).query)
        assert query["scope"] == ["openid"]
        assert query["code_challenge_method"] == ["S256"]
        assert query["prompt"] == ["select_account"]
        assert query["redirect_uri"] == [ORIGIN + "/api/v1/auth/google/callback"]
        code = str(uuid4())
        codes[code] = (
            {
                "iss": "https://accounts.google.com",
                "aud": CLIENT,
                "sub": subject,
                "nonce": query["nonce"][0],
                "iat": int(time.time()),
                "exp": int(time.time()) + 600,
                **claims,
            },
            query["code_challenge"][0],
        )
        return {"state": query["state"][0], "code": code}

    def finish(client, parameters):
        return client.get(
            PREFIX + "/auth/google/callback", params=parameters, follow_redirects=False
        )

    return new_device, clock, admin, actor, member, player, begin, finish, exchanges


def test_link_login_disconnect_and_no_automatic_registration(google):
    device, _, admin, _, member, player, begin, finish, _ = google
    anonymous = device()
    initial = begin(anonymous)
    assert finish(anonymous, initial).headers["location"].endswith("#google=unlinked")
    assert anonymous.get(PREFIX + "/me").status_code == 401
    flow = begin(member, "link", "Player-test-passphrase-456")
    assert finish(member, flow).headers["location"] == ORIGIN + "/profile#google=linked"
    assert member.get(PREFIX + "/me/google").json() == {"connected": True}
    other = device()
    assert finish(other, begin(other)).headers["location"] == ORIGIN + "/"
    assert other.get(PREFIX + "/me").json()["id"] == player["id"]
    assert other.get(PREFIX + "/admin/players").status_code == 403
    assert (
        mutate(
            member, "/me/google/disconnect", {"password": "Wrong-test-passphrase-000"}
        ).status_code
        == 401
    )
    assert (
        mutate(
            member, "/me/google/disconnect", {"password": "Player-test-passphrase-456"}
        ).status_code
        == 200
    )
    assert other.get(PREFIX + "/me").status_code == 401
    assert member.get(PREFIX + "/me").status_code == 200
    assert member.get(PREFIX + "/me/google").json() == {"connected": False}
    fresh = device()
    assert finish(fresh, begin(fresh)).headers["location"].endswith("#google=unlinked")
    assert login(fresh, player).status_code == 200
    assert len(admin.get(PREFIX + "/admin/players").json()) == 2


def test_link_requires_password_session_and_post_csrf(google):
    device, _, _, _, member, _, _, _, _ = google
    assert (
        mutate(
            device(),
            "/auth/google/start",
            {"mode": "link", "password": "Player-test-passphrase-456"},
        ).status_code
        == 401
    )
    assert mutate(member, "/auth/google/start", {"mode": "link"}).status_code == 422
    assert (
        mutate(
            member, "/auth/google/start", {"mode": "link", "password": "Wrong-test-passphrase-000"}
        ).status_code
        == 401
    )
    assert member.post(PREFIX + "/auth/google/start", json={"mode": "login"}).status_code == 403


def test_state_browser_binding_expiry_and_replay(google):
    device, clock, _, _, member, _, begin, finish, exchanges = google
    flow = begin(member, "link", "Player-test-passphrase-456")
    assert finish(device(), flow).headers["location"].endswith("#google=invalid")
    assert not exchanges
    assert (
        finish(member, {**flow, "state": "x" * 43}).headers["location"].endswith("#google=invalid")
    )
    assert not exchanges
    assert finish(member, flow).headers["location"].endswith("#google=linked")
    assert finish(member, flow).headers["location"].endswith("#google=invalid")
    assert len(exchanges) == 1
    new = device()
    expired = begin(new)
    clock.at += timedelta(minutes=10)
    assert finish(new, expired).headers["location"].endswith("#google=invalid")
    assert len(exchanges) == 1


def test_link_cannot_survive_logout_or_password_reset(google):
    device, _, admin, _, member, player, begin, finish, _ = google
    flow = begin(member, "link", "Player-test-passphrase-456")
    assert mutate(member, "/auth/logout").status_code == 200
    assert finish(member, flow).headers["location"].endswith("#google=session")
    assert login(member, player).status_code == 200
    flow = begin(member, "link", "Player-test-passphrase-456")
    grant = (
        mutate(admin, f"/admin/players/{player['id']}/password-reset").json()["url"].split("#")[1]
    )
    assert (
        mutate(
            device(),
            "/auth/reset-password",
            {
                "token": grant,
                "username": player["username"],
                "password": "Other-test-passphrase-333",
            },
        ).status_code
        == 200
    )
    assert finish(member, flow).headers["location"].endswith("#google=session")


def test_subject_uniqueness_and_blocked_player(google):
    device, _, admin, _, member, player, begin, finish, _ = google
    assert (
        finish(member, begin(member, "link", "Player-test-passphrase-456"))
        .headers["location"]
        .endswith("#google=linked")
    )
    assert (
        finish(admin, begin(admin, "link", "Admin-test-passphrase-123"))
        .headers["location"]
        .endswith("#google=conflict")
    )
    assert (
        mutate(admin, f"/admin/players/{player['id']}", {"is_active": False}, "PATCH").status_code
        == 200
    )
    client = device()
    assert finish(client, begin(client)).headers["location"].endswith("#google=unlinked")
    assert client.get(PREFIX + "/me").status_code == 401


def test_cancel_provider_failure_and_new_flow_invalidates_previous(google):
    device, _, _, _, member, _, begin, finish, exchanges = google
    old = begin(member, "link", "Player-test-passphrase-456")
    new = begin(member, "link", "Player-test-passphrase-456")
    assert finish(member, old).headers["location"].endswith("#google=invalid")
    assert (
        finish(member, {"state": new["state"], "error": "access_denied"})
        .headers["location"]
        .endswith("#google=cancelled")
    )
    assert not exchanges
    client = device()
    flow = begin(client)
    assert (
        finish(client, {**flow, "code": "rejected-code"})
        .headers["location"]
        .endswith("#google=unavailable")
    )
    assert finish(client, flow).headers["location"].endswith("#google=invalid")


@pytest.mark.parametrize(
    "claim,value",
    [
        ("iss", "https://attacker.invalid"),
        ("aud", "another-client"),
        ("exp", 1),
        ("nonce", "wrong-nonce"),
        ("azp", "another-client"),
        ("sub", ""),
    ],
)
def test_invalid_signed_claims_cannot_link(google, claim, value):
    _, _, _, _, member, _, begin, finish, _ = google
    flow = begin(member, "link", "Player-test-passphrase-456", **{claim: value})
    assert finish(member, flow).headers["location"].endswith("#google=invalid")
    assert member.get(PREFIX + "/me/google").json() == {"connected": False}


def test_concurrent_callback_is_used_once(google):
    _, _, _, _, member, _, begin, finish, exchanges = google
    flow = begin(member, "link", "Player-test-passphrase-456")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: finish(member, flow).headers["location"], range(2)))
    assert sum(url.endswith("#google=linked") for url in results) == 1
    assert len(exchanges) == 1


def test_flow_does_not_store_codes_secrets_or_raw_state(google):
    _, _, _, _, member, _, begin, _, _ = google
    params = begin(member, "link", "Player-test-passphrase-456")

    async def inspect():
        async with member.app.state.database.sessions() as db:
            flow = (await db.scalars(select(GoogleFlow))).one()
            assert params["state"] not in str(vars(flow))
            assert params["code"] not in str(vars(flow))
            assert SECRET not in str(vars(flow))
            assert await db.scalar(select(func.count()).select_from(GoogleIdentity)) == 0

    member.portal.call(inspect)


@pytest.mark.asyncio
async def test_verifier_rejects_bad_signature_and_algorithms(signing):
    from app.core.config import Settings
    from app.core.security import token_hash

    provider = GoogleProvider(
        Settings(google_client_id=CLIENT, google_client_secret=SECRET), b"key"
    )

    async def keys(_):
        return [signing[1]]

    provider.keys = keys
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT,
        "sub": "subject",
        "nonce": "nonce",
        "exp": int(time.time()) + 100,
        "iat": int(time.time()),
    }
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encoded = jwt.encode(claims, other_key, algorithm="RS256", headers={"kid": "test-key"})
    with pytest.raises(GoogleRejected):
        await provider.verify(encoded, token_hash("nonce"))
    encoded = jwt.encode(claims, "a" * 32, algorithm="HS256", headers={"kid": "test-key"})
    with pytest.raises(GoogleRejected):
        await provider.verify(encoded, token_hash("nonce"))


def test_organizer_password_recovery_removes_existing_google_link(google):
    device, _, admin, _, member, player, begin, finish, _ = google
    assert (
        finish(member, begin(member, "link", "Player-test-passphrase-456"))
        .headers["location"]
        .endswith("#google=linked")
    )
    reset = (
        mutate(admin, f"/admin/players/{player['id']}/password-reset").json()["url"].split("#")[1]
    )
    recovered = device()
    assert (
        mutate(
            recovered,
            "/auth/reset-password",
            {
                "token": reset,
                "username": player["username"],
                "password": "Other-test-passphrase-333",
            },
        ).status_code
        == 200
    )
    assert recovered.get(PREFIX + "/me/google").json() == {"connected": False}
    anonymous = device()
    assert finish(anonymous, begin(anonymous)).headers["location"].endswith("#google=unlinked")


def test_return_destination_is_internal_and_link_cookie_flags(google):
    device, _, _, _, member, _, begin, finish, _ = google
    assert (
        finish(member, begin(member, "link", "Player-test-passphrase-456"))
        .headers["location"]
        .endswith("#google=linked")
    )
    client = device()
    for target in [
        "//attacker.test",
        "https://attacker.test",
        "/\\attacker",
        "/api/v1/auth/google/callback",
        "/profile#secret",
    ]:
        assert mutate(client, "/auth/google/start", {"return_to": target}).status_code == 422
    result = mutate(client, "/auth/google/start", {"return_to": "/calendar?month=2026-12"})
    assert result.status_code == 200
    cookie = next(
        c for c in result.headers.get_list("set-cookie") if c.startswith("__Host-vc_google_flow=")
    )
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    assert "Path=/" in cookie and "Domain=" not in cookie
    flow = begin(client, return_to="/calendar?month=2026-12")
    assert finish(client, flow).headers["location"] == ORIGIN + "/calendar?month=2026-12"


def test_pending_flow_survives_api_restart_with_same_persistent_key(google):
    device, _, _, _, member, _, begin, finish, _ = google
    parameters = begin(member, "link", "Player-test-passphrase-456")
    restarted = device()
    for cookie in member.cookies.jar:
        restarted.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
    assert finish(restarted, parameters).headers["location"].endswith("#google=linked")


def test_disabled_google_preserves_password_login_and_exposes_no_secrets(system):
    device, _ = system
    client = device()
    assert client.get(PREFIX + "/auth/google/config").json() == {
        "enabled": False,
        "public_url": ORIGIN,
    }
    assert mutate(client, "/auth/google/start", {"mode": "login"}).status_code == 503
    response = client.get(
        PREFIX + "/auth/google/callback?state=fake&code=fake", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == ORIGIN + "/login#google=unavailable"


def test_ingress_cannot_start_or_finish_a_public_google_flow(google):
    from fastapi.testclient import TestClient

    from app.main import create_app

    _, clock, admin, _, _, _, _, _, _ = google
    settings = admin.app.state.settings.model_copy(update={"behind_proxy": True})
    prefix = "/api/hassio_ingress/test-google"
    headers = {"X-Volleycrew-Base": prefix, "Origin": ORIGIN}
    with TestClient(
        create_app(settings, clock), base_url=ORIGIN, client=("127.0.0.1", 1234)
    ) as client:
        csrf = client.get(PREFIX + "/auth/csrf", headers=headers).json()["token"]
        response = client.post(
            PREFIX + "/auth/google/start",
            json={"mode": "login"},
            headers={
                **headers,
                "X-CSRF-Token": csrf,
                "Cookie": f"vc_csrf_ingress={csrf}",
            },
        )
        assert response.status_code == 409
        assert response.json()["code"] == "google_public_url"
        response = client.get(
            PREFIX + "/auth/google/callback?state=fake&code=fake",
            headers=headers,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == ORIGIN + "/login#google=unavailable"


def test_google_flow_outcome_logs_never_include_provider_secrets(google, caplog):
    _, _, _, _, member, _, begin, finish, _ = google
    with caplog.at_level("INFO", logger="volleycrew.security"):
        flow = begin(member, "link", "Player-test-passphrase-456")
        assert finish(member, flow).headers["location"].endswith("#google=linked")
    for secret in [flow["state"], flow["code"], SECRET, "google-subject-1", "discarded"]:
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_jwks_respects_short_cache_lifetime_and_rotates_keys(signing):
    from app.core.config import Settings

    at, calls = [0], []

    def transport(request):
        calls.append(str(request.url))
        key = {**signing[1], "kid": "first" if len(calls) == 1 else "second"}
        return httpx.Response(
            200, json={"keys": [key]}, headers={"Cache-Control": "public, max-age=10"}
        )

    provider = GoogleProvider(
        Settings(google_client_id=CLIENT, google_client_secret=SECRET),
        b"key",
        httpx.MockTransport(transport),
        timer=lambda: at[0],
    )
    assert (await provider.keys("first"))[0]["kid"] == "first"
    at[0] = 5
    await provider.keys("first")
    await provider.keys("unknown")
    assert len(calls) == 1
    at[0] = 11
    assert (await provider.keys("second"))[0]["kid"] == "second"
    assert len(calls) == 2


def test_migration_round_trip_preserves_profiles_and_requires_password_setup(google):
    from alembic import command

    from app.core.database import migration_config

    device, _, _, _, member, player, begin, finish, _ = google
    finish(member, begin(member, "link", "Player-test-passphrase-456"))
    command.downgrade(migration_config(), "0010_preliminary_teams")
    command.upgrade(migration_config(), "head")
    assert member.get(PREFIX + "/me").status_code == 401
    assert member.get(PREFIX + "/me/google").status_code == 401
    assert login(device(), player).status_code == 401
