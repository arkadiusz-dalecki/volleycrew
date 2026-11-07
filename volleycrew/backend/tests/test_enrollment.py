import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.database import Database
from app.models.auth import Player
from app.models.enrollment import EnrollmentEvent
from app.models.meetings import Enrollment, Meeting
from app.services import enrollment
from app.services.meetings import resolve
from tests.test_auth import PREFIX, group, login, mutate
from tests.test_auth import system as system
from tests.test_meetings import calendar_system as calendar_system
from tests.test_meetings import resolve_day


def declaration(client, meeting, value="going", key=None, acknowledge=False):
    return mutate(
        client,
        f"/meetings/{meeting['id']}/my-declaration",
        {
            "declaration": value,
            "term_version": meeting["term_version"],
            "acknowledge_late": acknowledge,
        },
        "PUT",
        **{"Idempotency-Key": str(key or uuid4())},
    )


def own(client, meeting):
    response = client.get(PREFIX + f"/meetings/{meeting['id']}/my-participation")
    assert response.status_code == 200, response.text
    return response.json()


def setup_group(system, count=14):
    device, clock, admin, actor, member, player, _, _ = group(system)
    meeting = resolve_day(member)

    async def seed():
        async with member.app.state.database.sessions() as db:
            source = await db.get(Player, UUID(player["id"]))
            seeded = []
            for index in range(count + 3):
                person = Player(
                    first_name=f"Gracz{index}",
                    last_name="Testowy",
                    priority_status="guest",
                    role="player",
                    is_active=True,
                    pin_hash=source.pin_hash,
                    created_at=clock.at,
                )
                db.add(person)
                await db.flush()
                seeded.append(str(person.id))
                if index < count:
                    await enrollment.declare(
                        db, UUID(meeting["id"]), person, "going", 1, clock.at, uuid4()
                    )
                    await db.commit()
            await db.commit()
            return seeded

    ids = member.portal.call(seed)
    return device, clock, admin, actor, member, player, meeting, ids


def as_player(device, player_id):
    client = device()
    assert login(client, {"id": player_id}).status_code == 200
    return client


def counts(client, meeting):
    data = client.get(PREFIX + f"/meetings/{meeting['id']}").json()
    return (
        data["participant_count"],
        data["reserved_count"],
        data["waitlist_count"],
        data["free_count"],
    )


def propose(admin, meeting, player_id):
    response = mutate(
        admin,
        f"/admin/meetings/{meeting['id']}/offers",
        {"player_id": player_id, "term_version": meeting["term_version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_concurrent_last_seat_http_and_independent_transactions(calendar_system):
    device, clock, _, _, member, player, meeting, ids = setup_group(calendar_system, 13)
    other = as_player(device, ids[13])
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda client: declaration(client, meeting), [member, other]))
    assert all(response.status_code == 200 for response in responses)
    assert counts(member, meeting) == (14, 0, 1, 0)

    async def concurrent():
        database = Database(os.environ["VOLLEYCREW_TEST_DATABASE_URL"])
        try:
            async with database.sessions() as db:
                row = await db.get(Meeting, UUID(meeting["id"]))
                # A second real Meeting to run a race without the HTTP identity advisory lock.
                second = await resolve(
                    db, row.schedule_version_id, row.source_date + timedelta(days=7), clock.at
                )
                second_id = second.id
                for identifier in ids[:13]:
                    await enrollment.declare(
                        db,
                        second_id,
                        await db.get(Player, UUID(identifier)),
                        "going",
                        1,
                        clock.at,
                        uuid4(),
                    )
                await db.commit()

            async def one(identifier):
                async with database.sessions() as db:
                    await enrollment.declare(
                        db,
                        second_id,
                        await db.get(Player, UUID(identifier)),
                        "going",
                        1,
                        clock.at,
                        uuid4(),
                    )
                    await db.commit()

            await asyncio.gather(one(player["id"]), one(ids[13]))
            async with database.sessions() as db:
                rows = (
                    await db.scalars(select(Enrollment).where(Enrollment.meeting_id == second_id))
                ).all()
                assert sum(row.allocation == "seat" for row in rows) == 14
                assert sum(row.allocation == "waitlist" for row in rows) == 1
        finally:
            await database.engine.dispose()

    asyncio.run(concurrent())


def test_priority_displacement_retry_and_private_dto(calendar_system):
    device, _, admin, actor, member, player, meeting, ids = setup_group(calendar_system)
    assert (
        mutate(
            admin, f"/admin/players/{player['id']}", {"priority_status": "player"}, "PATCH"
        ).status_code
        == 200
    )
    key = uuid4()
    assert declaration(member, meeting, key=key).status_code == 200
    assert own(member, meeting)["allocation"] == "seat"
    last = as_player(device, ids[13])
    assert own(last, meeting)["allocation"] == "waitlist"
    assert declaration(admin, meeting).status_code == 200
    assert counts(member, meeting) == (14, 0, 2, 0)
    assert declaration(member, meeting, key=key).status_code == 200
    before = own(member, meeting)
    assert declaration(member, meeting, "not-going").status_code == 200
    assert (
        declaration(member, meeting, key=key).status_code == 200
    )  # replay cannot undo the later cancellation
    assert own(member, meeting)["declaration"] == "not-going"
    assert declaration(member, meeting, "not-going", key=key).status_code == 409
    assert before["allocation"] == "seat"
    for path in [
        f"/meetings/{meeting['id']}",
        "/players",
        "/calendar?from=2026-11-01&to=2026-12-01",
    ]:
        response = member.get(PREFIX + path)
        assert response.status_code == 200
        assert not any(
            field in response.text
            for field in [
                "priority_status",
                "founder",
                "pin_hash",
                "cancellation_kind",
                "accepted_late_offer",
            ]
        )
    assert (
        mutate(
            member, f"/admin/players/{actor['id']}", {"priority_status": "guest"}, "PATCH"
        ).status_code
        == 403
    )


def test_reservation_is_protected_and_requires_explicit_proposal_and_acceptance(calendar_system):
    device, _, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    leaving = as_player(device, ids[0])
    assert declaration(leaving, meeting, "not-going").status_code == 200
    assert counts(member, meeting) == (13, 1, 1, 0)
    state = own(member, meeting)
    assert state["allocation"] == "reserved" and state["offer"]["state"] == "reserved"
    assert declaration(member, meeting).status_code == 200
    assert own(member, meeting)["allocation"] == "reserved"
    assert (
        mutate(member, f"/offers/{state['offer']['id']}/accept", {"term_version": 1}).status_code
        == 409
    )
    assert (
        declaration(admin, meeting).status_code == 200
    )  # founder may displace a seat but cannot steal this reservation
    assert own(member, meeting)["allocation"] == "reserved"
    offer = propose(admin, meeting, player["id"])
    assert propose(admin, meeting, player["id"])["id"] == offer["id"]
    assert mutate(leaving, f"/offers/{offer['id']}/accept", {"term_version": 1}).status_code == 403
    assert mutate(member, f"/offers/{offer['id']}/accept", {"term_version": 1}).status_code == 200
    assert mutate(member, f"/offers/{offer['id']}/accept", {"term_version": 1}).status_code == 200
    assert own(member, meeting)["allocation"] == "seat"
    assert counts(member, meeting)[0] == 14


def test_decline_close_multiple_reservations_and_new_queue_on_rejoin(calendar_system):
    device, clock, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    waiters = [member, as_player(device, ids[14]), as_player(device, ids[15])]
    for client in waiters:
        assert declaration(client, meeting).status_code == 200
    for identifier in ids[:2]:
        assert declaration(as_player(device, identifier), meeting, "not-going").status_code == 200
    assert counts(member, meeting) == (12, 2, 3, 0)
    first = propose(admin, meeting, player["id"])
    second = propose(admin, meeting, ids[14])
    clock.at += timedelta(hours=1)
    assert mutate(member, f"/offers/{first['id']}/decline", {"term_version": 1}).status_code == 200
    assert own(member, meeting)["declaration"] == "withdrawn"
    assert own(waiters[2], meeting)["allocation"] == "reserved"
    assert (
        mutate(admin, f"/admin/offers/{second['id']}/close", {"term_version": 1}).status_code == 200
    )
    assert (
        mutate(admin, f"/admin/offers/{second['id']}/close", {"term_version": 1}).status_code == 200
    )
    assert (
        mutate(waiters[1], f"/offers/{second['id']}/accept", {"term_version": 1}).status_code == 409
    )
    assert own(waiters[1], meeting)["declaration"] == "withdrawn"
    assert declaration(member, meeting).status_code == 200
    assert mutate(member, f"/offers/{first['id']}/accept", {"term_version": 1}).status_code == 409

    async def history():
        async with member.app.state.database.sessions() as db:
            events = (
                await db.scalars(
                    select(EnrollmentEvent)
                    .where(
                        EnrollmentEvent.player_id == UUID(player["id"]),
                        EnrollmentEvent.kind == "declared",
                    )
                    .order_by(EnrollmentEvent.created_at)
                )
            ).all()
            assert len(events) == 2
            assert events[1].details["queue_number"] > events[0].details["queue_number"]
            assert events[1].created_at > events[0].created_at

    member.portal.call(history)


def test_cutoff_protects_seats_and_status_change_respects_reservations(calendar_system):
    device, clock, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    assert (
        mutate(
            admin, f"/admin/players/{player['id']}", {"priority_status": "founder"}, "PATCH"
        ).status_code
        == 200
    )
    assert (
        own(member, meeting)["allocation"] == "reserved"
    )  # changed priority still needs reserve confirmation
    clock.at = datetime.fromisoformat(meeting["starts_at"]) - timedelta(hours=24)
    assert declaration(admin, meeting).status_code == 200
    assert (
        own(admin, meeting)["allocation"] == "waitlist"
    )  # founder cannot evict in the protected period
    assert own(member, meeting)["allocation"] == "reserved"
    assert (
        mutate(
            admin, f"/admin/players/{ids[0]}", {"priority_status": "founder"}, "PATCH"
        ).status_code
        == 200
    )
    assert own(as_player(device, ids[0]), meeting)["allocation"] == "seat"
    # A vacancy is still available to signups; priority freeze is not a registration freeze.
    for identifier in ids[:3]:
        assert declaration(as_player(device, identifier), meeting, "not-going").status_code == 200
    assert own(admin, meeting)["allocation"] == "reserved"
    assert declaration(as_player(device, ids[14]), meeting).status_code == 200
    assert own(as_player(device, ids[14]), meeting)["allocation"] == "seat"


@pytest.mark.parametrize("seconds,expected", [(0, "normal"), (1, "late")])
def test_cancellation_deadline_is_checked_again_in_mutation(calendar_system, seconds, expected):
    _, clock, _, _, member, _, meeting, _ = setup_group(calendar_system, 0)
    assert declaration(member, meeting).status_code == 200
    clock.at = (
        datetime.fromisoformat(meeting["starts_at"])
        - timedelta(hours=24)
        + timedelta(seconds=seconds)
    )
    assert own(member, meeting)["cancellation_kind"] == expected
    response = declaration(member, meeting, "not-going")
    assert response.status_code == (409 if seconds else 200)
    if seconds:
        assert declaration(member, meeting, "not-going", acknowledge=True).status_code == 200


def test_late_offer_exception_is_recorded_but_direct_late_signup_has_no_exception(calendar_system):
    device, clock, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    clock.at = datetime.fromisoformat(meeting["starts_at"]) - timedelta(hours=2)
    assert (
        declaration(as_player(device, ids[0]), meeting, "not-going", acknowledge=True).status_code
        == 200
    )
    offer = propose(admin, meeting, player["id"])
    assert mutate(member, f"/offers/{offer['id']}/accept", {"term_version": 1}).status_code == 200
    assert own(member, meeting)["cancellation_kind"] == "late_offer_exception"
    assert declaration(member, meeting, "not-going").status_code == 200
    fresh = as_player(device, ids[14])
    assert declaration(fresh, meeting).status_code == 200
    assert own(fresh, meeting)["cancellation_kind"] == "late"


def test_block_racing_offer_accept_releases_all_future_places_and_invalidates_offer(
    calendar_system,
):
    device, _, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    assert declaration(as_player(device, ids[14]), meeting).status_code == 200
    assert declaration(as_player(device, ids[0]), meeting, "not-going").status_code == 200
    offer = propose(admin, meeting, player["id"])
    with ThreadPoolExecutor(max_workers=2) as executor:
        accepted = executor.submit(
            mutate, member, f"/offers/{offer['id']}/accept", {"term_version": 1}
        )
        blocked = executor.submit(
            mutate, admin, f"/admin/players/{player['id']}", {"is_active": False}, "PATCH"
        )
        assert accepted.result().status_code in {200, 401}
        assert blocked.result().status_code == 200
    replacement = as_player(device, ids[14])
    assert own(replacement, meeting)["allocation"] == "reserved"
    assert counts(replacement, meeting) == (13, 1, 1, 0)
    assert (
        mutate(admin, f"/admin/players/{player['id']}", {"is_active": True}, "PATCH").status_code
        == 200
    )
    assert login(member, player).status_code == 200
    assert own(member, meeting)["declaration"] == "withdrawn"
    assert mutate(member, f"/offers/{offer['id']}/accept", {"term_version": 1}).status_code == 409


def test_stale_term_cancelled_meeting_and_non_admin_offer_mutations(calendar_system):
    device, _, admin, _, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    assert declaration(as_player(device, ids[0]), meeting, "not-going").status_code == 200
    offer = propose(admin, meeting, player["id"])
    assert (
        mutate(
            member,
            f"/admin/meetings/{meeting['id']}/offers",
            {"player_id": player["id"], "term_version": 1},
        ).status_code
        == 403
    )

    async def change():
        async with member.app.state.database.sessions() as db:
            row = await db.get(Meeting, UUID(meeting["id"]))
            row.term_version = 2
            await db.commit()

    member.portal.call(change)
    assert declaration(member, meeting).status_code == 409
    assert mutate(member, f"/offers/{offer['id']}/accept", {"term_version": 2}).status_code == 409

    async def cancel():
        async with member.app.state.database.sessions() as db:
            row = await db.get(Meeting, UUID(meeting["id"]))
            row.status = "cancelled"
            await db.commit()

    member.portal.call(cancel)
    assert not own(member, meeting)["can_declare"]
    assert declaration(member, {**meeting, "term_version": 2}).status_code == 409


def test_block_releases_every_future_meeting_and_preserves_past_enrollment(calendar_system):
    _, clock, admin, _, member, player, first, _ = setup_group(calendar_system, 0)
    later = [resolve_day(member, day) for day in ["2026-11-24", "2026-12-01"]]
    for meeting in [first, *later]:
        assert declaration(member, meeting).status_code == 200
    clock.at = datetime.fromisoformat(first["ends_at"]) + timedelta(days=1)
    assert (
        mutate(admin, f"/admin/players/{player['id']}", {"is_active": False}, "PATCH").status_code
        == 200
    )

    async def inspect():
        async with admin.app.state.database.sessions() as db:
            rows = (
                await db.scalars(
                    select(Enrollment).where(Enrollment.player_id == UUID(player["id"]))
                )
            ).all()
            assert (
                next(row for row in rows if str(row.meeting_id) == first["id"]).allocation == "seat"
            )
            assert all(
                row.declaration == "withdrawn" and row.allocation == "none"
                for row in rows
                if str(row.meeting_id) != first["id"]
            )

    admin.portal.call(inspect)
    assert (
        mutate(admin, f"/admin/players/{player['id']}", {"is_active": True}, "PATCH").status_code
        == 200
    )
    assert login(member, player).status_code == 200
    assert own(member, later[0])["allocation"] == "none"


@pytest.mark.parametrize(
    "existing,new_status,allocation",
    [
        ("player", "founder", "seat"),
        ("guest", "player", "seat"),
        ("player", "guest", "waitlist"),
        ("founder", "player", "waitlist"),
    ],
)
def test_all_three_priority_levels_are_independent_of_admin_role(
    calendar_system, existing, new_status, allocation
):
    _, _, admin, _, member, player, meeting, ids = setup_group(calendar_system)

    async def initial_statuses():
        async with admin.app.state.database.sessions() as db:
            for identifier in ids[:14]:
                row = await db.get(Player, UUID(identifier))
                row.priority_status = existing
            await db.commit()

    admin.portal.call(initial_statuses)
    assert (
        mutate(
            admin, f"/admin/players/{player['id']}", {"priority_status": new_status}, "PATCH"
        ).status_code
        == 200
    )
    assert declaration(member, meeting).status_code == 200
    assert own(member, meeting)["allocation"] == allocation
    assert member.get(PREFIX + "/me").json()["role"] == "player"
    assert mutate(member, "/admin/invites").status_code == 403
    assert counts(member, meeting)[0] == 14


def test_pending_offer_and_new_signup_race_in_separate_transactions(calendar_system):
    device, clock, admin, actor, member, player, meeting, ids = setup_group(calendar_system)
    assert declaration(member, meeting).status_code == 200
    assert declaration(as_player(device, ids[0]), meeting, "not-going").status_code == 200
    offer = propose(admin, meeting, player["id"])
    clock.at = datetime.fromisoformat(meeting["starts_at"]) - timedelta(hours=2)

    async def race():
        database = Database(os.environ["VOLLEYCREW_TEST_DATABASE_URL"])
        try:

            async def accept():
                async with database.sessions() as db:
                    person = await db.get(Player, UUID(player["id"]))
                    await enrollment.respond(db, UUID(offer["id"]), person, 1, clock.at, "accept")
                    await db.commit()

            async def signup():
                async with database.sessions() as db:
                    person = await db.get(Player, UUID(actor["id"]))
                    await enrollment.declare(
                        db, UUID(meeting["id"]), person, "going", 1, clock.at, uuid4()
                    )
                    await db.commit()

            await asyncio.gather(accept(), accept(), signup())
        finally:
            await database.engine.dispose()

    asyncio.run(race())
    assert counts(member, meeting) == (14, 0, 1, 0)
    assert own(member, meeting)["allocation"] == "seat"
    assert own(admin, meeting)["allocation"] == "waitlist"


def test_waiting_for_database_lock_cannot_bypass_start_time(calendar_system):
    _, clock, _, _, member, player, meeting, _ = setup_group(calendar_system, 0)

    async def delayed_request():
        from app.api.errors import DomainError

        database = Database(os.environ["VOLLEYCREW_TEST_DATABASE_URL"])
        try:
            async with database.sessions() as holder:
                await enrollment.lock_meeting(holder, UUID(meeting["id"]))

                async def waiting():
                    async with database.sessions() as db:
                        person = await db.get(Player, UUID(player["id"]))
                        await enrollment.declare(
                            db, UUID(meeting["id"]), person, "going", 1, clock, uuid4()
                        )

                task = asyncio.create_task(waiting())
                await asyncio.sleep(0.05)
                clock.at = datetime.fromisoformat(meeting["starts_at"])
                await holder.commit()
                with pytest.raises(DomainError) as failure:
                    await task
                assert failure.value.code == "enrollment_closed"
        finally:
            await database.engine.dispose()

    asyncio.run(delayed_request())
