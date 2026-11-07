"""Pure local-date recurrence. No persistence, HTTP or server-local timezone."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

OCCURRENCE_NAMESPACE = UUID("ee37b8c9-6ff1-45bc-b264-108036a9457b")


@dataclass(frozen=True)
class Rule:
    id: UUID
    effective_from: date
    effective_until: date | None
    weekday: int
    local_time: time
    duration_minutes: int
    timezone: str
    venue: str


@dataclass(frozen=True)
class Occurrence:
    id: UUID
    schedule_version_id: UUID
    source_date: date
    starts_at: datetime
    ends_at: datetime
    timezone: str
    venue: str


def first_date_on_or_after(day: date, weekday: int) -> date:
    return day + timedelta(days=(weekday - day.weekday()) % 7)


def occurrence(rule: Rule, day: date) -> Occurrence:
    if not 0 <= rule.weekday <= 6 or not 1 <= rule.duration_minutes <= 1440:
        raise ValueError("Invalid schedule")
    if (
        day < rule.effective_from
        or (rule.effective_until and day >= rule.effective_until)
        or day.weekday() != rule.weekday
    ):
        raise ValueError("Date does not belong to this schedule version")
    zone = ZoneInfo(rule.timezone)
    naive = datetime.combine(day, rule.local_time)
    local = naive.replace(tzinfo=zone, fold=0)
    # Do not silently invent a policy for an ambiguous/nonexistent local hour.
    if (
        local.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive
        or local.utcoffset() != naive.replace(tzinfo=zone, fold=1).utcoffset()
    ):
        raise ValueError("Ambiguous or nonexistent local start time")
    start = local.astimezone(UTC)
    return Occurrence(
        uuid5(OCCURRENCE_NAMESPACE, f"{rule.id}:{day.isoformat()}"),
        rule.id,
        day,
        start,
        start + timedelta(minutes=rule.duration_minutes),
        rule.timezone,
        rule.venue,
    )


def occurrences(rule: Rule, start: date, end: date) -> list[Occurrence]:
    """Half-open date range; callers bound the requested window."""
    day = first_date_on_or_after(max(start, rule.effective_from), rule.weekday)
    stop = min(end, rule.effective_until) if rule.effective_until else end
    result = []
    while day < stop:
        result.append(occurrence(rule, day))
        day += timedelta(days=7)
    return result
