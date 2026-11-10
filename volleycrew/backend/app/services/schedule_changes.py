from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from app.api.errors import DomainError
from app.api.meeting_schemas import ScheduleView
from app.api.schedule_schemas import PlannedMeeting, SchedulePreview, ScheduleSettings
from app.core.security import token_hash
from app.domain.schedule import Rule, first_date_on_or_after, occurrence, occurrences
from app.models.enrollment import SeatOffer
from app.models.meetings import Meeting, ScheduleVersion
from app.models.schedule import MeetingTermRevision, ScheduleState
from app.services import enrollment
from app.services.auth import audit

ZONE = ZoneInfo("Europe/Warsaw")


async def state_lock(db):
    return await db.scalar(
        select(ScheduleState)
        .where(ScheduleState.id == 1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def settings(db):
    state = await db.get(ScheduleState, 1)
    rules = (
        await db.scalars(
            select(ScheduleVersion)
            .where(ScheduleVersion.superseded.is_(False))
            .order_by(ScheduleVersion.effective_from)
        )
    ).all()
    return ScheduleSettings(
        version=state.version, rules=[ScheduleView.model_validate(row) for row in rules]
    )


def conflict():
    raise DomainError(
        409,
        "version_conflict",
        "Dane zmieniły się w innej karcie. Odśwież podgląd przed zatwierdzeniem.",
    )


def check_future(row, expected, at):
    if row.version != expected:
        conflict()
    if row.status not in {"scheduled", "cancelled"} or row.starts_at <= at:
        raise DomainError(
            409, "meeting_locked", "Zmiana dotyczy wyłącznie przyszłego, nierozpoczętego spotkania."
        )


def proposed_occurrence(body, identifier=None):
    return Rule(
        identifier or uuid4(),
        body.effective_from,
        body.effective_until,
        body.weekday,
        body.local_time,
        body.duration_minutes,
        "Europe/Warsaw",
        body.venue,
    )


def validate_rule(rule):
    # Validate the complete Gregorian calendar cycle, not just the next few weeks.
    # DST-ambiguous 02:xx Sundays are rejected rather than silently shifting a meeting.
    try:
        cycle = Rule(
            rule.id,
            date(2000, 1, 1),
            date(2400, 1, 1),
            rule.weekday,
            rule.local_time,
            rule.duration_minutes,
            rule.timezone,
            rule.venue,
        )
        occurrences(cycle, cycle.effective_from, cycle.effective_until)
    except ValueError as exc:
        raise DomainError(
            422,
            "ambiguous_schedule",
            "Wybrana godzina jest niejednoznaczna lub nie istnieje w dniu zmiany czasu. "
            "Wybierz inną godzinę.",
        ) from exc


async def change_term(db, row, start, end, actor_id, at, venue=None, cancel=False):
    from app.models.room import Attendance

    await db.execute(
        delete(Attendance).where(
            Attendance.meeting_id == row.id, Attendance.confirmed_state.is_(None)
        )
    )
    old_start, old_end = row.starts_at, row.ends_at
    row.previous_starts_at, row.previous_ends_at = old_start, old_end
    row.starts_at, row.ends_at = start, end
    if venue is not None:
        row.venue = venue
    row.term_version += 1
    row.version += 1
    if cancel:
        row.status = "cancelled"
    db.add(
        MeetingTermRevision(
            meeting_id=row.id,
            term_version=row.term_version,
            action="cancelled" if cancel else "rescheduled",
            previous_starts_at=old_start,
            previous_ends_at=old_end,
            starts_at=start,
            ends_at=end,
            actor_id=actor_id,
            created_at=at,
        )
    )
    pairs = await enrollment.entries(db, row)
    # Retire old proposals first; the unique active-offer index can then accept replacements.
    old_offers = (
        await db.scalars(
            select(SeatOffer).where(
                SeatOffer.meeting_id == row.id, SeatOffer.state.in_(enrollment.ACTIVE_OFFERS)
            )
        )
    ).all()
    for offer in old_offers:
        offer.state, offer.responded_at = "revoked", at
    await db.flush()
    for entry, player in pairs:
        if entry.declaration != "going":
            continue
        if cancel or row.status == "cancelled":
            # Preserve the declaration/history but release every allocation; no absence event.
            entry.allocation, entry.reservation_kind = "none", None
            entry.reconfirmation_required = False
        else:
            entry.reconfirmation_required = True
            if entry.allocation == "seat" or entry.reservation_kind == "reconfirmation":
                entry.allocation, entry.reservation_kind = "reserved", "reconfirmation"
            elif entry.allocation == "reserved" and entry.reservation_kind == "offer":
                db.add(
                    SeatOffer(
                        meeting_id=row.id,
                        player_id=player.id,
                        enrollment_sequence=entry.queue_number,
                        term_version=row.term_version,
                        state="reserved",
                        reserved_at=at,
                    )
                )
        entry.accepted_late_offer = False
        enrollment.event(
            db,
            row,
            player.id,
            actor_id,
            "meeting_cancelled" if cancel else "term_changed",
            at,
            term_version=row.term_version,
            previous_starts_at=old_start.isoformat(),
            starts_at=start.isoformat(),
        )
    audit(db, actor_id, "cancel_meeting" if cancel else "reschedule_meeting", row.id, at)


async def check_virtual_overlap(db, row, start, end):
    from app.services.meetings import rule_of

    first = start.astimezone(ZONE).date() - timedelta(days=1)
    last = end.astimezone(ZONE).date() + timedelta(days=1)
    rules = (
        await db.scalars(select(ScheduleVersion).where(ScheduleVersion.superseded.is_(False)))
    ).all()
    overrides = set(
        (await db.execute(select(Meeting.calendar_schedule_id, Meeting.calendar_source_date))).all()
    )
    for source in rules:
        for candidate in occurrences(rule_of(source), first, last):
            key = (candidate.schedule_version_id, candidate.source_date)
            if key in overrides:
                continue
            if candidate.starts_at < end and candidate.ends_at > start:
                raise DomainError(
                    409,
                    "schedule_collision",
                    "Ten czas zajmuje inny termin harmonogramu. Najpierw go zmień lub odwołaj.",
                )


async def reschedule(db, meeting_id, body, actor_id, clock):
    await state_lock(db)  # Same order as bulk schedule mutations, before Meeting.
    row = await enrollment.lock_meeting(db, meeting_id)
    at = enrollment.current_time(clock)
    check_future(row, body.expected_version, at)
    if row.status == "cancelled":
        raise DomainError(409, "meeting_cancelled", "Nie można przesunąć odwołanego spotkania.")
    try:
        rule = Rule(
            uuid4(),
            body.local_date,
            None,
            body.local_date.weekday(),
            body.local_time,
            body.duration_minutes,
            "Europe/Warsaw",
            row.venue,
        )
        item = occurrence(rule, body.local_date)
    except ValueError as exc:
        raise DomainError(
            422, "invalid_local_time", "Wybrana godzina nie istnieje lub jest niejednoznaczna."
        ) from exc
    if item.starts_at <= at:
        raise DomainError(422, "past_term", "Nowy termin musi być w przyszłości.")
    overlap = await db.scalar(
        select(Meeting.id)
        .where(
            Meeting.id != row.id,
            Meeting.status != "cancelled",
            Meeting.starts_at < item.ends_at,
            Meeting.ends_at > item.starts_at,
        )
        .limit(1)
    )
    if overlap:
        raise DomainError(409, "schedule_collision", "Nowy termin nakłada się na inne spotkanie.")
    if row.starts_at == item.starts_at and row.ends_at == item.ends_at:
        return row
    row.is_exception = True
    # A generated slot is still an occupied schedule slot, even before materialization.
    await check_virtual_overlap(db, row, item.starts_at, item.ends_at)
    await change_term(db, row, item.starts_at, item.ends_at, actor_id, at)
    return row


async def cancel(db, meeting_id, body, actor_id, clock):
    await state_lock(db)
    row = await enrollment.lock_meeting(db, meeting_id)
    at = enrollment.current_time(clock)
    check_future(row, body.expected_version, at)
    if row.status == "cancelled":
        return row
    await change_term(db, row, row.starts_at, row.ends_at, actor_id, at, cancel=True)
    return row


async def preview(db, body, clock):
    state = await state_lock(db)
    if body.expected_version != state.version:
        conflict()
    at = enrollment.current_time(clock)
    if body.effective_from < at.astimezone(ZONE).date() or body.effective_from.year > 9997:
        raise DomainError(
            422, "past_schedule", "Wybierz dzisiejszą lub przyszłą datę obowiązywania."
        )
    if body.effective_until and (
        body.effective_until <= body.effective_from or body.effective_until.year > 9998
    ):
        raise DomainError(422, "invalid_range", "Koniec serii musi być późniejszy niż początek.")
    rule = proposed_occurrence(body)
    if (
        rule.effective_until
        and first_date_on_or_after(rule.effective_from, rule.weekday) >= rule.effective_until
    ):
        raise DomainError(422, "empty_schedule", "W tym zakresie nie ma wybranego dnia tygodnia.")
    validate_rule(rule)
    boundary = datetime.combine(body.effective_from, datetime.min.time(), ZONE).astimezone(UTC)
    rows = (
        await db.scalars(
            select(Meeting)
            .where(
                Meeting.starts_at > at,
                Meeting.is_additional.is_(False),
                (Meeting.calendar_source_date >= body.effective_from)
                | (Meeting.starts_at >= boundary),
            )
            .order_by(Meeting.id)
            .with_for_update()
        )
    ).all()
    at = enrollment.current_time(clock)
    planned, bindings = [], {}
    for row in rows:
        if body.effective_until and row.calendar_source_date >= body.effective_until:
            continue
        if row.status not in {"scheduled", "cancelled"}:
            raise DomainError(
                409,
                "meeting_locked",
                "Jedno z przyszłych spotkań jest już obsługiwane. Zmień zakres harmonogramu.",
            )
        base = (
            row.calendar_source_date
            if row.calendar_source_date >= body.effective_from
            else row.starts_at.astimezone(ZONE).date()
        )
        day = base - timedelta(days=base.weekday()) + timedelta(days=body.weekday)
        if day < body.effective_from or (body.effective_until and day >= body.effective_until):
            raise DomainError(
                409,
                "schedule_boundary_conflict",
                "Nowy dzień przeniósłby istniejące spotkanie przed datę obowiązywania. "
                "Wybierz początek tygodnia lub późniejszy zakres.",
            )
        if day in bindings:
            raise DomainError(
                409,
                "schedule_collision",
                "Dwa istniejące spotkania trafiłyby na ten sam termin. "
                "Popraw zakres lub indywidualne terminy.",
            )
        bindings[day] = row.id
        item = occurrence(rule, day)
        start, end = (
            (row.starts_at, row.ends_at) if row.is_exception else (item.starts_at, item.ends_at)
        )
        if start <= at:
            raise DomainError(
                409,
                "past_term",
                "Zmiana przeniosłaby spotkanie w przeszłość. Wybierz późniejszy zakres.",
            )
        pairs = await enrollment.entries(db, row)
        changed = (start, end, body.venue) != (
            row.starts_at,
            row.ends_at,
            row.venue,
        ) and not row.is_exception
        count = (
            sum(entry.declaration == "going" for entry, _ in pairs)
            if changed and row.status != "cancelled"
            else 0
        )
        planned.append(
            PlannedMeeting(
                id=row.id,
                version=row.version,
                previous_starts_at=row.starts_at,
                starts_at=start,
                ends_at=end,
                status=row.status,
                kept_exception=row.is_exception,
                reconfirmation_count=count,
                deleted=row.deleted_at is not None,
            )
        )
    for index, item in enumerate(planned):
        if item.status == "cancelled":
            continue
        if any(
            other.status != "cancelled"
            and other.id != item.id
            and item.starts_at < other.ends_at
            and item.ends_at > other.starts_at
            for other in planned[index + 1 :]
        ):
            raise DomainError(
                409, "schedule_collision", "Przesunięte spotkania nakładałyby się na siebie."
            )
    # Check generated slots too: a kept exception from another week must not
    # silently duplicate an occurrence which has not been materialized yet.
    planned_ids = {item.id for item in planned}
    untouched = (
        await db.scalars(
            select(Meeting).where(
                Meeting.ends_at > at, Meeting.status != "cancelled", Meeting.id.notin_(planned_ids)
            )
        )
    ).all()
    for other in untouched:
        window_start = other.starts_at.astimezone(ZONE).date() - timedelta(days=1)
        window_end = other.ends_at.astimezone(ZONE).date() + timedelta(days=1)
        if any(
            generated.source_date not in bindings
            and generated.starts_at < other.ends_at
            and generated.ends_at > other.starts_at
            for generated in occurrences(rule, window_start, window_end)
        ):
            raise DomainError(409, "schedule_collision", "Seria nakłada się na inne spotkanie.")
    for item in planned:
        if item.status == "cancelled":
            continue
        if any(
            item.starts_at < other.ends_at and item.ends_at > other.starts_at for other in untouched
        ):
            raise DomainError(
                409,
                "schedule_collision",
                "Nowy termin nakłada się na spotkanie poza zmienianym zakresem.",
            )
        window_start = item.starts_at.astimezone(ZONE).date() - timedelta(days=1)
        window_end = item.ends_at.astimezone(ZONE).date() + timedelta(days=1)
        for generated in occurrences(rule, window_start, window_end):
            if (
                generated.source_date not in bindings
                and generated.starts_at < item.ends_at
                and generated.ends_at > item.starts_at
            ):
                raise DomainError(
                    409,
                    "schedule_collision",
                    "Zachowany wyjątek nakłada się na nowy termin reguły. "
                    "Popraw wyjątek lub zakres zmiany.",
                )
    rules = (
        await db.scalars(
            select(ScheduleVersion)
            .where(ScheduleVersion.superseded.is_(False))
            .order_by(ScheduleVersion.effective_from)
        )
    ).all()
    # Date ranges do not prevent an overnight meeting at a range boundary
    # from overlapping a slot preserved before/after the replacement.
    from app.services.meetings import rule_of

    override_keys = set(
        (await db.execute(select(Meeting.calendar_schedule_id, Meeting.calendar_source_date))).all()
    )
    boundary_candidates = [item for item in planned if item.status != "cancelled"]
    for edge in (body.effective_from, body.effective_until):
        if edge:
            boundary_candidates.extend(
                item
                for item in occurrences(rule, edge - timedelta(days=1), edge + timedelta(days=2))
                if item.source_date not in bindings
            )
    for candidate in boundary_candidates:
        first = candidate.starts_at.astimezone(ZONE).date() - timedelta(days=1)
        last = candidate.ends_at.astimezone(ZONE).date() + timedelta(days=1)
        for old in rules:
            for kept in occurrences(rule_of(old), first, last):
                outside = kept.source_date < body.effective_from or (
                    body.effective_until and kept.source_date >= body.effective_until
                )
                if (
                    outside
                    and (old.id, kept.source_date) not in override_keys
                    and candidate.starts_at < kept.ends_at
                    and candidate.ends_at > kept.starts_at
                ):
                    raise DomainError(
                        409,
                        "schedule_collision",
                        "Seria nakłada się na termin poza zmienianym zakresem.",
                    )
    payload = body.model_dump(mode="json", exclude={"preview_token"})
    payload["existing"] = [item.model_dump(mode="json") for item in planned]
    payload["rules"] = [ScheduleView.model_validate(item).model_dump(mode="json") for item in rules]
    import json

    digest = token_hash(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    first = first_date_on_or_after(
        max(body.effective_from, at.astimezone(ZONE).date()), body.weekday
    )
    examples = [
        item.starts_at
        for item in occurrences(rule, first, first + timedelta(days=56))
        if item.starts_at > at
    ]
    return SchedulePreview(
        version=state.version,
        preview_token=digest,
        existing=planned,
        examples=examples,
        reconfirmation_count=sum(item.reconfirmation_count for item in planned),
        kept_exception_count=sum(item.kept_exception for item in planned),
    ), bindings


async def apply(db, body, actor_id, clock):
    shown, bindings = await preview(db, body, clock)
    if shown.preview_token != body.preview_token:
        conflict()
    at = enrollment.current_time(clock)
    state = await db.get(ScheduleState, 1)
    old_rules = (
        await db.scalars(
            select(ScheduleVersion)
            .where(ScheduleVersion.superseded.is_(False))
            .order_by(ScheduleVersion.effective_from)
            .with_for_update()
        )
    ).all()
    for old in old_rules:
        if old.effective_until and old.effective_until <= body.effective_from:
            continue
        if body.effective_until and old.effective_from >= body.effective_until:
            continue
        # Preserve the original schedule after a bounded replacement, including
        # materialized occurrences and their stable public/source identities.
        tail = None
        if body.effective_until and (
            old.effective_until is None or old.effective_until > body.effective_until
        ):
            tail = ScheduleVersion(
                id=uuid4(),
                effective_from=body.effective_until,
                effective_until=old.effective_until,
                weekday=old.weekday,
                local_time=old.local_time,
                duration_minutes=old.duration_minutes,
                timezone=old.timezone,
                venue=old.venue,
                created_at=at,
            )
        if old.effective_from >= body.effective_from:
            old.superseded = True
        else:
            old.effective_until = body.effective_from
        await db.flush()
        if tail:
            db.add(tail)
            await db.flush()
            following = (
                await db.scalars(
                    select(Meeting)
                    .where(
                        Meeting.calendar_schedule_id == old.id,
                        Meeting.calendar_source_date >= body.effective_until,
                    )
                    .with_for_update()
                )
            ).all()
            for row in following:
                row.calendar_schedule_id = tail.id
    await db.flush()
    new = ScheduleVersion(
        id=uuid4(),
        effective_from=body.effective_from,
        effective_until=body.effective_until,
        weekday=body.weekday,
        local_time=body.local_time,
        duration_minutes=body.duration_minutes,
        timezone="Europe/Warsaw",
        venue=body.venue,
        created_at=at,
    )
    db.add(new)
    await db.flush()
    dates = {identifier: day for day, identifier in bindings.items()}
    for item in shown.existing:
        row = (
            await db.get(Meeting, item.id)
            if item.deleted
            else await enrollment.lock_meeting(db, item.id)
        )
        row.calendar_schedule_id, row.calendar_source_date = new.id, dates[row.id]
        if (
            not row.deleted_at
            and not item.kept_exception
            and (row.starts_at, row.ends_at, row.venue)
            != (
                item.starts_at,
                item.ends_at,
                body.venue,
            )
        ):
            await change_term(db, row, item.starts_at, item.ends_at, actor_id, at, venue=body.venue)
    state.version += 1
    audit(
        db,
        actor_id,
        "change_schedule",
        new.id,
        at,
        {"effective_from": body.effective_from.isoformat()},
    )
    return await settings(db)


async def release(db, meeting_id, body, actor_id, clock):
    meeting = await enrollment.lock_meeting(db, meeting_id)
    at = enrollment.current_time(clock)
    check_future(meeting, body.expected_version, at)
    pairs = await enrollment.entries(db, meeting)
    entry = next((entry for entry, _ in pairs if entry.player_id == body.player_id), None)
    if not entry or entry.allocation != "reserved" or entry.reservation_kind != "reconfirmation":
        raise DomainError(
            409, "no_reservation", "Ta osoba nie ma miejsca oczekującego na ponowne potwierdzenie."
        )
    entry.declaration, entry.allocation, entry.reservation_kind = "withdrawn", "none", None
    entry.reconfirmation_required = False
    entry.confirmed_term_version = None
    entry.accepted_late_offer = False
    enrollment.event(db, meeting, entry.player_id, actor_id, "reconfirmation_released", at)
    await enrollment.rebalance(db, meeting, actor_id, at)
    meeting.version += 1
    return meeting


async def create_meeting(db, body, actor_id, clock):
    state = await state_lock(db)
    if state.version != body.expected_version:
        conflict()
    at = enrollment.current_time(clock)
    try:
        rule = Rule(
            uuid4(),
            body.local_date,
            body.local_date + timedelta(days=1),
            body.local_date.weekday(),
            body.local_time,
            body.duration_minutes,
            "Europe/Warsaw",
            body.venue,
        )
        item = occurrence(rule, body.local_date)
    except (ValueError, OverflowError) as exc:
        raise DomainError(
            422, "invalid_local_time", "Wybrana data lub godzina jest nieprawidłowa."
        ) from exc
    if item.starts_at <= at:
        raise DomainError(422, "past_term", "Nowy termin musi być w przyszłości.")
    overlap = await db.scalar(
        select(Meeting.id)
        .where(
            Meeting.status != "cancelled",
            Meeting.starts_at < item.ends_at,
            Meeting.ends_at > item.starts_at,
        )
        .limit(1)
    )
    if overlap:
        raise DomainError(409, "schedule_collision", "Ten czas zajmuje inne spotkanie.")
    await check_virtual_overlap(db, None, item.starts_at, item.ends_at)
    db.add(
        ScheduleVersion(
            **{key: getattr(rule, key) for key in Rule.__dataclass_fields__},
            superseded=True,
            created_at=at,
        )
    )
    await db.flush()
    row = Meeting(
        **{key: getattr(item, key) for key in item.__dataclass_fields__},
        calendar_schedule_id=rule.id,
        calendar_source_date=body.local_date,
        is_additional=True,
        is_exception=True,
        created_at=at,
    )
    db.add(row)
    state.version += 1
    audit(db, actor_id, "create_meeting", row.id, at)
    await db.flush()
    return row


async def delete_meeting(db, meeting_id, body, actor_id, clock):
    await state_lock(db)
    row = await enrollment.lock_meeting(db, meeting_id)
    at = enrollment.current_time(clock)
    if row.version != body.expected_version:
        conflict()
    await hide_meeting(db, row, actor_id, at)
    state = await db.get(ScheduleState, 1)
    state.version += 1


async def hide_meeting(db, row, actor_id, at):
    if row.deleted_at:
        return
    if row.status != "cancelled":
        check_future(row, row.version, at)
        await change_term(db, row, row.starts_at, row.ends_at, actor_id, at, cancel=True)
    else:
        row.version += 1
    row.deleted_at = at
    audit(db, actor_id, "delete_meeting", row.id, at)
