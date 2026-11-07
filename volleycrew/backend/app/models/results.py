from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ResultRevision(Base):
    __tablename__ = "result_revisions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"))
    revision: Mapped[int] = mapped_column(Integer)
    sheet_id: Mapped[UUID] = mapped_column(ForeignKey("team_sheets.id"))
    sets_a: Mapped[int] = mapped_column(Integer)
    sets_b: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean)
    algorithm: Mapped[str] = mapped_column(String(32))
    __table_args__ = (
        UniqueConstraint("meeting_id", "revision"),
        CheckConstraint("revision > 0 AND sets_a >= 0 AND sets_b >= 0"),
        CheckConstraint("revision = 1 OR (reason IS NOT NULL AND length(trim(reason)) > 0)"),
        Index("ix_active_result", "meeting_id", unique=True, postgresql_where=text("active")),
    )


class RatingState(Base):
    __tablename__ = "rating_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (CheckConstraint("id = 1 AND version > 0"),)


class PlayerRating(Base):
    __tablename__ = "player_ratings"
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True)
    points: Mapped[Decimal] = mapped_column(Numeric())
    meetings: Mapped[int] = mapped_column(Integer)


class RatingEntry(Base):
    """Materialized current replay; immutable original inputs live in ResultRevision/TeamSheet."""

    __tablename__ = "rating_entries"
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("result_revisions.id"))
    side: Mapped[str] = mapped_column(String(1))
    before: Mapped[Decimal] = mapped_column(Numeric())
    delta: Mapped[Decimal] = mapped_column(Numeric())
    after: Mapped[Decimal] = mapped_column(Numeric())
    __table_args__ = (CheckConstraint("side IN ('A','B')"),)


class ResultMutation(Base):
    __tablename__ = "result_mutations"
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    key: Mapped[UUID] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))


class RatingCalculation(Base):
    __tablename__ = "rating_calculations"
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("result_revisions.id"))
    mean_a: Mapped[Decimal] = mapped_column(Numeric())
    mean_b: Mapped[Decimal] = mapped_column(Numeric())
    expected_a: Mapped[Decimal] = mapped_column(Numeric())
    share_a: Mapped[Decimal | None] = mapped_column(Numeric())
    delta_a: Mapped[Decimal] = mapped_column(Numeric())
    delta_b: Mapped[Decimal] = mapped_column(Numeric())
