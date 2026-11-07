from dataclasses import replace
from datetime import UTC, date, time, timedelta
from uuid import uuid4

import pytest

from app.domain.schedule import Rule, occurrence, occurrences

RULE = Rule(uuid4(), date(1970, 1, 1), None, 1, time(18), 120, "Europe/Warsaw", "I LO w Gdańsku")


@pytest.mark.parametrize(
    ("day", "utc_hour"),
    [
        (date(2026, 3, 24), 17),
        (date(2026, 3, 31), 16),
        (date(2026, 10, 20), 16),
        (date(2026, 10, 27), 17),
    ],
)
def test_warsaw_local_start_survives_dst(day, utc_hour):
    item = occurrence(RULE, day)
    assert item.starts_at.tzinfo == UTC
    assert item.starts_at.hour == utc_hour
    assert item.ends_at - item.starts_at == timedelta(hours=2)


def test_versions_change_weekday_and_keep_half_open_boundary():
    old = replace(RULE, effective_until=date(2027, 1, 1))
    new = replace(
        RULE, id=uuid4(), effective_from=date(2027, 1, 1), weekday=4, local_time=time(19, 30)
    )
    old_dates = occurrences(old, date(2026, 12, 25), date(2027, 1, 10))
    new_dates = occurrences(new, date(2026, 12, 25), date(2027, 1, 10))
    assert [item.source_date for item in old_dates] == [date(2026, 12, 29)]
    assert [item.source_date for item in new_dates] == [date(2027, 1, 1), date(2027, 1, 8)]
    assert new_dates[0].starts_at.hour == 18 and new_dates[0].starts_at.minute == 30
    assert occurrence(new, date(2027, 1, 8)).id == new_dates[1].id
    with pytest.raises(ValueError):
        occurrence(old, date(2027, 1, 5))


@pytest.mark.parametrize("day", [date(2026, 3, 29), date(2026, 10, 25)])
def test_undefined_dst_hours_are_not_silently_shifted(day):
    rule = replace(RULE, weekday=6, local_time=time(2, 30))
    with pytest.raises(ValueError, match="Ambiguous or nonexistent"):
        occurrence(rule, day)


def test_leap_day_and_elapsed_duration_crossing_dst():
    leap = replace(RULE, weekday=3)
    assert occurrences(leap, date(2024, 2, 29), date(2024, 3, 1))[0].source_date == date(
        2024, 2, 29
    )
    overnight = replace(RULE, weekday=6, local_time=time(1, 30))
    item = occurrence(overnight, date(2026, 3, 29))
    assert item.ends_at - item.starts_at == timedelta(hours=2)
