from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.auth_schemas import Input, clean_text
from app.api.meeting_schemas import PublicPlayer

State = Literal["unknown", "present", "absent"]
HistoryKind = Literal[
    "present",
    "no_show",
    "excused",
    "normal_cancellation",
    "late_cancellation",
    "late_offer_exception",
]


class VersionInput(Input):
    expected_version: int = Field(ge=1)


class DraftPlayer(Input):
    player_id: UUID
    state: State


class AttendanceDraft(VersionInput):
    players: list[DraftPlayer] = Field(max_length=14)


class AdmitPlayer(VersionInput):
    player_id: UUID


class ReasonInput(VersionInput):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_text(cls, value):
        return clean_text(value)


class CorrectionInput(ReasonInput):
    event_id: UUID
    value: HistoryKind


class GenerateTeams(VersionInput):
    mode: Literal["random", "balanced", "preliminary"]


class TeamsDraft(VersionInput):
    team_a: list[UUID] = Field(min_length=1, max_length=7)
    team_b: list[UUID] = Field(min_length=1, max_length=7)


class AttendancePlayer(BaseModel):
    player: PublicPlayer
    draft_state: State
    confirmed_state: Literal["present", "absent"] | None
    event_id: UUID | None


class ReservedPlayer(BaseModel):
    player: PublicPlayer
    kind: str


class AttendanceView(BaseModel):
    meeting_id: UUID
    version: int
    status: str
    attendance_revision: int
    confirmed_at: datetime | None
    can_confirm: bool
    players: list[AttendancePlayer]
    reservations: list[ReservedPlayer]
    free_count: int


class TeamPlayer(BaseModel):
    player: PublicPlayer
    position: int
    rating: float


class TeamsView(BaseModel):
    meeting_id: UUID
    version: int
    revision: int
    state: Literal["draft", "confirmed"]
    method: str
    team_a: list[TeamPlayer]
    team_b: list[TeamPlayer]
    average_a: float
    average_b: float


class CorrectionView(BaseModel):
    id: UUID
    kind: HistoryKind
    reason: str
    actor: PublicPlayer
    created_at: datetime


class HistoryItem(BaseModel):
    id: UUID
    meeting_id: UUID
    meeting_version: int
    starts_at: datetime
    original_kind: HistoryKind
    source_reason: str | None
    current_kind: HistoryKind
    created_at: datetime
    actor: PublicPlayer
    corrections: list[CorrectionView]


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    next_offset: int | None


class PreliminaryTeamsView(BaseModel):
    meeting_id: UUID
    roster_token: str
    revision: int
    method: Literal["balanced", "random", "manual"]
    participant_count: int
    team_a: list[TeamPlayer]
    team_b: list[TeamPlayer]
    average_a: float
    average_b: float


class PreliminaryTeamsInput(Input):
    roster_token: str = Field(min_length=64, max_length=64)
    revision: int = Field(ge=0)
    mode: Literal["balanced", "random", "manual"]
    team_a: list[UUID] = Field(default_factory=list, max_length=7)
    team_b: list[UUID] = Field(default_factory=list, max_length=7)
