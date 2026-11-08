import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOLLEYCREW_", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://volleycrew:volleycrew_dev@127.0.0.1:55432/volleycrew_dev"
    )
    public_url: str = "http://localhost:5173"
    cookie_secure: bool = True
    behind_proxy: bool = False
    additional_origins: list[str] = []
    trusted_proxy_cidrs: list[str] = []
    session_secret: SecretStr | None = None
    state_dir: Path = Path(__file__).resolve().parents[4] / ".runtime"

    @model_validator(mode="after")
    def require_secure_cookies(self):
        if not self.cookie_secure and urlsplit(self.public_url).hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("Insecure cookies are allowed only on localhost")
        return self

    @field_validator("public_url")
    @classmethod
    def validate_public_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("PUBLIC_URL must be an http(s) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("PUBLIC_URL cannot contain credentials, query or fragment")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("HTTPS required outside localhost")
        return value.rstrip("/")

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def validate_proxies(cls, value: list[str]) -> list[str]:
        from ipaddress import ip_network

        for cidr in value:
            ip_network(cidr)
        return value

    @field_validator("additional_origins")
    @classmethod
    def validate_origins(cls, value: list[str]) -> list[str]:
        for origin in value:
            cls.validate_public_url(origin)
            parsed = urlsplit(origin)
            if parsed.path or parsed.query or parsed.fragment:
                raise ValueError("Additional origins cannot contain a path")
        return value

    @field_validator("session_secret")
    @classmethod
    def validate_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+asyncpg" and bool(url.host and url.database)
        except Exception:
            valid = False
        if not valid:
            raise ValueError("Use a PostgreSQL URL with the asyncpg driver, host and database")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=os.environ.get("VOLLEYCREW_ENV_FILE", ".env"))
