from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ScheduleState(Base):
    __tablename__ = "schedule_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    __table_args__ = (CheckConstraint("id = 1 AND version > 0"),)


class MeetingTermRevision(Base):
    __tablename__ = "meeting_term_revisions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"))
    term_version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(16))
    previous_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("meeting_id", "term_version"),
        CheckConstraint("action IN ('rescheduled','cancelled')"),
    )
