"""The packaged signup fixture must remain valid during an ongoing game."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.test_auth import mutate
from tests.test_auth import system as system
from tests.test_meetings import calendar_system as calendar_system

spec = importlib.util.spec_from_file_location(
    "packaged_smoke", Path(__file__).resolve().parents[3] / "scripts/test_container.py"
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.mark.parametrize("hour", [16, 17, 18, 19])
def test_signup_fixture_skips_todays_meeting_even_while_it_is_next(calendar_system, hour):
    # Warsaw Tuesday 18:00 = 17:00 UTC; test before, at, during and after start.
    from tests.test_enrollment import declaration, setup_group

    _, clock, admin, _, _, _, _, _ = setup_group(calendar_system, 0)
    clock.at = datetime(2026, 11, 10, hour, 14, tzinfo=UTC)

    class Client:
        def call(self, path):
            result = admin.get(path)
            return result.status_code, result.json(), result.headers

    upcoming = admin.get("/api/v1/meetings/next").json()
    selected = smoke.signup_occurrence(Client(), clock.at)
    assert selected["source_date"] == "2026-11-17"
    assert datetime.fromisoformat(selected["starts_at"]) > clock.at
    if hour < 19:
        assert upcoming["source_date"] == "2026-11-10"
    resolved = mutate(
        admin,
        "/meetings/resolve",
        {
            "schedule_version_id": selected["schedule_version_id"],
            "source_date": selected["source_date"],
        },
    )
    assert resolved.status_code == 200, resolved.text
    meeting = resolved.json()
    declared = declaration(admin, meeting)
    assert declared.status_code == 200, declared.text
