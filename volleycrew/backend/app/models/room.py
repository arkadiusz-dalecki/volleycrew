from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.enrollment import EnrollmentEvent


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"))
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    kind: Mapped[str] = mapped_column(String(24))
    source_enrollment_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("enrollment_events.id"), unique=True
    )
    source_enrollment_event: Mapped[EnrollmentEvent | None] = relationship(
        foreign_keys=[source_enrollment_event_id]
    )
    correction_of: Mapped[UUID | None] = mapped_column(ForeignKey("attendance_events.id"))
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    __table_args__ = (
        CheckConstraint(
            "kind IN ('present','no_show','excused',"
            "'normal_cancellation','late_cancellation','late_offer_exception')"
        ),
        CheckConstraint("correction_of IS NULL OR length(trim(reason)) > 0"),
        Index("ix_attendance_history", "player_id", "sequence"),
        Index("ix_attendance_corrections", "correction_of", "sequence"),
    )


class Attendance(Base):
    __tablename__ = "attendance"
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True)
    draft_state: Mapped[str] = mapped_column(String(8), default="unknown", server_default="unknown")
    confirmed_state: Mapped[str | None] = mapped_column(String(8))
    root_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("attendance_events.id"), unique=True
    )
    __table_args__ = (
        CheckConstraint("draft_state IN ('unknown','present','absent')"),
        CheckConstraint("confirmed_state IS NULL OR confirmed_state IN ('present','absent')"),
    )


class TeamSheet(Base):
    __tablename__ = "team_sheets"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"))
    revision: Mapped[int] = mapped_column(Integer)
    attendance_revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(10))
    method: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("meeting_id", "revision"),
        CheckConstraint("state IN ('draft','confirmed','archived')"),
        CheckConstraint("method IN ('random','balanced','manual')"),
        CheckConstraint("revision > 0 AND attendance_revision > 0"),
        Index(
            "ix_active_team_sheet",
            "meeting_id",
            unique=True,
            postgresql_where=text("state IN ('draft','confirmed')"),
        ),
    )


class TeamMember(Base):
    __tablename__ = "team_members"
    sheet_id: Mapped[UUID] = mapped_column(ForeignKey("team_sheets.id"), primary_key=True)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True)
    side: Mapped[str] = mapped_column(String(1))
    position: Mapped[int] = mapped_column(Integer)
    rating_snapshot: Mapped[Decimal] = mapped_column(Numeric())
    __table_args__ = (
        UniqueConstraint("sheet_id", "side", "position"),
        CheckConstraint("side IN ('A','B') AND position BETWEEN 0 AND 6"),
    )


class RoomMutation(Base):
    __tablename__ = "room_mutations"
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    key: Mapped[UUID] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
