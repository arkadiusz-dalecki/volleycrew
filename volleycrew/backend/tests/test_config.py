from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_database_requires_postgresql():
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///production.db")


def test_clock_is_injected_and_timezone_aware():
    moment = datetime(2026, 11, 10, 17, tzinfo=UTC)

    class FrozenClock:
        def now(self):
            return moment

    app = create_app(clock=FrozenClock())
    with TestClient(app):
        assert app.state.clock.now() == moment
        assert app.state.clock.now().tzinfo == UTC


def test_google_credentials_are_optional_and_must_be_a_pair():
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    assert not Settings().google_enabled
    assert Settings(
        google_client_id="test.apps.googleusercontent.com", google_client_secret="secret"
    ).google_enabled
    for changes in [
        {"google_client_id": "test.apps.googleusercontent.com"},
        {"google_client_secret": "secret"},
        {"google_client_id": "bad", "google_client_secret": "secret"},
    ]:
        with pytest.raises(ValidationError):
            Settings(**changes)
