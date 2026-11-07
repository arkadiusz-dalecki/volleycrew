from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.auth_schemas import Input
from app.api.meeting_schemas import MeetingDetail, PublicPlayer


class TermInput(Input):
    term_version: int = Field(ge=1)


class DeclarationInput(TermInput):
    declaration: Literal["going", "not-going"]
    acknowledge_late: bool = False


class WithdrawInput(TermInput):
    acknowledge_late: bool = False


class ProposeOffer(TermInput):
    player_id: UUID


class CloseOffer(TermInput):
    reason: Literal["no-response"] = "no-response"


class OfferView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    player: PublicPlayer
    term_version: int
    state: Literal["reserved", "pending", "accepted", "declined", "closed", "revoked"]
    reserved_at: datetime
    proposed_at: datetime | None


class MyParticipation(BaseModel):
    declaration: Literal["going", "not-going", "withdrawn"] | None = None
    allocation: Literal["none", "seat", "waitlist", "reserved"] = "none"
    position: int | None = None
    offer: OfferView | None = None
    needs_reconfirmation: bool = False
    can_declare: bool
    term_version: int
    deadline: datetime
    priority_locked: bool
    cancellation_kind: Literal["none", "normal", "late", "late_offer_exception"] = "none"


class ParticipationResult(BaseModel):
    meeting: MeetingDetail
    participation: MyParticipation
