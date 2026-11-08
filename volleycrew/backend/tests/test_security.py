from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings
from app.core.security import csrf_token, load_auth_key, source_address, valid_csrf


def test_persistent_signing_key_and_csrf_session_binding(tmp_path):
    settings = Settings(state_dir=tmp_path)
    key = load_auth_key(settings)
    assert key == load_auth_key(settings)
    assert (tmp_path / "auth.key").stat().st_mode & 0o777 == 0o600
    at = datetime.now(UTC)
    token = csrf_token(key, "session-a", at)
    assert valid_csrf(token, key, "session-a", at)
    assert not valid_csrf(token, key, "session-b", at)
    assert not valid_csrf(token, key, "session-a", at + timedelta(days=1))
    assert not valid_csrf("broken", key, "session-a", at)


def test_proxy_chain_requires_explicit_trust():
    def address(peer, chain, networks):
        app = SimpleNamespace(
            state=SimpleNamespace(settings=Settings(trusted_proxy_cidrs=networks))
        )
        return source_address(
            Request(
                {
                    "type": "http",
                    "client": (peer, 1234),
                    "app": app,
                    "headers": [(b"x-forwarded-for", chain.encode())],
                }
            )
        )

    assert address("192.0.2.5", "1.1.1.1", []) == "192.0.2.5"
    assert address("127.0.0.1", "1.1.1.1, 192.0.2.5", ["127.0.0.1/32"]) == "192.0.2.5"
    assert (
        address("127.0.0.1", "192.0.2.5, 10.0.0.1", ["127.0.0.1/32", "10.0.0.0/24"]) == "192.0.2.5"
    )
    assert address("127.0.0.1", "invalid", ["127.0.0.1/32"]) == "127.0.0.1"


def test_external_deployment_requires_https_and_secure_cookies():
    with pytest.raises(ValidationError):
        Settings(public_url="http://volleycrew.example")
    with pytest.raises(ValidationError):
        Settings(public_url="https://volleycrew.example", cookie_secure=False)
    with pytest.raises(ValidationError):
        Settings(session_secret="short")
