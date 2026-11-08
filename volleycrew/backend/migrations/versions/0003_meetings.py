"""Versioned schedule, stable meeting occurrences and enrollment foundation."""

from datetime import UTC, date, datetime, time
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ExcludeConstraint

revision = "0003_meetings"
down_revision = "0002_auth"
branch_labels = None
depends_on = None
DEFAULT_SCHEDULE_ID = UUID("41754037-508d-4e98-8a48-928e3decb2b7")


def upgrade():
    schedules = op.create_table(
        "schedule_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date()),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("venue", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6"),
        sa.CheckConstraint("duration_minutes BETWEEN 1 AND 1440"),
        sa.CheckConstraint("effective_until IS NULL OR effective_until > effective_from"),
        ExcludeConstraint(
            (sa.text("daterange(effective_from, effective_until, '[)')"), "&&"),
            name="schedule_no_overlap",
            using="gist",
        ),
    )
    op.bulk_insert(
        schedules,
        [
            {
                "id": DEFAULT_SCHEDULE_ID,
                "effective_from": date(1970, 1, 1),
                "effective_until": None,
                "weekday": 1,
                "local_time": time(18),
                "duration_minutes": 120,
                "timezone": "Europe/Warsaw",
                "venue": "I LO w Gdańsku",
                "created_at": datetime.now(UTC),
            }
        ],
    )
    op.create_table(
        "meetings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "schedule_version_id", sa.Uuid(), sa.ForeignKey("schedule_versions.id"), nullable=False
        ),
        sa.Column("source_date", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("venue", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("term_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("schedule_version_id", "source_date", name="meeting_source_unique"),
        sa.CheckConstraint("ends_at > starts_at"),
        sa.CheckConstraint("capacity = 14"),
        sa.CheckConstraint("term_version > 0 AND version > 0"),
        sa.CheckConstraint(
            "status IN ('scheduled','attendance_checked','teams_confirmed','completed','cancelled')"
        ),
    )
    op.create_index("ix_meetings_starts_at", "meetings", ["starts_at"])
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("declaration", sa.String(12), nullable=False),
        sa.Column("allocation", sa.String(12), nullable=False, server_default="none"),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queue_number", sa.BigInteger(), sa.Identity(), unique=True, nullable=False),
        sa.Column("confirmed_term_version", sa.Integer()),
        sa.Column("accepted_late_offer", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("meeting_id", "player_id", name="enrollment_player_unique"),
        sa.CheckConstraint("declaration IN ('going','not-going','withdrawn')"),
        sa.CheckConstraint("allocation IN ('none','seat','waitlist','reserved')"),
        sa.CheckConstraint("declaration = 'going' OR allocation = 'none'"),
        sa.CheckConstraint("confirmed_term_version IS NULL OR confirmed_term_version > 0"),
    )
    op.create_index(
        "ix_enrollments_queue",
        "enrollments",
        ["meeting_id", "allocation", "declared_at", "queue_number"],
    )
    op.create_index("ix_enrollments_player", "enrollments", ["player_id", "meeting_id"])


def downgrade():
    op.drop_table("enrollments")
    op.drop_table("meetings")
    op.drop_table("schedule_versions")
