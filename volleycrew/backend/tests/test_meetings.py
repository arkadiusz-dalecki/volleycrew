import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.database import Database
from app.models.auth import BootstrapGrant
from app.models.meetings import Enrollment, Meeting, ScheduleVersion
from app.services.meetings import resolve
from tests.calendar_support import DEFAULT_ID, reset_calendar
from tests.test_auth import PREFIX, group, login, mutate
from tests.test_auth import system as system  # share guarded *_test DB fixture


@pytest.fixture
def calendar_system(system):
    device, clock = system
    client = device()
    clock.at = datetime(2026, 11, 6, 12, tzinfo=UTC)

    async def prepare():
        async with client.app.state.database.sessions() as db:
            await reset_calendar(db)
            grant = await db.get(BootstrapGrant, 1)
            grant.created_at = clock.at
            grant.expires_at = clock.at + timedelta(minutes=30)
            await db.commit()

    client.portal.call(prepare)
    return system


def read_calendar(client, start="2026-11-01", end="2026-12-01", **query):
    response = client.get(PREFIX + "/calendar", params={"from": start, "to": end, **query})
    assert response.status_code == 200, response.text
    return response.json()


def resolve_day(client, day="2026-11-10", schedule_id=str(DEFAULT_ID)):
    response = mutate(
        client, "/meetings/resolve", {"schedule_version_id": schedule_id, "source_date": day}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_calendar_distant_pagination_does_not_create_meetings(calendar_system):
    _, _, _, _, member, _, _, _ = group(calendar_system)
    first = read_calendar(member, "2040-12-01", "2041-01-01", limit=2)
    second = read_calendar(member, "2040-12-01", "2041-01-01", limit=2, offset=first["next_offset"])
    assert first["total"] >= 4
    assert not {item["id"] for item in first["items"]} & {item["id"] for item in second["items"]}
    assert all(not item["persisted"] for item in first["items"])

    async def count():
        async with member.app.state.database.sessions() as db:
            return await db.scalar(select(func.count()).select_from(Meeting))

    assert member.portal.call(count) == 0
    item = first["items"][0]
    saved = resolve_day(member, item["source_date"])
    assert saved["id"] == item["id"] and saved["persisted"]
    again = read_calendar(member, "2040-12-01", "2041-01-01")
    assert len([row for row in again["items"] if row["id"] == saved["id"]]) == 1
    assert member.portal.call(count) == 1
    for query in [
        {"from": "2026-01-01", "to": "2028-01-01"},
        {"from": "2026-12-01", "to": "2026-11-01"},
        {"from": "2026-11-01", "to": "2026-12-01", "limit": 0},
    ]:
        assert member.get(PREFIX + "/calendar", params=query).status_code == 422


def test_resolve_simultaneous_http_requests_and_database_transactions(calendar_system):
    device, clock, _, _, member, player, _, _ = group(calendar_system)
    other = device()
    assert login(other, player).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(resolve_day, [member, other]))
    assert results[0]["id"] == results[1]["id"]

    async def separate_transactions():
        database = Database(os.environ["VOLLEYCREW_TEST_DATABASE_URL"])
        try:

            async def one():
                async with database.sessions() as db:
                    row = await resolve(db, DEFAULT_ID, date(2026, 11, 17), clock.at)
                    await db.commit()
                    return row.id

            ids = await asyncio.gather(one(), one())
            async with database.sessions() as db:
                count = await db.scalar(select(func.count()).select_from(Meeting))
            assert ids[0] == ids[1] and count == 2
        finally:
            await database.engine.dispose()

    asyncio.run(separate_transactions())


def test_meeting_routes_authentication_and_invalid_occurrences(calendar_system):
    device, _, admin, _, member, player, _, _ = group(calendar_system)
    anonymous = device()
    for path in [
        "/schedule",
        "/players",
        "/calendar?from=2026-11-01&to=2026-12-01",
        "/meetings/next",
        f"/meetings/{uuid4()}",
    ]:
        assert anonymous.get(PREFIX + path).status_code == 401
    assert (
        member.post(
            PREFIX + "/meetings/resolve",
            json={"schedule_version_id": str(DEFAULT_ID), "source_date": "2026-11-10"},
        ).status_code
        == 403
    )
    for day, identifier, status in [
        ("2026-11-11", DEFAULT_ID, 409),
        ("2026-11-03", DEFAULT_ID, 409),
        ("2026-11-10", uuid4(), 404),
    ]:
        assert (
            mutate(
                member,
                "/meetings/resolve",
                {"schedule_version_id": str(identifier), "source_date": day},
            ).status_code
            == status
        )
    assert (
        mutate(
            member,
            "/meetings/resolve",
            {"schedule_version_id": str(DEFAULT_ID), "source_date": "2026-11-10", "capacity": 100},
        ).status_code
        == 422
    )
    assert member.get(PREFIX + f"/meetings/{uuid4()}").status_code == 404
    assert (
        mutate(admin, f"/admin/players/{player['id']}", {"is_active": False}, "PATCH").status_code
        == 200
    )
    assert (
        mutate(
            member,
            "/meetings/resolve",
            {"schedule_version_id": str(DEFAULT_ID), "source_date": "2026-11-10"},
        ).status_code
        == 401
    )


def test_moved_cancelled_and_historical_meetings_override_virtual_dates(calendar_system):
    _, clock, _, _, member, _, _, _ = group(calendar_system)
    moved = resolve_day(member)
    cancelled = resolve_day(member, "2026-11-17")

    async def edit():
        async with member.app.state.database.sessions() as db:
            row = await db.get(Meeting, UUID(moved["id"]))
            row.starts_at = datetime(2026, 12, 2, 17, tzinfo=UTC)
            row.ends_at = row.starts_at + timedelta(hours=2)
            row.term_version += 1
            cancel = await db.get(Meeting, UUID(cancelled["id"]))
            cancel.status = "cancelled"
            await db.commit()

    member.portal.call(edit)
    november = read_calendar(member)["items"]
    assert moved["id"] not in [row["id"] for row in november]
    assert next(row for row in november if row["id"] == cancelled["id"])["status"] == "cancelled"
    december = read_calendar(member, "2026-12-01", "2027-01-01")["items"]
    assert len([row for row in december if row["id"] == moved["id"]]) == 1
    assert member.get(PREFIX + "/meetings/next").json()["source_date"] == "2026-11-24"
    clock.at = datetime(2026, 12, 3, 12, tzinfo=UTC)
    detail = member.get(PREFIX + f"/meetings/{moved['id']}").json()
    assert detail["id"] == moved["id"] and detail["source_date"] == "2026-11-10"
    assert detail["term_version"] == 2
    assert len(read_calendar(member)["items"]) == 1  # only stored cancelled history
    assert resolve_day(member, "2026-11-10")["id"] == moved["id"]


def test_schedule_new_weekday_boundary_and_empty_next(calendar_system):
    _, _, _, _, member, _, _, _ = group(calendar_system)
    new_id = uuid4()

    async def change():
        async with member.app.state.database.sessions() as db:
            old = await db.get(ScheduleVersion, DEFAULT_ID)
            old.effective_until = date(2026, 11, 15)
            await db.flush()
            db.add(
                ScheduleVersion(
                    id=new_id,
                    effective_from=date(2026, 11, 15),
                    effective_until=date(2026, 12, 1),
                    weekday=3,
                    local_time=time(19, 30),
                    duration_minutes=120,
                    timezone="Europe/Warsaw",
                    venue="Nowa sala",
                    created_at=datetime.now(UTC),
                )
            )
            await db.commit()

    member.portal.call(change)
    items = read_calendar(member)["items"]
    assert [row["source_date"] for row in items] == ["2026-11-10", "2026-11-19", "2026-11-26"]
    assert items[1]["starts_at"].startswith("2026-11-19T18:30") and items[1]["venue"] == "Nowa sala"
    assert (
        mutate(
            member,
            "/meetings/resolve",
            {"schedule_version_id": str(DEFAULT_ID), "source_date": "2026-11-17"},
        ).status_code
        == 409
    )
    assert resolve_day(member, "2026-11-19", str(new_id))["id"] == items[1]["id"]
    assert read_calendar(member, "2030-01-01", "2030-02-01")["items"] == []

    async def close():
        async with member.app.state.database.sessions() as db:
            await db.execute(delete(Meeting))
            await db.execute(delete(ScheduleVersion))
            await db.commit()

    member.portal.call(close)
    assert member.get(PREFIX + "/meetings/next").json() is None


def test_rosters_and_group_directory_never_expose_priority_or_credentials(calendar_system):
    _, clock, _, actor, member, player, _, _ = group(calendar_system)
    saved = resolve_day(member)

    async def enroll():
        async with member.app.state.database.sessions() as db:
            for index, person in enumerate([actor, player]):
                db.add(
                    Enrollment(
                        meeting_id=UUID(saved["id"]),
                        player_id=UUID(person["id"]),
                        declaration="going",
                        allocation="seat" if index == 0 else "waitlist",
                        declared_at=clock.at,
                        confirmed_term_version=1,
                    )
                )
            await db.commit()

    member.portal.call(enroll)
    response = member.get(PREFIX + f"/meetings/{saved['id']}")
    body = response.json()
    assert body["participant_count"] == 1 and body["waitlist_count"] == 1
    assert body["participants"][0]["last_name"] == "Dalecki"
    assert body["waitlist"][0]["last_name"] == "Nowak"
    for path in [
        f"/meetings/{saved['id']}",
        "/players",
        "/meetings/next",
        "/calendar?from=2026-11-01&to=2026-12-01",
    ]:
        response = member.get(PREFIX + path)
        assert response.status_code == 200
        assert not any(
            key in response.text
            for key in ["priority_status", "pin_hash", '"role"', "accepted_late_offer"]
        )
    directory = member.get(PREFIX + "/players?limit=1").json()
    assert directory["total"] == 2 and directory["next_offset"] == 1
    assert len(directory["items"]) == 1


def test_schedule_versions_cannot_overlap_at_database_level(calendar_system):
    device, _ = calendar_system
    client = device()

    async def overlap():
        async with client.app.state.database.sessions() as db:
            db.add(
                ScheduleVersion(
                    effective_from=date(2026, 11, 1),
                    weekday=3,
                    local_time=time(18),
                    duration_minutes=120,
                    timezone="Europe/Warsaw",
                    venue="Test",
                    created_at=datetime.now(UTC),
                )
            )
            with pytest.raises(IntegrityError):
                await db.commit()

    client.portal.call(overlap)
