from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        CheckConstraint("priority_status IN ('founder','player','guest')"),
        CheckConstraint("role IN ('admin','player')"),
        CheckConstraint(
            "(username IS NULL) = (password_hash IS NULL)", name="player_credentials_pair"
        ),
        CheckConstraint("username ~ '^[a-z0-9][a-z0-9._-]{2,31}$'", name="player_username_format"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    nickname: Mapped[str | None] = mapped_column(String(40))
    priority_status: Mapped[str] = mapped_column(
        String(12), default="guest", server_default="guest"
    )
    role: Mapped[str] = mapped_column(String(12), default="player", server_default="player")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    username: Mapped[str | None] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None


class Session(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetGrant(Base):
    __tablename__ = "password_reset_grants"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), index=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("players.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BootstrapGrant(Base):
    __tablename__ = "bootstrap_grants"
    __table_args__ = (CheckConstraint("id = 1"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthThrottle(Base):
    __tablename__ = "auth_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("players.id"))
    action: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class GoogleIdentity(Base):
    __tablename__ = "google_identities"
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GoogleFlow(Base):
    __tablename__ = "google_flows"
    mode: Mapped[str] = mapped_column(String(8), default="login", server_default="login")
    invite_id: Mapped[UUID | None] = mapped_column(ForeignKey("invites.id"))
    return_to: Mapped[str] = mapped_column(String(512))
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    browser_hash: Mapped[str] = mapped_column(String(64))
    nonce_hash: Mapped[str] = mapped_column(String(64))
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("auth_sessions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GoogleActionGrant(Base):
    __tablename__ = "google_action_grants"
    __table_args__ = (
        CheckConstraint("purpose IN ('register','password')"),
        CheckConstraint(
            "(purpose = 'register' AND invite_id IS NOT NULL AND session_id IS NULL) OR "
            "(purpose = 'password' AND invite_id IS NULL AND session_id IS NOT NULL)"
        ),
    )
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    browser_hash: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(8))
    subject: Mapped[str] = mapped_column(String(255))
    invite_id: Mapped[UUID | None] = mapped_column(ForeignKey("invites.id"))
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("auth_sessions.id"))
    first_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
