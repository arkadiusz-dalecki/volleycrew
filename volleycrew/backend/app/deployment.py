"""Home Assistant options -> validated settings and private s6 environment files."""

import json
import os
import re
import secrets
from ipaddress import ip_network
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from sqlalchemy.engine import URL

from app.core.config import Settings

ENV_DIR = Path("/var/run/s6/container_environment")


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    DATABASE_MODE: str = "auto"
    POSTGRES_HOST: str = Field(default="", max_length=253)
    POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
    POSTGRES_DB: str = Field(default="volleycrew", min_length=1)
    POSTGRES_USER: str = Field(default="volleycrew", min_length=1)
    POSTGRES_PASSWORD: SecretStr = SecretStr("")
    POSTGRES_SSL: str = "prefer"
    PUBLIC_URL: str
    ADDITIONAL_ORIGINS: list[str] = []
    TRUSTED_PROXY_CIDRS: list[str] = []
    SESSION_SECRET: SecretStr = SecretStr("")
    BOOTSTRAP_TOKEN: SecretStr = SecretStr("")
    BACKUP_HOUR: int = Field(default=3, ge=0, le=23)

    @field_validator("PUBLIC_URL")
    @classmethod
    def root_url(cls, value):
        Settings.validate_public_url(value)
        if urlsplit(value).path not in {"", "/"}:
            raise ValueError("PUBLIC_URL must not contain a path")
        return value

    @field_validator("POSTGRES_SSL")
    @classmethod
    def ssl_mode(cls, value):
        if value not in {"disable", "prefer", "require", "verify-full"}:
            raise ValueError("Invalid PostgreSQL TLS mode")
        return value

    @field_validator("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER")
    @classmethod
    def no_controls(cls, value):
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are not allowed")
        return value

    @field_validator("TRUSTED_PROXY_CIDRS")
    @classmethod
    def proxies(cls, value):
        for cidr in value:
            network = ip_network(cidr, strict=True)
            if network.prefixlen == 0:
                raise ValueError("Do not trust the entire Internet")
        return value

    @field_validator("BOOTSTRAP_TOKEN", "SESSION_SECRET")
    @classmethod
    def secret_length(cls, value):
        raw = value.get_secret_value()
        if raw and (len(raw) < 32 or not raw.isascii() or any(c.isspace() for c in raw)):
            raise ValueError("Use at least 32 ASCII characters without whitespace")
        return value

    @field_validator("BOOTSTRAP_TOKEN")
    @classmethod
    def token_alphabet(cls, value):
        raw = value.get_secret_value()
        if raw and not re.fullmatch(r"[A-Za-z0-9_-]{32,}", raw):
            raise ValueError("BOOTSTRAP_TOKEN must be URL-safe: letters, digits, - and _")
        return value

    @model_validator(mode="after")
    def database_mode_valid(self):
        if self.DATABASE_MODE not in {"auto", "embedded", "external"}:
            raise ValueError("DATABASE_MODE must be auto, embedded or external")
        if self.DATABASE_MODE == "external" and not self.POSTGRES_HOST:
            raise ValueError("POSTGRES_HOST is required for an external database")
        return self

    @property
    def embedded(self) -> bool:
        return self.DATABASE_MODE == "embedded" or (
            self.DATABASE_MODE == "auto" and not self.POSTGRES_HOST
        )

    def settings(self, state: Path) -> Settings:
        if self.embedded:
            password_file = state / "postgres-password"
            if not password_file.exists():
                if (state / "postgres-initialized").exists() or (
                    state / "postgresql/PG_VERSION"
                ).exists():
                    raise ValueError("Bundled database password missing; recover matching state")
                private_write(password_file, secrets.token_hex(32))
            host, port, database, user, password, ssl = (
                "127.0.0.1",
                5432,
                "volleycrew",
                "volleycrew",
                password_file.read_text().strip(),
                "disable",
            )
        else:
            host, port, database, user, password, ssl = (
                self.POSTGRES_HOST,
                self.POSTGRES_PORT,
                self.POSTGRES_DB,
                self.POSTGRES_USER,
                self.POSTGRES_PASSWORD.get_secret_value(),
                self.POSTGRES_SSL,
            )
        url = URL.create(
            "postgresql+asyncpg",
            username=user,
            password=password,
            host=host,
            port=port,
            database=database,
            query={"ssl": ssl},
        )
        return Settings(
            _env_file=None,
            database_url=url.render_as_string(hide_password=False),
            public_url=self.PUBLIC_URL,
            additional_origins=self.ADDITIONAL_ORIGINS,
            trusted_proxy_cidrs=["127.0.0.1/32", "::1/128"],
            cookie_secure=True,
            behind_proxy=True,
            state_dir=state,
            session_secret=self.SESSION_SECRET.get_secret_value() or None,
        )


def private_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data.encode() if isinstance(data, str) else data)


def prepare(
    options_path: Path = Path("/data/options.json"),
    state: Path = Path("/data"),
    env_dir: Path = ENV_DIR,
    nginx_dir: Path = Path("/etc/nginx"),
) -> Options:
    options = Options.model_validate_json(options_path.read_bytes())
    mode = "embedded" if options.embedded else "external"
    previous = state / "database-mode"
    if previous.exists() and previous.read_text().strip() != mode:
        raise ValueError(
            "Database mode change requires explicit data migration; original data retained"
        )
    if not previous.exists() and mode == "embedded" and (state / "installed-version").exists():
        raise ValueError("Existing installation requires explicit database migration")
    settings = options.settings(state)
    private_write(previous, mode)
    os.umask(0o077)
    env_dir.mkdir(parents=True, exist_ok=True)
    values = {
        "VOLLEYCREW_DATABASE_URL": settings.database_url.get_secret_value(),
        "VOLLEYCREW_PUBLIC_URL": settings.public_url,
        "VOLLEYCREW_COOKIE_SECURE": "true",
        "VOLLEYCREW_BEHIND_PROXY": "true",
        "VOLLEYCREW_STATE_DIR": str(state),
        "VOLLEYCREW_ADDITIONAL_ORIGINS": json.dumps(settings.additional_origins),
        "VOLLEYCREW_TRUSTED_PROXY_CIDRS": json.dumps(settings.trusted_proxy_cidrs),
        "VOLLEYCREW_SESSION_SECRET": options.SESSION_SECRET.get_secret_value(),
        "VOLLEYCREW_ENV_FILE": "/dev/null",
    }
    # Empty session secret means the application persists its own key in /data.
    if not values["VOLLEYCREW_SESSION_SECRET"]:
        values.pop("VOLLEYCREW_SESSION_SECRET")
        (env_dir / "VOLLEYCREW_SESSION_SECRET").unlink(missing_ok=True)
    for key, value in values.items():
        if "\0" in value:
            raise ValueError("NUL in configuration")
        private_write(env_dir / key, value)
    networks = [str(ip_network(c)) for c in options.TRUSTED_PROXY_CIDRS]
    template = (nginx_dir / "nginx.conf.template").read_text()
    config = template.replace("@@TRUSTED_TLS@@", "\n".join(f"{n} 1;" for n in networks))
    config = config.replace("@@REAL_IP@@", "\n".join(f"set_real_ip_from {n};" for n in networks))
    (nginx_dir / "nginx.conf").write_text(config)
    return options


def load_environment(env_dir: Path = ENV_DIR) -> None:
    """CLI/backup hooks load the private settings without shell evaluation.

    Explicit caller variables (including the restore target) retain precedence.
    """
    for path in env_dir.glob("VOLLEYCREW_*"):
        if path.is_file():
            os.environ.setdefault(path.name, path.read_text())
