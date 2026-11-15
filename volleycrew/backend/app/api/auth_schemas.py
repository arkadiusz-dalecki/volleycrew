import re
import unicodedata
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
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


class PasswordInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    password: SecretStr = Field(min_length=1, max_length=128)


class NewPassword(PasswordInput):
    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 8:
            raise ValueError("Hasło musi mieć od 8 do 128 znaków.")
        return value


class UsernameInput(Input):
    username: str = Field(min_length=3, max_length=32)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Podaj login.")
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,31}", value):
            raise ValueError("Login: 3–32 litery ASCII, cyfry, kropki, myślniki lub podkreślenia.")
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


class Registration(ProfileInput, UsernameInput, NewPassword):
    token: SecretStr


class Login(UsernameInput, PasswordInput):
    pass


class ChangePassword(NewPassword):
    current_password: SecretStr = Field(min_length=1, max_length=128)


class ResetPassword(UsernameInput, NewPassword):
    token: SecretStr


class PlayerView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str | None
    has_password: bool
    first_name: str
    last_name: str
    nickname: str | None
    priority_status: Priority
    role: Literal["admin", "player"]
    is_active: bool


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


class GoogleStart(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    return_to: str = Field(default="/", max_length=512)

    @field_validator("return_to")
    @classmethod
    def internal_target(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            not value.startswith("/")
            or value.startswith("//")
            or "\\" in value
            or parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or parsed.path.startswith("/api/")
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError("Use an internal page path")
        return value

    mode: Literal["login", "link", "register", "password"] = "login"
    invite_token: SecretStr | None = Field(default=None, min_length=1, max_length=128)
    password: SecretStr | None = Field(default=None, min_length=1, max_length=128)


class GoogleConfig(BaseModel):
    enabled: bool
    public_url: str


class GoogleConnection(BaseModel):
    connected: bool


class GoogleRedirect(BaseModel):
    url: str


class GoogleActionToken(Input):
    token: SecretStr = Field(min_length=43, max_length=43)


class GoogleActionView(BaseModel):
    purpose: Literal["register", "password"]
    first_name: str
    last_name: str


class GoogleRegistration(ProfileInput, GoogleActionToken):
    pass


class GooglePassword(UsernameInput, NewPassword, GoogleActionToken):
    pass
