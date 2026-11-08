from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class SeatOffer(Base):
    __tablename__ = "seat_offers"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"))
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    enrollment_sequence: Mapped[int] = mapped_column(BigInteger)
    term_version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(12))
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("players.id"))
    __table_args__ = (
        CheckConstraint("state IN ('reserved','pending','accepted','declined','closed','revoked')"),
        CheckConstraint("term_version > 0"),
        Index(
            "ix_offer_active_player",
            "meeting_id",
            "player_id",
            unique=True,
            postgresql_where=text("state IN ('reserved','pending')"),
        ),
        Index("ix_offer_player", "player_id", "meeting_id"),
    )


class EnrollmentEvent(Base):
    __tablename__ = "enrollment_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"))
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    kind: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (Index("ix_enrollment_history", "player_id", "meeting_id", "created_at"),)


class EnrollmentMutation(Base):
    """Retry receipts are separate from domain history; replay returns current state."""

    __tablename__ = "enrollment_mutations"
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    key: Mapped[UUID] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
