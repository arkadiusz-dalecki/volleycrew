from datetime import time, timedelta
from uuid import uuid4

from app.domain.schedule import first_date_on_or_after, occurrence
from app.models.auth import Player
from app.models.meetings import Meeting, ScheduleVersion
from app.models.settlements import MeetingCharge
from app.services.enrollment import declare
from app.services.meetings import rule_of


async def seed_settlements(db, admin, at):
    return {
        project: await seed_project(db, admin, at, project, index)
        for index, project in enumerate(("desktop", "mobile", "webkit"))
    }


async def seed_project(db, admin, at, project, index):
    first_day = first_date_on_or_after(at.date() + timedelta(weeks=56 + index * 12), 2)
    schedule = ScheduleVersion(
        effective_from=first_day,
        weekday=2,
        local_time=time(12),
        duration_minutes=120,
        timezone="Europe/Warsaw",
        venue="Sala testowa",
        created_at=at,
        superseded=True,
    )
    db.add(schedule)
    await db.flush()

    async def new_player(key, name):
        player = Player(
            username=f"wallet-{project}-{key}",
            first_name=name,
            last_name=f"Rozliczenia {project}",
            priority_status="guest",
            role="player",
            password_hash=admin.password_hash,
            created_at=at,
        )
        db.add(player)
        await db.flush()
        return player

    first = await new_player("first", "Alicja")
    second = await new_player("second", "Bartek")
    additional = [await new_player(str(number), f"Grający {number}") for number in range(1, 13)]

    async def meeting(offset, cost, attendees=(), starts_minutes=None):
        source_day = first_day + timedelta(weeks=offset)
        slot = occurrence(rule_of(schedule), source_day)
        row = Meeting(
            id=slot.id,
            schedule_version_id=schedule.id,
            source_date=source_day,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            timezone=slot.timezone,
            venue=slot.venue,
            calendar_schedule_id=schedule.id,
            calendar_source_date=source_day,
            is_additional=True,
            is_exception=True,
            created_at=at,
        )
        db.add(row)
        await db.flush()
        for player in attendees:
            await declare(db, row.id, player, "going", 1, at, uuid4())
        if cost is not None:
            row.cost_grosz = cost
            row.cost_overridden = True
        if starts_minutes is not None:
            row.starts_at = at + timedelta(minutes=starts_minutes)
            row.ends_at = row.starts_at + timedelta(hours=2)
            row.is_exception = True
        await db.flush()
        return row

    exact = await meeting(0, 20000, [first, *additional], -21 * 1440)
    payer = await new_player("payer", "Celina")
    correction = await meeting(1, 20000, [payer, *additional[:3]], -22 * 1440)
    free = await meeting(2, 0, [second], -23 * 1440)
    no_cost = await meeting(11, None, [second], -24 * 1440)
    cancelled = await meeting(3, 20000, [second])
    charges = []
    for offset, amount, player, age_hours in [
        (4, 4000, first, 0),
        (5, 3000, first, 0),
        (6, 2000, first, 0),
        (7, 10000, second, 0),
        (8, 1, second, 0),
        (9, 500, second, 30 * 24 + 2),
        (10, 500, second, 30 * 24 - 2),
    ]:
        row = await meeting(offset, amount, starts_minutes=-1440 * (offset + 31))
        row.status = "attendance_checked"
        row.attendance_confirmed_at = at - timedelta(hours=age_hours)
        row.attendance_revision = 1
        db.add(
            MeetingCharge(
                meeting_id=row.id,
                player_id=player.id,
                amount=amount,
                posted_at=row.attendance_confirmed_at,
            )
        )
        charges.append(str(row.id))
    series_start = first_date_on_or_after(first_day + timedelta(weeks=80), 1)
    return {
        "first": first.username,
        "second": second.username,
        "payer": payer.username,
        "payer_id": str(payer.id),
        "first_id": str(first.id),
        "second_id": str(second.id),
        "exact": str(exact.id),
        "free": str(free.id),
        "no_cost": str(no_cost.id),
        "correction": str(correction.id),
        "cancelled": str(cancelled.id),
        "charges": charges,
        "series_start": series_start.isoformat(),
    }
