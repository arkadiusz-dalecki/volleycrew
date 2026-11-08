from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select

from app.models.enrollment import EnrollmentEvent, SeatOffer
from app.models.meetings import Enrollment, ScheduleVersion
from app.models.schedule import MeetingTermRevision
from tests.test_auth import PREFIX, mutate
from tests.test_auth import system as system
from tests.test_enrollment import as_player, declaration, own, propose, setup_group
from tests.test_meetings import calendar_system as calendar_system
from tests.test_meetings import read_calendar, resolve_day


def fresh(client, meeting):
    response = client.get(PREFIX + f"/meetings/{meeting['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def move(admin, meeting, day="2026-11-12", hour="19:00"):
    current = fresh(admin, meeting)
    response = mutate(
        admin,
        f"/admin/meetings/{meeting['id']}/reschedule",
        {
            "expected_version": current["version"],
            "local_date": day,
            "local_time": hour,
            "duration_minutes": 120,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def schedule_body(admin, start="2026-11-09", weekday=3, hour="18:00"):
    state = admin.get(PREFIX + "/admin/schedule").json()
    return {
        "expected_version": state["version"],
        "effective_from": start,
        "weekday": weekday,
        "local_time": hour,
        "duration_minutes": 120,
        "venue": "I LO w Gdańsku",
    }


def preview(admin, body):
    response = mutate(admin, "/admin/schedule/preview", body)
    assert response.status_code == 200, response.text
    return response.json()


def apply(admin, body, shown=None):
    shown = shown or preview(admin, body)
    response = mutate(
        admin, "/admin/schedule/versions", {**body, "preview_token": shown["preview_token"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_single_change_requires_reconfirmation_and_preserves_identity_and_order(calendar_system):
    _, _, admin, _, member, player, original, _ = setup_group(calendar_system, 0)
    assert declaration(member, original).status_code == 200

    async def stamp():
        async with member.app.state.database.sessions() as db:
            entry = await db.scalar(
                select(Enrollment).where(Enrollment.player_id == UUID(player["id"]))
            )
            return entry.declared_at, entry.queue_number

    before = member.portal.call(stamp)
    changed = move(admin, original)
    assert changed["id"] == original["id"] and changed["source_date"] == original["source_date"]
    assert changed["term_version"] == 2 and changed["is_exception"]
    assert changed["participant_count"] == 0 and changed["reserved_count"] == 1
    assert changed["awaiting_confirmation"][0]["id"] == player["id"]
    assert declaration(member, original).status_code == 409
    assert own(member, changed)["needs_reconfirmation"]
    assert declaration(member, changed).status_code == 200
    assert not own(member, changed)["needs_reconfirmation"]
    assert own(member, changed)["allocation"] == "seat"
    assert member.portal.call(stamp) == before
    assert fresh(member, changed)["participant_count"] == 1


def test_repeated_changes_reconfirm_every_time_without_reordering_responses(calendar_system):
    device, _, admin, _, member, _, original, ids = setup_group(calendar_system, 2)
    changed = move(admin, original)
    last = as_player(device, ids[1])
    first = as_player(device, ids[0])
    assert declaration(last, changed).status_code == 200
    assert fresh(member, changed)["reserved_count"] == 1
    again = move(admin, changed, "2026-11-13", "20:00")
    assert again["term_version"] == 3 and again["reserved_count"] == 2
    assert own(last, again)["needs_reconfirmation"]
    assert declaration(last, again).status_code == 200
    assert declaration(first, again).status_code == 200
    data = fresh(member, again)
    assert [p["id"] for p in data["participants"]] == ids[:2]
    assert data["reserved_count"] == 0 and data["participant_count"] == 2

    async def revisions():
        async with member.app.state.database.sessions() as db:
            return await db.scalar(select(func.count()).select_from(MeetingTermRevision))

    assert member.portal.call(revisions) == 2


def test_change_retires_old_offer_and_keeps_one_reservation_for_new_term(calendar_system):
    device, _, admin, _, member, player, original, ids = setup_group(calendar_system)
    assert declaration(member, original).status_code == 200
    assert declaration(as_player(device, ids[0]), original, "not-going").status_code == 200
    old_offer = propose(admin, original, player["id"])
    changed = move(admin, original)
    state = own(member, changed)
    assert state["offer"]["id"] != old_offer["id"]
    assert state["offer"]["state"] == "reserved" and state["needs_reconfirmation"]
    assert changed["reserved_count"] == 14 and changed["participant_count"] == 0
    assert (
        mutate(member, f"/offers/{old_offer['id']}/accept", {"term_version": 2}).status_code == 409
    )
    new_offer = propose(admin, changed, player["id"])
    assert (
        mutate(member, f"/offers/{new_offer['id']}/accept", {"term_version": 2}).status_code == 200
    )
    assert not own(member, changed)["needs_reconfirmation"]
    assert own(member, changed)["allocation"] == "seat"
    assert fresh(member, changed)["reserved_count"] == 13


def test_waiting_places_are_protected_until_manual_release(calendar_system):
    _, _, admin, _, member, player, original, ids = setup_group(calendar_system)
    assert declaration(member, original).status_code == 200
    changed = move(admin, original)
    assert (
        declaration(admin, changed).status_code == 200
    )  # founder cannot steal reconfirmation seats
    assert own(admin, changed)["allocation"] == "waitlist"
    assert fresh(member, changed)["reserved_count"] == 14
    response = mutate(
        admin,
        f"/admin/meetings/{changed['id']}/release-reconfirmation",
        {"expected_version": fresh(admin, changed)["version"], "player_id": ids[0]},
    )
    assert response.status_code == 200, response.text
    assert own(admin, changed)["offer"]["state"] == "reserved"
    assert fresh(member, changed)["reserved_count"] == 14
    assert len(fresh(member, changed)["awaiting_confirmation"]) == 13
    assert own(member, changed)["needs_reconfirmation"]
    assert player["id"] not in [p["id"] for p in fresh(member, changed)["participants"]]


def test_cancel_preserves_calendar_and_history_but_closes_all_offers(calendar_system):
    device, _, admin, _, member, player, original, ids = setup_group(calendar_system)
    assert declaration(member, original).status_code == 200
    assert declaration(as_player(device, ids[0]), original, "not-going").status_code == 200
    old_offer = propose(admin, original, player["id"])
    current = fresh(admin, original)
    response = mutate(
        admin, f"/admin/meetings/{original['id']}/cancel", {"expected_version": current["version"]}
    )
    assert response.status_code == 200, response.text
    cancelled = response.json()
    assert cancelled["status"] == "cancelled" and cancelled["reserved_count"] == 0
    assert cancelled["participant_count"] == 0 and not own(member, cancelled)["can_declare"]
    assert (
        next(row for row in read_calendar(member)["items"] if row["id"] == original["id"])["status"]
        == "cancelled"
    )
    assert declaration(member, cancelled).status_code == 409
    assert (
        mutate(
            member, f"/offers/{old_offer['id']}/accept", {"term_version": cancelled["term_version"]}
        ).status_code
        == 409
    )
    assert member.get(PREFIX + "/meetings/next").json()["id"] != original["id"]

    async def inspect():
        async with member.app.state.database.sessions() as db:
            assert not (
                await db.scalars(
                    select(SeatOffer).where(SeatOffer.state.in_(["reserved", "pending"]))
                )
            ).all()
            events = (
                await db.scalars(
                    select(EnrollmentEvent).where(
                        EnrollmentEvent.meeting_id == UUID(original["id"]),
                        EnrollmentEvent.kind == "meeting_cancelled",
                    )
                )
            ).all()
            assert len(events) == 14 and all("cancellation_kind" not in e.details for e in events)

    member.portal.call(inspect)


def test_bulk_day_change_handles_virtual_existing_cancelled_and_kept_exception(calendar_system):
    _, _, admin, _, member, _, first, _ = setup_group(calendar_system, 0)
    assert declaration(member, first).status_code == 200
    second = resolve_day(member, "2026-11-17")
    cancelled = resolve_day(member, "2026-11-24")
    assert (
        mutate(
            admin,
            f"/admin/meetings/{cancelled['id']}/cancel",
            {"expected_version": cancelled["version"]},
        ).status_code
        == 200
    )
    special = move(admin, resolve_day(member, "2026-12-01"), "2026-12-02", "19:00")
    body = schedule_body(admin)
    shown = preview(admin, body)
    assert shown["kept_exception_count"] == 1 and shown["reconfirmation_count"] == 1
    result = apply(admin, body, shown)
    new_id = result["rules"][-1]["id"]
    assert result["version"] == 2
    assert fresh(member, first)["starts_at"].startswith("2026-11-12T17:00")
    assert fresh(member, second)["starts_at"].startswith("2026-11-19T17:00")
    assert fresh(member, cancelled)["status"] == "cancelled"
    assert fresh(member, special)["starts_at"] == special["starts_at"]
    november = read_calendar(member)["items"]
    assert len([row for row in november if row["id"] == first["id"]]) == 1
    assert all(datetime.fromisoformat(row["starts_at"]).weekday() == 3 for row in november)
    december = read_calendar(member, "2026-12-01", "2027-01-01")["items"]
    assert special["id"] in [row["id"] for row in december]
    assert not any(row["starts_at"].startswith("2026-12-03") for row in december)
    aliased = resolve_day(member, "2026-11-12", new_id)
    assert aliased["id"] == first["id"]
    assert resolve_day(member, "2026-11-10")["id"] == first["id"]
    assert (
        mutate(
            member,
            "/meetings/resolve",
            {"schedule_version_id": first["schedule_version_id"], "source_date": "2026-12-08"},
        ).status_code
        == 409
    )


def test_preview_detects_new_enrollment_and_other_admin_card(calendar_system):
    device, _, admin, actor, member, _, first, _ = setup_group(calendar_system, 0)
    body = schedule_body(admin)
    shown = preview(admin, body)
    assert declaration(member, first).status_code == 200
    assert (
        mutate(
            admin, "/admin/schedule/versions", {**body, "preview_token": shown["preview_token"]}
        ).status_code
        == 409
    )
    assert admin.get(PREFIX + "/admin/schedule").json()["version"] == 1
    other = device()
    from tests.test_auth import login

    assert login(other, actor, "123456").status_code == 200
    second_body = {**body, "weekday": 4}
    options = [
        (admin, body, preview(admin, body)),
        (other, second_body, preview(other, second_body)),
    ]
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda item: mutate(
                    item[0],
                    "/admin/schedule/versions",
                    {**item[1], "preview_token": item[2]["preview_token"]},
                ),
                options,
            )
        )
    assert sorted(row.status_code for row in responses) == [200, 409]


def test_earlier_change_supersedes_future_rules_without_losing_foreign_keys(calendar_system):
    _, _, admin, _, member, _, _, _ = setup_group(calendar_system, 0)
    future = apply(admin, schedule_body(admin, "2026-12-07", 2, "19:00"))
    rule_id = future["rules"][-1]["id"]
    existing = resolve_day(member, "2026-12-09", rule_id)
    apply(admin, schedule_body(admin))
    assert fresh(member, existing)["starts_at"].startswith("2026-12-10T17:00")
    assert resolve_day(member, "2026-12-09", rule_id)["id"] == existing["id"]
    assert (
        mutate(
            member,
            "/meetings/resolve",
            {"schedule_version_id": rule_id, "source_date": "2026-12-16"},
        ).status_code
        == 409
    )
    active = member.get(PREFIX + "/schedule").json()
    assert all(row["id"] != rule_id for row in active)

    async def preserved():
        async with member.app.state.database.sessions() as db:
            row = await db.get(ScheduleVersion, UUID(rule_id))
            assert row.superseded

    member.portal.call(preserved)


def test_permissions_boundaries_dst_and_stale_single_edit_are_explicit(calendar_system):
    _, clock, admin, _, member, _, first, _ = setup_group(calendar_system, 0)
    body = schedule_body(admin)
    assert mutate(member, "/admin/schedule/preview", body).status_code == 403
    assert (
        mutate(
            member, f"/admin/meetings/{first['id']}/cancel", {"expected_version": first["version"]}
        ).status_code
        == 403
    )
    assert (
        mutate(
            admin, "/admin/schedule/preview", {**body, "effective_from": "2026-11-05"}
        ).status_code
        == 422
    )
    assert (
        mutate(
            admin, "/admin/schedule/preview", {**body, "weekday": 6, "local_time": "02:30"}
        ).status_code
        == 422
    )
    assert (
        mutate(
            admin, "/admin/schedule/preview", {**body, "effective_from": "2026-11-10", "weekday": 0}
        ).status_code
        == 409
    )
    assert (
        mutate(
            admin,
            f"/admin/meetings/{first['id']}/reschedule",
            {
                "expected_version": first["version"],
                "local_date": "2027-03-28",
                "local_time": "02:30",
                "duration_minutes": 120,
            },
        ).status_code
        == 422
    )
    changed = move(admin, first)
    assert (
        mutate(
            admin, f"/admin/meetings/{first['id']}/cancel", {"expected_version": first["version"]}
        ).status_code
        == 409
    )
    clock.at = datetime.fromisoformat(changed["starts_at"])
    assert (
        mutate(
            admin, f"/admin/meetings/{first['id']}/cancel", {"expected_version": changed["version"]}
        ).status_code
        == 409
    )


def test_single_edit_cannot_duplicate_an_unmaterialized_weekly_slot(calendar_system):
    _, _, admin, _, _, _, original, _ = setup_group(calendar_system, 0)
    response = mutate(
        admin,
        f"/admin/meetings/{original['id']}/reschedule",
        {
            "expected_version": original["version"],
            "local_date": "2026-11-17",
            "local_time": "18:00",
            "duration_minutes": 120,
        },
    )
    assert response.status_code == 409 and response.json()["code"] == "schedule_collision"


def test_kept_exception_cannot_duplicate_a_new_unmaterialized_schedule_slot(calendar_system):
    _, _, admin, _, _, _, original, _ = setup_group(calendar_system, 0)
    move(admin, original, "2026-11-18", "18:00")
    body = schedule_body(admin, weekday=2)
    response = mutate(admin, "/admin/schedule/preview", body)
    assert response.status_code == 409 and response.json()["code"] == "schedule_collision"
    assert admin.get(PREFIX + "/admin/schedule").json()["version"] == 1


def test_bounded_series_restores_schedule_and_preserves_following_meeting(calendar_system):
    _, _, admin, _, member, _, first, _ = setup_group(calendar_system, 0)
    following = resolve_day(member, "2026-12-01")
    body = {**schedule_body(admin, "2026-11-09", 2, "17:00"), "effective_until": "2026-11-30"}
    apply(admin, body)
    november = read_calendar(member)["items"]
    assert [row["starts_at"][:10] for row in november] == ["2026-11-11", "2026-11-18", "2026-11-25"]
    assert all(row["starts_at"][11:16] == "16:00" for row in november)
    assert fresh(member, first)["id"] == first["id"]
    assert fresh(member, following)["starts_at"] == following["starts_at"]
    december = read_calendar(member, "2026-12-01", "2027-01-01")["items"]
    assert len(december) == 5
    assert all(datetime.fromisoformat(row["starts_at"]).weekday() == 1 for row in december)
    assert sum(row["id"] == following["id"] for row in december) == 1
    assert (
        resolve_day(member, "2026-12-01", december[0]["schedule_version_id"])["id"]
        == following["id"]
    )


def test_single_addition_permissions_collision_and_survival_of_series_change(calendar_system):
    _, _, admin, _, member, _, _, _ = setup_group(calendar_system, 0)
    body = {
        "expected_version": 1,
        "local_date": "2026-11-08",
        "local_time": "17:00",
        "duration_minutes": 120,
        "venue": "Inna sala",
    }
    assert mutate(member, "/admin/meetings", body).status_code == 403
    response = mutate(admin, "/admin/meetings", body)
    assert response.status_code == 200, response.text
    added = response.json()
    assert member.get(PREFIX + "/meetings/next").json()["id"] == added["id"]
    assert declaration(member, added).status_code == 200
    assert mutate(admin, "/admin/meetings", body).status_code == 409
    current = {**body, "expected_version": 2}
    assert mutate(admin, "/admin/meetings", current).status_code == 409
    assert (
        mutate(
            admin, "/admin/meetings", {**current, "local_date": "2026-11-10", "local_time": "18:00"}
        ).status_code
        == 409
    )
    assert (
        mutate(admin, "/admin/meetings", {**current, "local_date": "2026-11-05"}).status_code == 422
    )
    assert (
        mutate(
            admin, "/admin/meetings", {**current, "local_date": "2027-03-28", "local_time": "02:30"}
        ).status_code
        == 422
    )
    apply(admin, schedule_body(admin, "2026-11-07", 3))
    assert fresh(member, added)["starts_at"] == added["starts_at"]
    assert fresh(member, added)["participant_count"] == 1
    assert any(row["id"] == added["id"] for row in read_calendar(member)["items"])


def test_bounded_series_validates_range_and_collisions_with_additional_meetings(calendar_system):
    _, _, admin, _, _, _, _, _ = setup_group(calendar_system, 0)
    body = schedule_body(admin, "2026-11-09", 2)
    for end in ("2026-11-08", "2026-11-09", "2026-11-10"):
        assert (
            mutate(admin, "/admin/schedule/preview", {**body, "effective_until": end}).status_code
            == 422
        )
    assert (
        mutate(
            admin,
            "/admin/meetings",
            {
                "expected_version": 1,
                "local_date": "2026-11-18",
                "local_time": "18:00",
                "duration_minutes": 120,
                "venue": "Sala",
            },
        ).status_code
        == 200
    )
    body = {**body, "expected_version": 2, "effective_until": "2026-11-30"}
    assert mutate(admin, "/admin/schedule/preview", body).status_code == 409


def test_series_cannot_overlap_preserved_overnight_slot_at_end_boundary(calendar_system):
    _, _, admin, _, _, _, _, _ = setup_group(calendar_system, 0)
    # Monday 23:00 through Tuesday 23:00 would overlap the restored Tuesday 18:00.
    body = {
        **schedule_body(admin, "2026-11-09", 0, "23:00"),
        "duration_minutes": 1440,
        "effective_until": "2026-11-10",
    }
    response = mutate(admin, "/admin/schedule/preview", body)
    assert response.status_code == 409, response.text
