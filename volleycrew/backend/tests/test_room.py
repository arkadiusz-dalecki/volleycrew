from datetime import datetime, timedelta
from random import Random
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.domain.teams import split_teams, validate_teams
from app.models.meetings import Meeting
from tests.test_auth import PREFIX, mutate
from tests.test_auth import system as system
from tests.test_enrollment import as_player, counts, declaration, setup_group
from tests.test_meetings import calendar_system as calendar_system
from tests.test_schedule_changes import fresh, move


def read(admin, meeting):
    response = admin.get(PREFIX + f"/admin/meetings/{meeting['id']}/attendance")
    assert response.status_code == 200, response.text
    return response.json()


def change(admin, meeting, path, fields=None, method="POST", key=None, version=None):
    return mutate(
        admin,
        f"/admin/meetings/{meeting['id']}/{path}",
        {"expected_version": version or fresh(admin, meeting)["version"], **(fields or {})},
        method,
        **{"Idempotency-Key": str(key or uuid4())},
    )


def draft(admin, meeting, absent=()):
    return change(
        admin,
        meeting,
        "attendance",
        {
            "players": [
                {
                    "player_id": p["player"]["id"],
                    "state": "absent" if p["player"]["id"] in absent else "present",
                }
                for p in read(admin, meeting)["players"]
            ]
        },
        "PUT",
    )


def start(clock, meeting):
    clock.at = datetime.fromisoformat(meeting["starts_at"].replace("Z", "+00:00"))


def confirm(admin, meeting):
    response = change(admin, meeting, "attendance/confirm")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("size", [2, 3, 11, 12, 13, 14])
def test_team_modes(size):
    ratings = {UUID(int=i + 1): 900 + i * 37 for i in range(size)}
    a, b = split_teams(ratings, "random", Random(42))
    assert (a, b) == split_teams(ratings, "random", Random(42))
    validate_teams(list(ratings), a, b)
    balanced = split_teams(ratings, "balanced")
    validate_teams(list(ratings), *balanced)

    def mean_diff(sides):
        return abs(
            sum(ratings[p] for p in sides[0]) / len(sides[0])
            - sum(ratings[p] for p in sides[1]) / len(sides[1])
        )

    assert mean_diff(balanced) <= mean_diff((a, b))
    assert balanced == split_teams(ratings, "balanced")
    with pytest.raises(ValueError):
        validate_teams(list(ratings), a + [b[0]], b)


@pytest.mark.parametrize("size", [0, 1, 15])
def test_invalid_sizes(size):
    with pytest.raises(ValueError):
        split_teams({UUID(int=i + 1): 1000 for i in range(size)}, "random")


def test_draft_confirm_history_privacy_and_retry(calendar_system):
    device, clock, admin, actor, member, _, meeting, ids = setup_group(calendar_system, 3)
    absent = as_player(device, ids[2])
    assert draft(admin, meeting, [ids[2]]).status_code == 200
    assert absent.get(PREFIX + "/me/attendance-history").json()["total"] == 0
    assert change(admin, meeting, "attendance/confirm").status_code == 409
    assert member.get(PREFIX + f"/admin/meetings/{meeting['id']}/attendance").status_code == 403
    start(clock, meeting)
    key, version = uuid4(), fresh(admin, meeting)["version"]
    result = change(admin, meeting, "attendance/confirm", key=key, version=version)
    assert result.status_code == 200, result.text
    assert change(admin, meeting, "attendance/confirm", key=key, version=version).status_code == 200
    history = absent.get(PREFIX + "/me/attendance-history").json()
    assert history["total"] == 1 and history["items"][0]["current_kind"] == "no_show"
    assert history["items"][0]["actor"]["id"] == actor["id"]
    assert member.get(PREFIX + f"/admin/players/{ids[2]}/attendance-history").status_code == 403
    assert counts(admin, meeting) == (2, 0, 0, 12)
    assert change(admin, meeting, "attendance/confirm").status_code == 409
    correction = {
        "event_id": history["items"][0]["id"],
        "value": "excused",
        "reason": "Uraz przed wyjściem",
    }
    assert (
        change(admin, meeting, "attendance/corrections", {**correction, "reason": "  "}).status_code
        == 422
    )
    assert change(admin, meeting, "attendance/corrections", correction).status_code == 200
    updated = absent.get(PREFIX + "/me/attendance-history").json()["items"][0]
    assert updated["original_kind"] == "no_show" and updated["current_kind"] == "excused"
    assert updated["corrections"][0]["reason"] == correction["reason"]
    assert "no_show" not in member.get(PREFIX + f"/meetings/{meeting['id']}").text
    assert member.get(PREFIX + "/me/attendance-history").json()["total"] == 0


def test_no_show_releases_to_waitlist_and_cannot_steal_reservation(calendar_system):
    device, clock, admin, _, member, _, meeting, ids = setup_group(calendar_system)
    waiting = as_player(device, ids[14])
    assert declaration(waiting, meeting).status_code == 200
    assert draft(admin, meeting, [ids[0]]).status_code == 200
    start(clock, meeting)
    view = confirm(admin, meeting)
    assert counts(admin, meeting) == (13, 1, 1, 0)
    source = next(p["event_id"] for p in view["players"] if p["player"]["id"] == ids[0])
    correction = {"event_id": source, "value": "present", "reason": "Dotarł później"}
    assert change(admin, meeting, "attendance/corrections", correction).status_code == 409
    assert change(admin, meeting, "attendance/admit", {"player_id": ids[15]}).status_code == 409
    admitted = change(admin, meeting, "attendance/admit", {"player_id": ids[14]})
    assert admitted.status_code == 200, admitted.text
    assert counts(admin, meeting) == (14, 0, 0, 0)
    assert (
        waiting.get(PREFIX + "/me/attendance-history").json()["items"][0]["current_kind"]
        == "present"
    )
    assert member.get(PREFIX + f"/meetings/{meeting['id']}/teams").json() is None


@pytest.mark.parametrize("size", [11, 12, 13, 14])
def test_team_lifecycle_swap_and_corrections(calendar_system, size):
    device, clock, admin, _, member, _, meeting, ids = setup_group(calendar_system, size)
    assert draft(admin, meeting).status_code == 200
    start(clock, meeting)
    view = confirm(admin, meeting)
    for mode in ["random", "balanced"]:
        key, version = uuid4(), fresh(admin, meeting)["version"]
        generated = change(
            admin, meeting, "teams/generate", {"mode": mode}, key=key, version=version
        )
        assert generated.status_code == 200, generated.text
        teams = generated.json()
        assert (
            change(
                admin, meeting, "teams/generate", {"mode": mode}, key=key, version=version
            ).json()
            == teams
        )
        assert abs(len(teams["team_a"]) - len(teams["team_b"])) <= 1
        assert teams["average_a"] == teams["average_b"] == 1000
        assert member.get(PREFIX + f"/meetings/{meeting['id']}/teams").json() is None
    a, b = [[p["player"]["id"] for p in teams[key]] for key in ["team_a", "team_b"]]
    a[-1], b[-1] = b[-1], a[-1]  # includes both rotation players at 7:7
    invalid = change(admin, meeting, "teams", {"team_a": a, "team_b": b[:-1] + [a[0]]}, "PUT")
    assert invalid.status_code == 422
    saved = change(admin, meeting, "teams", {"team_a": a, "team_b": b}, "PUT")
    assert saved.status_code == 200, saved.text
    key, version = uuid4(), fresh(admin, meeting)["version"]
    result = change(admin, meeting, "teams/confirm", key=key, version=version)
    assert result.status_code == 200, result.text
    assert change(admin, meeting, "teams/confirm", key=key, version=version).status_code == 200
    public = member.get(PREFIX + f"/meetings/{meeting['id']}/teams").json()
    assert {p["player"]["id"] for p in public["team_a"]} == set(a)
    assert "priority_status" not in str(public) and "no_show" not in str(public)
    correction = {
        "event_id": view["players"][0]["event_id"],
        "value": "no_show",
        "reason": "Pomyłka przy sprawdzaniu",
    }
    assert change(admin, meeting, "attendance/corrections", correction).status_code == 409
    assert (
        change(admin, meeting, "teams/reopen", {"reason": "Poprawka obecności"}).status_code == 200
    )
    assert member.get(PREFIX + f"/meetings/{meeting['id']}/teams").json() is None
    assert change(admin, meeting, "attendance/corrections", correction).status_code == 200
    assert admin.get(PREFIX + f"/admin/meetings/{meeting['id']}/teams").json() is None
    assert change(admin, meeting, "teams/generate", {"mode": "balanced"}).status_code == 200


def test_incomplete_changed_draft_and_cancelled_meeting(calendar_system):
    device, clock, admin, _, _, _, meeting, ids = setup_group(calendar_system, 2)
    start(clock, meeting)
    assert change(admin, meeting, "attendance/confirm").status_code == 422
    clock.at -= timedelta(days=1)
    assert draft(admin, meeting).status_code == 200
    player = as_player(device, ids[0])
    assert declaration(player, meeting, "not-going", acknowledge=True).status_code == 200
    assert len(read(admin, meeting)["players"]) == 1
    moved = move(admin, meeting)
    assert read(admin, meeting)["players"] == []
    cancelled = change(admin, moved, "cancel")  # E5 has no idempotency requirement
    assert cancelled.status_code == 200, cancelled.text
    assert change(admin, meeting, "attendance/confirm").status_code == 409
    assert (
        player.get(PREFIX + "/me/attendance-history").json()["items"][0]["current_kind"]
        == "normal_cancellation"
    )


def test_late_correction_and_no_sets_lock(calendar_system):
    device, clock, admin, _, member, _, meeting, ids = setup_group(calendar_system, 2)
    assert draft(admin, meeting, [ids[0]]).status_code == 200
    start(clock, meeting)
    view = confirm(admin, meeting)
    assert change(admin, meeting, "teams/generate", {"mode": "random"}).status_code == 422
    source = next(p["event_id"] for p in view["players"] if p["player"]["id"] == ids[0])
    correction = {"event_id": source, "value": "present", "reason": "Dotarł z opóźnieniem"}
    result = change(admin, meeting, "attendance/corrections", correction)
    assert result.status_code == 200, result.text
    assert counts(admin, meeting) == (2, 0, 0, 12)
    present = as_player(device, ids[0])
    entry = present.get(PREFIX + "/me/attendance-history").json()["items"][0]
    assert entry["original_kind"] == "no_show" and entry["current_kind"] == "present"
    assert change(admin, meeting, "teams/generate", {"mode": "random"}).status_code == 200
    assert change(admin, meeting, "teams/confirm").status_code == 200

    async def complete():
        async with admin.app.state.database.sessions() as db:
            row = await db.get(Meeting, UUID(meeting["id"]))
            row.status = "completed"
            await db.commit()

    admin.portal.call(complete)
    assert change(admin, meeting, "teams/reopen", {"reason": "Historia"}).status_code == 409
    assert (
        change(
            admin, meeting, "attendance/corrections", {**correction, "value": "no_show"}
        ).status_code
        == 409
    )
    # Never let a normal player mutate either public or administrative room data.
    for path, body, method in [
        ("attendance", {"players": []}, "PUT"),
        ("attendance/confirm", {}, "POST"),
        ("attendance/admit", {"player_id": ids[2]}, "POST"),
        ("attendance/corrections", correction, "POST"),
        ("teams/generate", {"mode": "random"}, "POST"),
        ("teams/reopen", {"reason": "x"}, "POST"),
        ("teams/confirm", {}, "POST"),
    ]:
        assert change(member, meeting, path, body, method).status_code == 403


def test_concurrent_admission_uses_meeting_lock(calendar_system):
    import asyncio
    import os

    from app.api.errors import DomainError
    from app.api.room_schemas import AdmitPlayer
    from app.core.database import Database
    from app.models.meetings import Enrollment
    from app.services import room

    _, clock, admin, actor, _, _, meeting, ids = setup_group(calendar_system, 13)
    start(clock, meeting)
    assert draft(admin, meeting).status_code == 200
    confirm(admin, meeting)

    async def race():
        database = Database(os.environ["VOLLEYCREW_TEST_DATABASE_URL"])
        version = fresh(admin, meeting)["version"]
        try:

            async def one(identifier):
                async with database.sessions() as db:
                    body = AdmitPlayer(expected_version=version, player_id=identifier)
                    try:
                        row, at, _ = await room.begin(
                            db,
                            UUID(meeting["id"]),
                            UUID(actor["id"]),
                            "admit",
                            body,
                            uuid4(),
                            clock,
                        )
                        await room.admit(db, row, body.player_id, UUID(actor["id"]), at)
                        await db.commit()
                        return "accepted"
                    except DomainError as error:
                        await db.rollback()
                        return error.code

            results = await asyncio.gather(one(ids[13]), one(ids[14]))
            assert sorted(results) == ["accepted", "version_conflict"]
            async with database.sessions() as db:
                occupied = await db.scalar(
                    select(func.count())
                    .select_from(Enrollment)
                    .where(
                        Enrollment.meeting_id == UUID(meeting["id"]),
                        Enrollment.allocation.in_(["seat", "reserved"]),
                    )
                )
                assert occupied == 14
        finally:
            await database.engine.dispose()

    # Independent PostgreSQL sessions deliberately bypass the HTTP identity advisory lock.
    asyncio.run(race())


def test_reconfirmation_is_not_absence_and_queue_can_pass_on_site(calendar_system):
    device, clock, admin, _, _, _, meeting, ids = setup_group(calendar_system)
    for identifier in ids[14:16]:
        assert declaration(as_player(device, identifier), meeting).status_code == 200
    moved = move(admin, meeting)
    start(clock, moved)
    assert read(admin, moved)["players"] == []
    confirm(admin, moved)
    # Pending reconfirmations are reservations, never no-shows.
    profile = as_player(device, ids[0])
    assert profile.get(PREFIX + "/me/attendance-history").json()["total"] == 0
    assert (
        change(admin, moved, "attendance/release-reservation", {"player_id": ids[0]}).status_code
        == 200
    )
    reservations = read(admin, moved)["reservations"]
    assert any(p["player"]["id"] == ids[14] for p in reservations)
    assert (
        change(admin, moved, "attendance/release-reservation", {"player_id": ids[14]}).status_code
        == 200
    )
    assert any(p["player"]["id"] == ids[15] for p in read(admin, moved)["reservations"])
    assert change(admin, moved, "attendance/admit", {"player_id": ids[15]}).status_code == 200
    assert as_player(device, ids[14]).get(PREFIX + "/me/attendance-history").json()["total"] == 0


def test_cancellation_history_classification_and_retry(calendar_system):
    device, clock, admin, _, _, _, meeting, ids = setup_group(calendar_system, 3)
    player = as_player(device, ids[0])
    start(clock, meeting)
    clock.at -= timedelta(hours=1)
    key = uuid4()
    assert declaration(player, meeting, "not-going", key=key, acknowledge=True).status_code == 200
    assert declaration(player, meeting, "not-going", key=key, acknowledge=True).status_code == 200
    history = player.get(PREFIX + "/me/attendance-history").json()
    assert history["total"] == 1 and history["items"][0]["current_kind"] == "late_cancellation"
    assert (
        change(
            admin,
            meeting,
            "attendance/corrections",
            {
                "event_id": history["items"][0]["id"],
                "value": "excused",
                "reason": "Sytuacja losowa",
            },
        ).status_code
        == 200
    )
    assert (
        player.get(PREFIX + "/me/attendance-history").json()["items"][0]["original_kind"]
        == "late_cancellation"
    )


@pytest.mark.parametrize("cancel", [True, False])
def test_late_offer_exception_never_excuses_no_show(calendar_system, cancel):
    from tests.test_enrollment import propose

    device, clock, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    start(clock, meeting)
    clock.at -= timedelta(hours=2)
    assert (
        declaration(as_player(device, ids[0]), meeting, "not-going", acknowledge=True).status_code
        == 200
    )
    offer = propose(admin, meeting, player["id"])
    assert mutate(member, f"/offers/{offer['id']}/accept", {"term_version": 1}).status_code == 200
    if cancel:
        assert declaration(member, meeting, "not-going").status_code == 200
        kind = "late_offer_exception"
    else:
        assert draft(admin, meeting, [player["id"]]).status_code == 200
        start(clock, meeting)
        confirm(admin, meeting)
        kind = "no_show"
        generated = change(admin, meeting, "teams/generate", {"mode": "balanced"})
        assert generated.status_code == 200
        assert player["id"] not in [
            p["player"]["id"] for p in generated.json()["team_a"] + generated.json()["team_b"]
        ]
    history = member.get(PREFIX + "/me/attendance-history").json()
    assert history["total"] == 1 and history["items"][0]["current_kind"] == kind
