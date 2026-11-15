"""Real signed Google identities, editable invite joins, and Google-only accounts."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from sqlalchemy import func, select

from app.models.auth import GoogleActionGrant, GoogleIdentity
from tests import test_auth, test_google_auth
from tests.test_auth import PREFIX, mutate

system = test_auth.system
signing = test_google_auth.signing
google = test_google_auth.google
PASSWORD = "Optional-google-password-2026"


def invitation(admin):
    return mutate(admin, "/admin/invites").json()


def pending_join(google, *, subject="new-google-subject", names=True):
    device, _, admin, _, _, _, begin, finish, _ = google
    invite = invitation(admin)
    client = device()
    claims = {"given_name": "Anna", "family_name": "Google"} if names else {}
    flow = begin(
        client,
        "register",
        invite_token=invite["url"].split("?token=")[1],
        subject=subject,
        **claims,
    )
    response = finish(client, flow)
    assert response.status_code == 303
    assert urlsplit(response.headers["location"]).path == "/join/google"
    token = urlsplit(response.headers["location"]).fragment
    assert len(token) == 43
    return client, token, invite


def complete(client, token, **extras):
    return mutate(
        client,
        "/auth/google/register",
        {
            "token": token,
            "first_name": "Anna",
            "last_name": "Poprawione",
            "nickname": "Ania",
            **extras,
        },
    )


def test_google_invite_suggests_editable_names_and_creates_guest_without_password(google):
    client, token, _ = pending_join(google)
    peek = mutate(client, "/auth/google/completion", {"token": token})
    assert peek.status_code == 200
    assert peek.json() == {"purpose": "register", "first_name": "Anna", "last_name": "Google"}
    assert client.get(PREFIX + "/me").status_code == 401  # Nothing registered before confirmation.
    response = complete(client, token)
    assert response.status_code == 200, response.text
    player = response.json()
    assert player["last_name"] == "Poprawione" and player["nickname"] == "Ania"
    assert player["role"] == "player" and player["priority_status"] == "guest"
    assert player["username"] is None and player["has_password"] is False
    assert client.get(PREFIX + "/me").json()["id"] == player["id"]
    assert "sub" not in peek.text and token not in peek.text
    assert complete(client, token).status_code == 400
    assert mutate(client, "/me/google/disconnect", {"password": PASSWORD}).status_code == 409
    assert client.get(PREFIX + "/me/google").json() == {"connected": True}
    device, _, _, _, _, _, begin, finish, _ = google
    login = device()
    assert finish(login, begin(login, subject="new-google-subject")).status_code == 303
    assert login.get(PREFIX + "/me").json()["id"] == player["id"]


def test_missing_names_are_empty_and_validation_does_not_consume_confirmation(google):
    client, token, _ = pending_join(google, names=False)
    assert mutate(client, "/auth/google/completion", {"token": token}).json()["first_name"] == ""
    assert complete(client, token, first_name="").status_code == 422
    assert complete(client, token, role="admin").status_code == 422
    assert complete(client, token, priority_status="founder").status_code == 422
    assert complete(client, token).status_code == 200


def test_confirmation_browser_binding_expiry_and_only_hashed_tokens(google):
    client, token, _ = pending_join(google)
    device, clock, *_ = google
    assert mutate(device(), "/auth/google/completion", {"token": token}).status_code == 400
    assert complete(device(), token).status_code == 400

    async def inspect():
        async with client.app.state.database.sessions() as db:
            rows = (await db.scalars(select(GoogleActionGrant))).all()
            assert len(rows) == 1 and rows[0].token_hash != token
            assert len(rows[0].token_hash) == len(rows[0].browser_hash) == 64
            assert rows[0].subject == "new-google-subject"

    client.portal.call(inspect)
    clock.at += timedelta(minutes=10)
    assert complete(client, token).status_code == 400


@pytest.mark.parametrize("stage", ["start", "callback", "confirmation"])
def test_revoked_invite_cannot_register_at_any_stage(google, stage):
    device, _, admin, _, _, _, begin, finish, _ = google
    invite = invitation(admin)
    token = invite["url"].split("?token=")[1]
    client = device()
    if stage == "start":
        mutate(admin, f"/admin/invites/{invite['id']}/revoke")
        assert (
            mutate(
                client, "/auth/google/start", {"mode": "register", "invite_token": token}
            ).status_code
            == 400
        )
        return
    flow = begin(client, "register", invite_token=token, subject="revoked-subject")
    if stage == "callback":
        mutate(admin, f"/admin/invites/{invite['id']}/revoke")
        assert finish(client, flow).headers["location"].endswith("#google=invite")
    else:
        response = finish(client, flow)
        pending = urlsplit(response.headers["location"]).fragment
        assert mutate(client, "/auth/google/completion", {"token": pending}).status_code == 200
        mutate(admin, f"/admin/invites/{invite['id']}/revoke")
        assert complete(client, pending).status_code == 400
    assert client.get(PREFIX + "/me").status_code == 401


def test_concurrent_google_joins_never_duplicate_or_overwrite_profile(google):
    first, first_token, _ = pending_join(google)
    second, second_token, _ = pending_join(google)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda pair: complete(*pair), [(first, first_token), (second, second_token)])
        )
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json()["id"] == responses[1].json()["id"]

    async def count():
        async with first.app.state.database.sessions() as db:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(GoogleIdentity)
                    .where(GoogleIdentity.subject == "new-google-subject")
                )
                == 1
            )

    first.portal.call(count)
    # Starting another invite flow with an already registered subject logs into the same account.
    device, _, admin, _, _, _, begin, finish, _ = google
    invite = invitation(admin)["url"].split("?token=")[1]
    another = device()
    result = finish(
        another,
        begin(
            another,
            "register",
            invite_token=invite,
            subject="new-google-subject",
            given_name="Intruder",
        ),
    )
    assert urlsplit(result.headers["location"]).path == "/"
    assert another.get(PREFIX + "/me").json()["first_name"] == "Anna"


def password_proof(google):
    client, token, _ = pending_join(google)
    player = complete(client, token).json()
    *_, begin, finish, _ = google
    response = finish(client, begin(client, "password", subject="new-google-subject"))
    assert urlsplit(response.headers["location"]).path == "/profile/password"
    return client, player, urlsplit(response.headers["location"]).fragment


def test_google_only_can_add_password_after_same_google_proof_then_disconnect(google):
    client, player, token = password_proof(google)
    body = {"token": token, "username": "new-local-login", "password": PASSWORD}
    assert (
        mutate(client, "/auth/google/completion", {"token": token}).json()["purpose"] == "password"
    )
    response = mutate(client, "/me/google/password", body)
    assert response.status_code == 200 and response.json()["has_password"] is True
    assert response.json()["id"] == player["id"]
    assert mutate(client, "/me/google/password", body).status_code == 400
    assert mutate(client, "/me/google/disconnect", {"password": PASSWORD}).status_code == 200
    device, *_ = google
    assert (
        mutate(
            device(), "/auth/login", {"username": "new-local-login", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_wrong_google_cannot_add_credentials_and_old_session_proof_is_rejected(google):
    client, token, _ = pending_join(google)
    player = complete(client, token).json()
    device, _, admin, _, _, _, begin, finish, _ = google
    mismatch = finish(client, begin(client, "password", subject="another-account"))
    assert mismatch.headers["location"].endswith("#google=conflict")
    response = finish(client, begin(client, "password", subject="new-google-subject"))
    token = urlsplit(response.headers["location"]).fragment
    mutate(client, "/auth/logout")
    assert (
        mutate(
            client,
            "/me/google/password",
            {"token": token, "username": "stolen-login", "password": PASSWORD},
        ).status_code
        == 401
    )
    reset = (
        mutate(admin, f"/admin/players/{player['id']}/password-reset").json()["url"].split("#")[1]
    )
    recovered = device()
    assert (
        mutate(
            recovered,
            "/auth/reset-password",
            {"token": reset, "username": "recovered", "password": PASSWORD},
        ).status_code
        == 200
    )
    assert recovered.get(PREFIX + "/me/google").json() == {"connected": False}
