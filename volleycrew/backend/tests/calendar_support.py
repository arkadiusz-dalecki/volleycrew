"""Disposable schedule baseline shared by real DB tests and the E2E seeder."""

from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy import text

from app.models.meetings import ScheduleVersion
from app.models.schedule import ScheduleState

DEFAULT_ID = UUID("41754037-508d-4e98-8a48-928e3decb2b7")


async def reset_calendar(db):
    # Caller must already have checked the dedicated *_test database boundary.
    await db.execute(text("TRUNCATE meetings, schedule_versions CASCADE"))
    db.add(
        ScheduleVersion(
            id=DEFAULT_ID,
            effective_from=date(1970, 1, 1),
            weekday=1,
            local_time=time(18),
            duration_minutes=120,
            timezone="Europe/Warsaw",
            venue="I LO w Gdańsku",
            created_at=datetime.now(UTC),
        )
    )
    state = await db.get(ScheduleState, 1)
    state.version = 1
    await db.commit()
