import re
import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

Priority = Literal["founder", "player", "guest"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def clean_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value.strip())
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Invalid control character")
    return value


class PinInput(Input):
    pin: SecretStr

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, value: SecretStr) -> SecretStr:
        if not re.fullmatch(r"[0-9]{6}", value.get_secret_value()):
            raise ValueError("PIN must contain six ASCII digits")
        return value


class ProfileInput(Input):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    nickname: str | None = Field(default=None, max_length=40)

    @field_validator("first_name", "last_name")
    @classmethod
    def names(cls, value: str) -> str:
        return clean_text(value)

    @field_validator("nickname")
    @classmethod
    def nick(cls, value: str | None) -> str | None:
        return (clean_text(value) or None) if value is not None else None


class Registration(ProfileInput, PinInput):
    token: SecretStr


class Login(PinInput):
    profile_id: UUID


class ChangePin(PinInput):
    current_pin: SecretStr

    @field_validator("current_pin")
    @classmethod
    def validate_current_pin(cls, value: SecretStr) -> SecretStr:
        return cls.validate_pin(value)


class ResetPin(PinInput):
    token: SecretStr


class PlayerView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    first_name: str
    last_name: str
    nickname: str | None
    priority_status: Priority
    role: Literal["admin", "player"]
    is_active: bool


class LoginProfile(BaseModel):
    profile_id: UUID
    first_name: str
    masked_last_name: str
    nickname: str | None


class AdminPlayerPatch(Input):
    is_active: bool | None = None
    priority_status: Priority | None = None


class InviteView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    revoked_at: datetime | None


class LinkCreated(BaseModel):
    id: UUID
    url: str


class CsrfView(BaseModel):
    token: str


class Done(BaseModel):
    ok: bool = True
