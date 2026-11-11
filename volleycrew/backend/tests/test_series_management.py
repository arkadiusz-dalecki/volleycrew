from datetime import UTC, datetime

from tests.calendar_support import DEFAULT_ID
from tests.test_auth import PREFIX, mutate
from tests.test_auth import system as system
from tests.test_enrollment import declaration, setup_group
from tests.test_meetings import calendar_system as calendar_system
from tests.test_meetings import read_calendar, resolve_day
from tests.test_schedule_changes import apply, fresh, move, schedule_body


def remove_meeting(admin, meeting):
    return mutate(
        admin, f"/admin/meetings/{meeting['id']}/delete", {"expected_version": meeting["version"]}
    )


def series_preview(admin, body=None, rule_id=DEFAULT_ID):
    state = admin.get(PREFIX + "/admin/schedule").json()
    action = "preview" if body else "delete-preview"
    payload = body or {"expected_version": state["version"]}
    result = mutate(admin, f"/admin/schedule/rules/{rule_id}/{action}", payload)
    assert result.status_code == 200, result.text
    return result.json()


def series_apply(admin, body=None, rule_id=DEFAULT_ID, shown=None):
    shown = shown or series_preview(admin, body, rule_id)
    action = "edit" if body else "delete"
    payload = body or {"expected_version": shown["version"]}
    return mutate(
        admin,
        f"/admin/schedule/rules/{rule_id}/{action}",
        {**payload, "preview_token": shown["preview_token"]},
    )


def test_delete_disappears_everywhere_and_cannot_regenerate(calendar_system):
    _, _, admin, _, member, _, original, _ = setup_group(calendar_system, 0)
    assert declaration(member, original).status_code == 200
    current = fresh(admin, original)
    assert remove_meeting(member, current).status_code == 403
    assert remove_meeting(admin, original).status_code == 409
    assert remove_meeting(admin, current).status_code == 204
    assert all(row["id"] != original["id"] for row in read_calendar(member)["items"])
    assert member.get(PREFIX + "/meetings/next").json()["id"] != original["id"]
    for path in [
        f"/meetings/{original['id']}",
        f"/meetings/{original['id']}/my-participation",
        f"/meetings/{original['id']}/teams",
        f"/admin/meetings/{original['id']}/signature-list",
    ]:
        assert admin.get(PREFIX + path).status_code == 404
    assert (
        mutate(
            member,
            "/meetings/resolve",
            {"schedule_version_id": str(DEFAULT_ID), "source_date": "2026-11-10"},
        ).status_code
        == 404
    )
    assert declaration(member, current).status_code == 404
    # A later series change must carry the invisible marker to the replacement rule.
    apply(admin, schedule_body(admin))
    assert not any(
        row["starts_at"].startswith("2026-11-12") for row in read_calendar(member)["items"]
    )


def test_delete_old_cancelled_meeting_but_preserve_started_game(calendar_system):
    _, clock, admin, _, member, _, original, _ = setup_group(calendar_system, 0)
    cancelled = mutate(
        admin, f"/admin/meetings/{original['id']}/cancel", {"expected_version": original["version"]}
    ).json()
    other = resolve_day(member, "2026-11-17")
    clock.at = datetime(2026, 11, 18, 12, tzinfo=UTC)
    assert remove_meeting(admin, cancelled).status_code == 204
    assert remove_meeting(admin, other).status_code == 409
    assert all(row["id"] != original["id"] for row in read_calendar(member)["items"])


def test_delete_series_removes_virtual_persisted_and_exception_not_additions(calendar_system):
    _, _, admin, _, member, _, original, _ = setup_group(calendar_system, 0)
    moved = move(admin, resolve_day(member, "2026-11-17"), "2026-11-18")
    added = mutate(
        admin,
        "/admin/meetings",
        {
            "expected_version": 1,
            "local_date": "2026-11-20",
            "local_time": "18:00",
            "duration_minutes": 120,
            "venue": "Sala",
        },
    ).json()
    shown = series_preview(admin)
    assert shown["removed_count"] == 2
    result = series_apply(admin, shown=shown)
    assert result.status_code == 200, result.text
    assert [row["id"] for row in read_calendar(member)["items"]] == [added["id"]]
    assert read_calendar(member, "2027-01-01", "2027-02-01")["items"] == []
    assert member.get(PREFIX + "/meetings/next").json()["id"] == added["id"]
    for row in [original, moved]:
        assert member.get(PREFIX + f"/meetings/{row['id']}").status_code == 404
    assert (
        mutate(
            member,
            "/meetings/resolve",
            {"schedule_version_id": str(DEFAULT_ID), "source_date": "2026-11-24"},
        ).status_code
        == 409
    )


def test_edit_selected_series_preserves_ids_reconfirmation_and_deleted_markers(calendar_system):
    _, _, admin, _, member, _, original, _ = setup_group(calendar_system, 0)
    assert declaration(member, original).status_code == 200
    deleted = resolve_day(member, "2026-11-17")
    assert remove_meeting(admin, deleted).status_code == 204
    later = resolve_day(member, "2026-12-01")
    body = {**schedule_body(admin, "2026-11-09", 2, "19:00"), "effective_until": "2026-11-30"}
    shown = series_preview(admin, body)
    assert shown["reconfirmation_count"] == 1 and shown["removed_count"] == 1
    result = series_apply(admin, body, shown=shown)
    assert result.status_code == 200, result.text
    changed = fresh(member, original)
    assert changed["starts_at"].startswith("2026-11-11T18:00")
    assert changed["reserved_count"] == 1 and changed["participants"] == []
    assert member.get(PREFIX + f"/meetings/{later['id']}").status_code == 404
    dates = [row["starts_at"][:10] for row in read_calendar(member)["items"]]
    assert dates == ["2026-11-11", "2026-11-25"]
    assert read_calendar(member, "2026-12-01", "2027-01-01")["items"] == []
    new = next(rule for rule in result.json()["rules"] if rule["effective_from"] == "2026-11-09")
    assert (
        mutate(
            member,
            "/meetings/resolve",
            {"schedule_version_id": new["id"], "source_date": "2026-11-18"},
        ).status_code
        == 404
    )


def test_series_preview_detects_enrollments_versions_and_permissions(calendar_system):
    _, _, admin, _, member, _, original, _ = setup_group(calendar_system, 0)
    assert (
        mutate(
            member, f"/admin/schedule/rules/{DEFAULT_ID}/delete-preview", {"expected_version": 1}
        ).status_code
        == 403
    )
    shown = series_preview(admin)
    assert declaration(member, original).status_code == 200
    assert series_apply(admin, shown=shown).status_code == 409
    assert fresh(member, original)["status"] == "scheduled"
    body = schedule_body(admin, "2026-11-09", 2)
    shown = series_preview(admin, body)
    assert remove_meeting(admin, fresh(admin, original)).status_code == 204
    assert series_apply(admin, body, shown=shown).status_code == 409


def test_series_delete_keeps_historical_games_and_other_rule_ranges(calendar_system):
    _, clock, admin, _, member, _, original, _ = setup_group(calendar_system, 0)
    # An untouched earlier record remains available when removing the future part.
    clock.at = datetime(2026, 11, 11, 12, tzinfo=UTC)
    assert series_apply(admin).status_code == 200
    assert fresh(member, original)["id"] == original["id"]
    assert [row["id"] for row in read_calendar(member)["items"]] == [original["id"]]
    assert member.get(PREFIX + "/meetings/next").json() is None


def test_edit_preserves_exceptions_and_rejects_colliding_new_series(calendar_system):
    _, _, admin, _, member, _, original, _ = setup_group(calendar_system, 0)
    special = move(admin, original, "2026-11-13", "20:00")
    body = schedule_body(admin, "2026-11-09", 2)
    result = series_apply(admin, body)
    assert result.status_code == 200, result.text
    assert fresh(member, special)["starts_at"] == special["starts_at"]
    assert not any(
        row["starts_at"].startswith("2026-11-11") for row in read_calendar(member)["items"]
    )
    new_id = next(
        rule["id"] for rule in result.json()["rules"] if rule["effective_from"] == "2026-11-09"
    )
    # An independent future rule blocks extending the selected rule into its dates.
    apply(admin, schedule_body(admin, "2026-12-07", 4))
    bad = schedule_body(admin, "2026-11-09", 3)
    response = mutate(admin, f"/admin/schedule/rules/{new_id}/preview", bad)
    assert response.status_code == 409


def test_delete_series_closes_pending_offers_without_attendance_events(calendar_system):
    from sqlalchemy import func, select

    from app.models.enrollment import SeatOffer
    from app.models.meetings import Enrollment
    from app.models.room import AttendanceEvent
    from tests.test_enrollment import as_player, propose

    device, _, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    assert declaration(as_player(device, ids[0]), meeting, "not-going").status_code == 200
    propose(admin, fresh(admin, meeting), player["id"])

    async def event_count():
        async with admin.app.state.database.sessions() as db:
            return await db.scalar(select(func.count()).select_from(AttendanceEvent))

    before = admin.portal.call(event_count)
    assert series_apply(admin).status_code == 200

    async def inspect():
        async with admin.app.state.database.sessions() as db:
            assert not (
                await db.scalars(
                    select(SeatOffer).where(SeatOffer.state.in_(["pending", "reserved"]))
                )
            ).all()
            assert not (
                await db.scalars(select(Enrollment).where(Enrollment.allocation != "none"))
            ).all()
            assert await db.scalar(select(func.count()).select_from(AttendanceEvent)) == before

    admin.portal.call(inspect)


def test_two_series_changes_cannot_overwrite_each_other(calendar_system):
    from concurrent.futures import ThreadPoolExecutor

    from tests.test_auth import login

    device, _, admin, actor, _, _, _, _ = setup_group(calendar_system, 0)
    other = device()
    assert login(other, actor, "123456").status_code == 200
    shown = series_preview(admin)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda client: series_apply(client, shown=shown), [admin, other]))
    assert sorted(result.status_code for result in results) == [200, 409]
