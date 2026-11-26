from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class MeetingCharge(Base):
    __tablename__ = "meeting_charges"
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), primary_key=True, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("amount >= 0"),)


class ChargeRevision(Base):
    __tablename__ = "charge_revisions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), index=True)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaymentReport(Base):
    __tablename__ = "payment_reports"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), index=True)
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"))
    status: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("players.id"))
    reason: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (CheckConstraint("status IN ('pending','paid','rejected')"),)


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    report_id: Mapped[UUID] = mapped_column(ForeignKey("payment_reports.id"), primary_key=True)
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    amount: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("amount > 0"),)
