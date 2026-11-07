from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.api.auth_schemas import Input

MeetingStatus = Literal[
    "scheduled", "attendance_checked", "teams_confirmed", "completed", "cancelled"
]


class PublicPlayer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    first_name: str
    last_name: str
    nickname: str | None


class PlayerPage(BaseModel):
    items: list[PublicPlayer]
    total: int
    next_offset: int | None


class ScheduleView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    effective_from: date
    effective_until: date | None
    weekday: int
    local_time: time
    duration_minutes: int
    timezone: str
    venue: str


class ResolveOccurrence(Input):
    schedule_version_id: UUID
    source_date: date


class MeetingSummary(BaseModel):
    id: UUID
    schedule_version_id: UUID
    source_date: date
    starts_at: datetime
    ends_at: datetime
    timezone: str
    venue: str
    status: MeetingStatus
    term_version: int
    version: int
    capacity: int
    previous_starts_at: datetime | None = None
    previous_ends_at: datetime | None = None
    is_exception: bool = False
    persisted: bool
    participant_count: int = 0
    waitlist_count: int = 0
    reserved_count: int = 0
    free_count: int = 14


class MeetingDetail(MeetingSummary):
    participants: list[PublicPlayer]
    waitlist: list[PublicPlayer]
    awaiting_confirmation: list[PublicPlayer] = []


class CalendarPage(BaseModel):
    from_date: date
    to_date: date
    items: list[MeetingSummary]
    total: int
    next_offset: int | None
