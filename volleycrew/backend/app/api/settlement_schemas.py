import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.auth_schemas import Input, clean_text


class PaymentDetails(Input):
    blik_phone: str | None = Field(default=None, max_length=30)
    revolut_link: str | None = Field(default=None, max_length=200)

    @field_validator("blik_phone")
    @classmethod
    def phone(cls, value):
        if not value:
            return None
        value = re.sub(r"[ -]", "", value)
        if not re.fullmatch(r"(?:\+48)?[0-9]{9}", value):
            raise ValueError("Podaj polski numer telefonu do BLIK.")
        return value

    @field_validator("revolut_link")
    @classmethod
    def link(cls, value):
        if not value:
            return None
        value = value.strip()
        if not re.fullmatch(r"https://(?:www\.)?revolut\.me/[A-Za-z0-9_-]+/?", value):
            raise ValueError("Podaj osobisty link https://revolut.me/…")
        return value


class Recipient(PaymentDetails):
    name: str


class ReportPayment(Input):
    id: UUID
    meeting_ids: list[UUID] = Field(min_length=1)
    amount: int = Field(gt=0, strict=True)

    @field_validator("meeting_ids")
    @classmethod
    def unique_meetings(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Spotkanie może wystąpić w zgłoszeniu tylko raz.")
        return value


class ReviewPayment(Input):
    status: Literal["paid", "rejected"]
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def rejection_reason(self):
        if self.status == "rejected":
            self.reason = clean_text(self.reason or "")
            if not self.reason:
                raise ValueError("Podaj powód odrzucenia.")
        return self


class Share(BaseModel):
    player_id: UUID
    amount: int
    delta: int = 0


class ChargeView(BaseModel):
    meeting_id: UUID
    starts_at: datetime
    posted_at: datetime
    amount: int
    due: int
    pending: int
    paid: int


class ReportView(BaseModel):
    id: UUID
    status: Literal["pending", "paid", "rejected"]
    amount: int
    created_at: datetime
    reviewed_at: datetime | None
    meeting_ids: list[UUID]
    reason: str | None


class PlayerSettlements(BaseModel):
    player_id: UUID
    name: str
    due: int
    pending: int
    credit: int
    oldest_due_at: datetime | None
    reminder: bool
    charges: list[ChargeView]
    reports: list[ReportView]


class MySettlements(PlayerSettlements):
    recipient: Recipient | None


class CorrectCost(Input):
    expected_version: int = Field(ge=1)
    cost_grosz: int = Field(ge=0, le=100_000_000, strict=True)
    reason: str = Field(min_length=1, max_length=500)

    _reason = field_validator("reason")(clean_text)


class CostPreview(BaseModel):
    meeting_id: UUID
    version: int
    cost_grosz: int
    shares: list[Share]
