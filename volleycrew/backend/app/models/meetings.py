from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ScheduleVersion(Base):
    __tablename__ = "schedule_versions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    weekday: Mapped[int] = mapped_column(Integer)  # Monday=0, Sunday=6
    local_time: Mapped[time] = mapped_column(Time(timezone=False))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64))
    venue: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6"),
        CheckConstraint("duration_minutes BETWEEN 1 AND 1440"),
        CheckConstraint("effective_until IS NULL OR effective_until > effective_from"),
        ExcludeConstraint(
            (func.daterange(effective_from, effective_until, "[)"), "&&"),
            using="gist",
            name="schedule_no_overlap",
            where=text("NOT superseded"),
        ),
    )


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    schedule_version_id: Mapped[UUID] = mapped_column(ForeignKey("schedule_versions.id"))
    source_date: Mapped[date] = mapped_column(Date)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64))
    venue: Mapped[str] = mapped_column(String(160))
    calendar_schedule_id: Mapped[UUID] = mapped_column(ForeignKey("schedule_versions.id"))
    calendar_source_date: Mapped[date] = mapped_column(Date)
    is_exception: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    previous_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    previous_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="scheduled", server_default="scheduled")
    term_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    attendance_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    team_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attendance_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer, default=14, server_default="14")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("schedule_version_id", "source_date", name="meeting_source_unique"),
        UniqueConstraint(
            "calendar_schedule_id", "calendar_source_date", name="meeting_calendar_unique"
        ),
        CheckConstraint("ends_at > starts_at"),
        CheckConstraint("capacity = 14"),
        CheckConstraint("term_version > 0 AND version > 0"),
        CheckConstraint(
            "status IN ('scheduled','attendance_checked','teams_confirmed','completed','cancelled')"
        ),
        Index("ix_meetings_starts_at", "starts_at"),
    )


class Enrollment(Base):
    """Persistence foundation. All allocation mutations are introduced together in E4."""

    __tablename__ = "enrollments"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"))
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    declaration: Mapped[str] = mapped_column(String(12))
    allocation: Mapped[str] = mapped_column(String(12), default="none", server_default="none")
    reconfirmation_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    reservation_kind: Mapped[str | None] = mapped_column(String(16))
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    queue_number: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    confirmed_term_version: Mapped[int | None] = mapped_column(Integer)
    accepted_late_offer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    __table_args__ = (
        UniqueConstraint("meeting_id", "player_id", name="enrollment_player_unique"),
        CheckConstraint(
            "(allocation = 'reserved') = (reservation_kind IS NOT NULL) "
            "AND (reservation_kind IS NULL OR reservation_kind IN ('offer','reconfirmation'))",
            name="enrollment_reservation_kind",
        ),
        CheckConstraint("declaration IN ('going','not-going','withdrawn')"),
        CheckConstraint("allocation IN ('none','seat','waitlist','reserved')"),
        CheckConstraint("declaration = 'going' OR allocation = 'none'"),
        CheckConstraint("confirmed_term_version IS NULL OR confirmed_term_version > 0"),
        Index("ix_enrollments_queue", "meeting_id", "allocation", "declared_at", "queue_number"),
        Index("ix_enrollments_player", "player_id", "meeting_id"),
    )
