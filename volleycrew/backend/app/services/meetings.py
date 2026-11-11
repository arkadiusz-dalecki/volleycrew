from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError
from app.api.meeting_schemas import AdjacentMeetings, MeetingDetail, MeetingSummary, PublicPlayer
from app.domain.schedule import Rule, first_date_on_or_after, occurrence, occurrences
from app.models.auth import Player
from app.models.meetings import Enrollment, Meeting, ScheduleVersion
from app.models.schedule import ScheduleState
from app.services.enrollment import order, waiting_order

CALENDAR_ZONE = ZoneInfo("Europe/Warsaw")
RULE_FIELDS = tuple(Rule.__dataclass_fields__)


def rule_of(row: ScheduleVersion) -> Rule:
    return Rule(**{key: getattr(row, key) for key in RULE_FIELDS})


def summary(row, persisted: bool) -> MeetingSummary:
    fields = {
        key: getattr(row, key)
        for key in (
            "id",
            "schedule_version_id",
            "source_date",
            "starts_at",
            "ends_at",
            "timezone",
            "venue",
        )
    }
    return MeetingSummary(
        **fields,
        persisted=persisted,
        **(
            {
                key: getattr(row, key)
                for key in (
                    "status",
                    "term_version",
                    "version",
                    "capacity",
                    "previous_starts_at",
                    "previous_ends_at",
                    "is_exception",
                )
            }
            if persisted
            else {"status": "scheduled", "term_version": 1, "version": 1, "capacity": 14}
        ),
    )


def bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return tuple(
        datetime.combine(day, datetime.min.time(), CALENDAR_ZONE).astimezone(UTC)
        for day in (start, end)
    )


async def calendar(db: AsyncSession, start: date, end: date, at: datetime) -> list[MeetingSummary]:
    await db.scalar(select(ScheduleState).where(ScheduleState.id == 1).with_for_update(read=True))
    lower, upper = bounds(start, end)
    schedules = (
        await db.scalars(
            select(ScheduleVersion).where(
                ScheduleVersion.effective_from < end,
                ScheduleVersion.superseded.is_(False),
                or_(
                    ScheduleVersion.effective_until.is_(None),
                    ScheduleVersion.effective_until > start,
                ),
            )
        )
    ).all()
    stored = (
        await db.scalars(
            select(Meeting).where(
                or_(
                    (Meeting.calendar_source_date >= start) & (Meeting.calendar_source_date < end),
                    (Meeting.starts_at >= lower) & (Meeting.starts_at < upper),
                )
            )
        )
    ).all()
    # Include both sources and actual dates: moved occurrences suppress their old slot.
    overrides = {(row.calendar_schedule_id, row.calendar_source_date) for row in stored}
    result = [
        summary(row, True)
        for row in stored
        if not row.deleted_at and lower <= row.starts_at < upper
    ]
    for schedule in schedules:
        for item in occurrences(rule_of(schedule), start, end):
            if (item.schedule_version_id, item.source_date) not in overrides and item.ends_at > at:
                result.append(summary(item, False))
    return sorted(result, key=lambda item: (item.starts_at, str(item.id)))


async def next_meeting(db: AsyncSession, at: datetime) -> MeetingSummary | None:
    await db.scalar(select(ScheduleState).where(ScheduleState.id == 1).with_for_update(read=True))
    stored = (
        await db.scalars(
            select(Meeting).where(Meeting.ends_at > at).order_by(Meeting.starts_at, Meeting.id)
        )
    ).all()
    candidates = [
        summary(row, True)
        for row in stored
        if not row.deleted_at and row.status not in {"cancelled", "completed"}
    ]
    # A stored override is authoritative even when moved into the past.
    original_dates = set(
        (
            await db.execute(
                select(Meeting.calendar_schedule_id, Meeting.calendar_source_date).where(
                    Meeting.calendar_source_date
                    >= at.astimezone(CALENDAR_ZONE).date() - timedelta(days=1)
                )
            )
        ).all()
    )
    schedules = (
        await db.scalars(
            select(ScheduleVersion).where(
                ScheduleVersion.superseded.is_(False),
                or_(
                    ScheduleVersion.effective_until.is_(None),
                    ScheduleVersion.effective_until
                    > at.astimezone(CALENDAR_ZONE).date() - timedelta(days=1),
                ),
            )
        )
    ).all()
    for schedule in schedules:
        rule = rule_of(schedule)
        day = first_date_on_or_after(
            max(
                rule.effective_from,
                at.astimezone(ZoneInfo(rule.timezone)).date() - timedelta(days=1),
            ),
            rule.weekday,
        )
        while not rule.effective_until or day < rule.effective_until:
            item = occurrence(rule, day)
            if item.ends_at > at and (rule.id, day) not in original_dates:
                candidates.append(summary(item, False))
                break
            day += timedelta(days=7)
    return min(candidates, key=lambda item: (item.starts_at, str(item.id)), default=None)


async def adjacent(
    db: AsyncSession, starts_at: datetime, meeting_id: UUID, at: datetime
) -> AdjacentMeetings:
    await db.scalar(select(ScheduleState).where(ScheduleState.id == 1).with_for_update(read=True))
    stored = (await db.scalars(select(Meeting))).all()
    overrides = {(row.calendar_schedule_id, row.calendar_source_date) for row in stored}
    candidates = [summary(row, True) for row in stored if not row.deleted_at]
    anchor = (starts_at, str(meeting_id))
    schedules = (
        await db.scalars(select(ScheduleVersion).where(ScheduleVersion.superseded.is_(False)))
    ).all()
    for schedule in schedules:
        rule = rule_of(schedule)
        zone = ZoneInfo(rule.timezone)
        # Unmaterialized past occurrences are absent from the calendar too.
        lower = max(rule.effective_from, at.astimezone(zone).date() - timedelta(days=1))
        upper = rule.effective_until or date(9998, 1, 1)
        for direction in (-1, 1):
            day = (
                max(lower, starts_at.astimezone(zone).date())
                if direction == 1
                else min(upper - timedelta(days=1), starts_at.astimezone(zone).date())
            )
            day += (
                timedelta(days=(rule.weekday - day.weekday()) % 7)
                if direction == 1
                else -timedelta(days=(day.weekday() - rule.weekday) % 7)
            )
            while lower <= day < upper:
                item = occurrence(rule, day)
                key = (item.starts_at, str(item.id))
                if (
                    item.ends_at > at
                    and (rule.id, day) not in overrides
                    and (key > anchor if direction == 1 else key < anchor)
                ):
                    candidates.append(summary(item, False))
                    break
                day += timedelta(days=7 * direction)
    previous = max(
        (item for item in candidates if (item.starts_at, str(item.id)) < anchor),
        key=lambda item: (item.starts_at, str(item.id)),
        default=None,
    )
    following = min(
        (item for item in candidates if (item.starts_at, str(item.id)) > anchor),
        key=lambda item: (item.starts_at, str(item.id)),
        default=None,
    )
    items = [item for item in (previous, following) if item is not None]
    await rosters(db, items)
    return AdjacentMeetings(previous=previous, next=following)


async def resolve(db: AsyncSession, version_id: UUID, day: date, at: datetime) -> Meeting:
    # Materialization and bulk changes share the order: state -> rule -> Meeting.
    await db.scalar(select(ScheduleState).where(ScheduleState.id == 1).with_for_update(read=True))
    # Shared rule lock cooperates with E5 schedule-version mutations.
    schedule = await db.scalar(
        select(ScheduleVersion).where(ScheduleVersion.id == version_id).with_for_update(read=True)
    )
    if schedule is None:
        raise DomainError(404, "not_found", "Nie znaleziono harmonogramu.")
    existing = await db.scalar(
        select(Meeting).where(Meeting.schedule_version_id == version_id, Meeting.source_date == day)
    )
    if existing is not None:
        ensure_visible(existing)
        return existing
    bound = await db.scalar(
        select(Meeting).where(
            Meeting.calendar_schedule_id == version_id, Meeting.calendar_source_date == day
        )
    )
    if bound is not None:
        ensure_visible(bound)
        return bound
    if schedule.superseded:
        raise DomainError(
            409, "invalid_occurrence", "Ten harmonogram został zastąpiony. Odśwież kalendarz."
        )
    try:
        item = occurrence(rule_of(schedule), day)
    except ValueError as exc:
        raise DomainError(
            409,
            "invalid_occurrence",
            "Termin nie należy do aktualnego harmonogramu. Odśwież kalendarz.",
        ) from exc
    if item.ends_at <= at:
        raise DomainError(409, "past_occurrence", "Nie można utworzyć zakończonego terminu.")
    fields = {key: getattr(item, key) for key in item.__dataclass_fields__}
    await db.execute(
        insert(Meeting)
        .values(
            **fields,
            calendar_schedule_id=version_id,
            calendar_source_date=day,
            status="scheduled",
            term_version=1,
            version=1,
            capacity=14,
            created_at=at,
        )
        .on_conflict_do_nothing(constraint="meeting_source_unique")
    )
    return await db.scalar(
        select(Meeting).where(Meeting.schedule_version_id == version_id, Meeting.source_date == day)
    )


async def rosters(
    db: AsyncSession, items: list[MeetingSummary]
) -> dict[UUID, tuple[list[PublicPlayer], list[PublicPlayer]]]:
    ids = [item.id for item in items if item.persisted]
    result = {key: ([], []) for key in ids}
    if not ids:
        return result
    rows = (
        await db.execute(
            select(Enrollment, Player)
            .join(Player, Player.id == Enrollment.player_id)
            .where(
                Enrollment.meeting_id.in_(ids),
                Enrollment.declaration == "going",
                Enrollment.allocation.in_(["seat", "waitlist", "reserved"]),
            )
            .order_by(Enrollment.declared_at, Enrollment.queue_number)
        )
    ).all()
    from app.models.room import Attendance

    actual = (
        await db.execute(
            select(Attendance.meeting_id, Player)
            .join(Player, Player.id == Attendance.player_id)
            .where(Attendance.meeting_id.in_(ids), Attendance.confirmed_state == "present")
            .order_by(Player.last_name, Player.first_name, Player.id)
        )
    ).all()
    for item in items:
        if item.id not in result:
            continue
        pairs = [(entry, player) for entry, player in rows if entry.meeting_id == item.id]
        seats = [
            PublicPlayer.model_validate(player)
            for entry, player in sorted(pairs, key=order)
            if entry.allocation == "seat" and entry.confirmed_term_version == item.term_version
        ]
        waiting = [
            PublicPlayer.model_validate(player)
            for entry, player in waiting_order(pairs)
            if entry.reservation_kind != "reconfirmation"
        ]
        if item.status == "completed":
            seats = [
                PublicPlayer.model_validate(person)
                for meeting_id, person in actual
                if meeting_id == item.id
            ]
            waiting = []
        result[item.id] = seats, waiting
        item.participant_count, item.waitlist_count = len(seats), len(waiting)
        item.reserved_count = sum(
            entry.allocation == "reserved"
            or (entry.allocation == "seat" and entry.confirmed_term_version != item.term_version)
            for entry, _ in pairs
        )
        if item.status == "completed":
            item.reserved_count = 0
        item.free_count = max(0, item.capacity - item.participant_count - item.reserved_count)

    return result


def ensure_visible(row: Meeting):
    if row.deleted_at:
        raise DomainError(404, "not_found", "Nie znaleziono spotkania.")


async def detail(db: AsyncSession, row: Meeting) -> MeetingDetail:
    ensure_visible(row)
    item = summary(row, True)
    roster = (await rosters(db, [item]))[row.id]
    pending = (
        await db.scalars(
            select(Player)
            .join(Enrollment, Enrollment.player_id == Player.id)
            .where(
                Enrollment.meeting_id == row.id,
                Enrollment.declaration == "going",
                Enrollment.reservation_kind == "reconfirmation",
            )
            .order_by(Enrollment.declared_at, Enrollment.queue_number)
        )
    ).all()
    return MeetingDetail(
        **item.model_dump(),
        participants=roster[0],
        waitlist=roster[1],
        awaiting_confirmation=[PublicPlayer.model_validate(player) for player in pending],
    )
