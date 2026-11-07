from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.auth_schemas import Input, clean_text
from app.api.meeting_schemas import PublicPlayer
from app.api.room_schemas import ReasonInput, TeamsDraft, VersionInput


class ScoreInput(VersionInput):
    sets_a: int = Field(strict=True, ge=0, le=2147483647)
    sets_b: int = Field(strict=True, ge=0, le=2147483647)


class SaveResult(ScoreInput):
    expected_rating_version: int = Field(ge=1)


class PresenceCorrection(Input):
    player_id: UUID
    value: Literal["present", "no_show", "excused"]
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value):
        return clean_text(value)


class CorrectionPreview(ScoreInput, TeamsDraft, ReasonInput):
    presence_changes: list[PresenceCorrection] = Field(default_factory=list, max_length=28)


class CorrectResult(CorrectionPreview):
    expected_rating_version: int = Field(ge=1)


class OutcomeView(BaseModel):
    mean_a: Decimal
    mean_b: Decimal
    expected_a: Decimal
    share_a: Decimal | None
    delta_a: Decimal
    delta_b: Decimal


class RatingChange(BaseModel):
    player: PublicPlayer
    side: Literal["A", "B"]
    before: Decimal
    delta: Decimal
    after: Decimal


class ResultPreview(BaseModel):
    meeting_version: int
    rating_version: int
    sets_a: int
    sets_b: int
    outcome: OutcomeView
    players: list[RatingChange]
    recalculated_meetings: int


class RevisionView(BaseModel):
    revision: int
    sets_a: int
    sets_b: int
    created_at: datetime
    actor: PublicPlayer


class ResultView(BaseModel):
    meeting_id: UUID
    meeting_version: int
    rating_version: int
    starts_at: datetime
    revision: int
    state: Literal["played", "no_sets"]
    sets_a: int
    sets_b: int
    algorithm: str
    outcome: OutcomeView
    players: list[RatingChange]
    revisions: list[RevisionView]


class HistoricalTeams(BaseModel):
    team_a: list[PublicPlayer]
    team_b: list[PublicPlayer]


class AdminResultView(ResultView):
    reasons: dict[int, str]
    squads: dict[int, HistoricalTeams]


class RankingPlayer(BaseModel):
    player: PublicPlayer
    points: Decimal
    meetings: int
    position: int


class RankingPage(BaseModel):
    version: int
    items: list[RankingPlayer]
    total: int
    next_offset: int | None


class ResultSummary(BaseModel):
    meeting_id: UUID
    starts_at: datetime
    revision: int
    sets_a: int
    sets_b: int
    state: Literal["played", "no_sets"]
    delta_a: Decimal
    delta_b: Decimal


class ResultsPage(BaseModel):
    version: int
    items: list[ResultSummary]
    total: int
    next_offset: int | None


class PlayerRatingHistory(BaseModel):
    version: int
    player: PublicPlayer
    points: Decimal
    items: list["RatingHistoryItem"]
    total: int
    next_offset: int | None


class RatingHistoryItem(ResultSummary):
    before: Decimal
    delta: Decimal
    after: Decimal
    side: Literal["A", "B"]
