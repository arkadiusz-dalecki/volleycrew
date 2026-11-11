"""Mutations of a selected recurring rule, preserving past games and occurrence markers."""

import json
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import or_, select

from app.api.errors import DomainError
from app.api.schedule_schemas import SeriesChangePreview
from app.core.security import token_hash
from app.domain.schedule import first_date_on_or_after, occurrence, occurrences
from app.models.meetings import Meeting, ScheduleVersion
from app.services import enrollment
from app.services import schedule_changes as changes
from app.services.auth import audit
from app.services.meetings import rule_of


def overlaps(first, second):
    return first.starts_at < second.ends_at and first.ends_at > second.starts_at


async def plan(db, rule_id, body, clock, remove=False):
    state = await changes.state_lock(db)
    if body.expected_version != state.version:
        changes.conflict()
    old = await db.scalar(
        select(ScheduleVersion).where(ScheduleVersion.id == rule_id).with_for_update()
    )
    at = enrollment.current_time(clock)
    today = at.astimezone(changes.ZONE).date()
    if not old or old.superseded or (old.effective_until and old.effective_until <= today):
        raise DomainError(404, "not_found", "Nie znaleziono przyszłej serii spotkań.")
    cutoff = max(today, old.effective_from)
    # A game which has already started today belongs to preserved history.
    if cutoff == today and today.weekday() == old.weekday:
        if occurrence(rule_of(old), today).starts_at <= at:
            cutoff += timedelta(days=1)
    if old.effective_until and cutoff >= old.effective_until:
        raise DomainError(409, "series_finished", "Ta seria nie ma już przyszłych terminów.")
    proposed = None
    if not remove:
        if body.effective_from < cutoff or body.effective_from.year > 9997:
            raise DomainError(
                422, "past_schedule", "Początek zmienionej serii musi być w przyszłości."
            )
        if body.effective_until and (
            body.effective_until <= body.effective_from or body.effective_until.year > 9998
        ):
            raise DomainError(
                422, "invalid_range", "Koniec serii musi być późniejszy niż początek."
            )
        proposed = changes.proposed_occurrence(body)
        if (
            proposed.effective_until
            and first_date_on_or_after(proposed.effective_from, proposed.weekday)
            >= proposed.effective_until
        ):
            raise DomainError(
                422, "empty_schedule", "W tym zakresie nie ma wybranego dnia tygodnia."
            )
        changes.validate_rule(proposed)
        other_rules = (
            await db.scalars(
                select(ScheduleVersion).where(
                    ScheduleVersion.superseded.is_(False), ScheduleVersion.id != old.id
                )
            )
        ).all()
        if any(
            (other.effective_until is None or other.effective_until > proposed.effective_from)
            and (
                proposed.effective_until is None or other.effective_from < proposed.effective_until
            )
            for other in other_rules
        ):
            raise DomainError(409, "schedule_collision", "Zakres nakłada się na inną serię.")
    rows = (
        await db.scalars(
            select(Meeting)
            .where(
                Meeting.calendar_schedule_id == old.id,
                Meeting.is_additional.is_(False),
                or_(Meeting.starts_at > at, Meeting.calendar_source_date >= cutoff),
            )
            .order_by(Meeting.id)
            .with_for_update()
        )
    ).all()
    targets, removed, bindings = {}, [], {}
    reconfirmations, exceptions = 0, 0
    for row in rows:
        if not row.deleted_at and (
            row.status not in {"scheduled", "cancelled"} or row.starts_at <= at
        ):
            raise DomainError(409, "meeting_locked", "Seria obejmuje już rozpoczęte spotkanie.")
        day = row.calendar_source_date
        day = (
            day - timedelta(days=day.weekday()) + timedelta(days=body.weekday) if proposed else day
        )
        in_range = (
            proposed
            and day >= proposed.effective_from
            and (proposed.effective_until is None or day < proposed.effective_until)
        )
        if not in_range:
            removed.append(row)
            continue
        if day in bindings:
            raise DomainError(
                409, "schedule_collision", "Dwa spotkania trafiłyby na ten sam termin."
            )
        bindings[day] = row.id
        item = occurrence(proposed, day)
        target = row if row.is_exception else item
        if not row.deleted_at and target.starts_at <= at:
            raise DomainError(409, "past_term", "Nowy termin musi być w przyszłości.")
        targets[row.id] = (day, target.starts_at, target.ends_at)
        if row.deleted_at:
            continue
        if row.is_exception:
            exceptions += 1
        elif row.status != "cancelled" and (row.starts_at, row.ends_at, row.venue) != (
            target.starts_at,
            target.ends_at,
            body.venue,
        ):
            reconfirmations += sum(
                entry.declaration == "going" for entry, _ in await enrollment.entries(db, row)
            )
    if proposed:
        untouched = (
            await db.scalars(
                select(Meeting).where(
                    Meeting.deleted_at.is_(None),
                    Meeting.status != "cancelled",
                    Meeting.ends_at > at,
                    Meeting.id.notin_([row.id for row in rows]),
                )
            )
        ).all()
        # Check materialized exceptions/additions against the virtual new series.
        kept = [
            row
            for row in rows
            if row.id in targets
            and row.is_exception
            and not row.deleted_at
            and row.status != "cancelled"
        ]
        for other in [*untouched, *kept]:
            first = other.starts_at.astimezone(changes.ZONE).date() - timedelta(days=1)
            last = other.ends_at.astimezone(changes.ZONE).date() + timedelta(days=1)
            if any(
                generated.source_date not in bindings and overlaps(generated, other)
                for generated in occurrences(proposed, first, last)
            ):
                raise DomainError(409, "schedule_collision", "Seria nakłada się na inne spotkanie.")
        active = [
            row
            for row in rows
            if row.id in targets and not row.deleted_at and row.status != "cancelled"
        ]
        for index, row in enumerate(active):
            _, start, end = targets[row.id]
            if any(start < other.ends_at and end > other.starts_at for other in untouched):
                raise DomainError(
                    409, "schedule_collision", "Nowy termin nakłada się na inne spotkanie."
                )
            if any(
                start < targets[other.id][2] and end > targets[other.id][1]
                for other in active[index + 1 :]
            ):
                raise DomainError(
                    409, "schedule_collision", "Nowe terminy nakładają się na siebie."
                )
        # Rules with adjacent date ranges may still overlap across midnight.
        markers = set(
            (
                await db.execute(select(Meeting.calendar_schedule_id, Meeting.calendar_source_date))
            ).all()
        )
        neighbors = [rule_of(other) for other in other_rules]
        if old.effective_from < cutoff:
            neighbors.append(replace(rule_of(old), effective_until=cutoff))
        candidates = [
            SimpleNamespace(starts_at=targets[row.id][1], ends_at=targets[row.id][2])
            for row in active
        ]
        for edge in (proposed.effective_from, proposed.effective_until):
            if edge:
                candidates.extend(
                    item
                    for item in occurrences(
                        proposed, edge - timedelta(days=1), edge + timedelta(days=2)
                    )
                    if item.source_date not in bindings
                )
        for candidate in candidates:
            first = candidate.starts_at.astimezone(changes.ZONE).date() - timedelta(days=1)
            last = candidate.ends_at.astimezone(changes.ZONE).date() + timedelta(days=1)
            for neighbor_rule in neighbors:
                for neighbor in occurrences(neighbor_rule, first, last):
                    if (neighbor_rule.id, neighbor.source_date) not in markers and overlaps(
                        candidate, neighbor
                    ):
                        raise DomainError(
                            409,
                            "schedule_collision",
                            "Seria koliduje na granicy zakresu lub z zachowanym wyjątkiem.",
                        )
    payload = {
        "rule": str(old.id),
        "remove": remove,
        "cutoff": cutoff.isoformat(),
        "body": body.model_dump(mode="json", exclude={"preview_token"}),
        "rows": [
            (str(row.id), row.version, row.term_version, bool(row.deleted_at)) for row in rows
        ],
    }
    digest = token_hash(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    view = SeriesChangePreview(
        version=state.version,
        preview_token=digest,
        affected_count=sum(not row.deleted_at for row in rows),
        removed_count=sum(not row.deleted_at for row in removed),
        reconfirmation_count=reconfirmations,
        kept_exception_count=exceptions,
    )
    return view, state, old, cutoff, rows, targets


async def preview(db, rule_id, body, clock, remove=False):
    return (await plan(db, rule_id, body, clock, remove))[0]


async def apply(db, rule_id, body, actor_id, clock, remove=False):
    shown, state, old, cutoff, rows, targets = await plan(db, rule_id, body, clock, remove)
    if shown.preview_token != body.preview_token:
        changes.conflict()
    at = enrollment.current_time(clock)
    if old.effective_from >= cutoff:
        old.superseded = True
    else:
        old.effective_until = cutoff
    await db.flush()
    new = None
    if not remove:
        proposed = changes.proposed_occurrence(body, uuid4())
        new = ScheduleVersion(
            **{key: getattr(proposed, key) for key in proposed.__dataclass_fields__}, created_at=at
        )
        db.add(new)
        await db.flush()
    for row in rows:
        if row.id not in targets:
            await changes.hide_meeting(db, row, actor_id, at)
            continue
        day, start, end = targets[row.id]
        row.calendar_schedule_id, row.calendar_source_date = new.id, day
        if (
            not row.deleted_at
            and not row.is_exception
            and (row.starts_at, row.ends_at, row.venue) != (start, end, body.venue)
        ):
            await changes.change_term(db, row, start, end, actor_id, at, venue=body.venue)
    state.version += 1
    audit(db, actor_id, "delete_series" if remove else "edit_series", old.id, at)
    await db.flush()
    return await changes.settings(db)
