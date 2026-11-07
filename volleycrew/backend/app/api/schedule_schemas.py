from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.auth_schemas import Input, clean_text
from app.api.meeting_schemas import ScheduleView


class ScheduleInput(Input):
    expected_version: int = Field(ge=1)
    effective_from: date
    weekday: int = Field(ge=0, le=6)
    local_time: time
    duration_minutes: int = Field(ge=1, le=1440)
    venue: str = Field(min_length=1, max_length=160)

    @field_validator("local_time")
    @classmethod
    def minute_precision(cls, value):
        if value.tzinfo or value.second or value.microsecond:
            raise ValueError("Local time must have minute precision without timezone")
        return value

    @field_validator("venue")
    @classmethod
    def venue_text(cls, value):
        return clean_text(value)


class ApplySchedule(ScheduleInput):
    preview_token: str = Field(min_length=64, max_length=64)


class ScheduleSettings(BaseModel):
    version: int
    rules: list[ScheduleView]


class PlannedMeeting(BaseModel):
    id: UUID
    version: int
    previous_starts_at: datetime
    starts_at: datetime
    ends_at: datetime
    status: str
    kept_exception: bool
    reconfirmation_count: int


class SchedulePreview(BaseModel):
    version: int
    preview_token: str
    existing: list[PlannedMeeting]
    examples: list[datetime]
    reconfirmation_count: int
    kept_exception_count: int


class RescheduleInput(Input):
    expected_version: int = Field(ge=1)
    local_date: date
    local_time: time
    duration_minutes: int = Field(ge=1, le=1440)
    _precision = field_validator("local_time")(ScheduleInput.minute_precision.__func__)


class MeetingVersionInput(Input):
    expected_version: int = Field(ge=1)


class ReleaseReservation(MeetingVersionInput):
    player_id: UUID
