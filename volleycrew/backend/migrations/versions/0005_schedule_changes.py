"""Stable occurrence bindings, schedule concurrency and durable term revisions."""

import sqlalchemy as sa
from alembic import op

revision = "0005_schedule_changes"
down_revision = "0004_enrollment"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("schedule_no_overlap", "schedule_versions")
    op.add_column(
        "schedule_versions",
        sa.Column("superseded", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.execute(
        "ALTER TABLE schedule_versions ADD CONSTRAINT schedule_no_overlap "
        "EXCLUDE USING gist (daterange(effective_from, effective_until, '[)') WITH &&) "
        "WHERE (NOT superseded)"
    )
    op.add_column(
        "meetings",
        sa.Column("calendar_schedule_id", sa.Uuid(), sa.ForeignKey("schedule_versions.id")),
    )
    op.add_column("meetings", sa.Column("calendar_source_date", sa.Date()))
    op.add_column(
        "meetings", sa.Column("is_exception", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column("meetings", sa.Column("previous_starts_at", sa.DateTime(timezone=True)))
    op.add_column("meetings", sa.Column("previous_ends_at", sa.DateTime(timezone=True)))
    op.execute(
        "UPDATE meetings SET calendar_schedule_id=schedule_version_id, "
        "calendar_source_date=source_date"
    )
    op.alter_column("meetings", "calendar_schedule_id", nullable=False)
    op.alter_column("meetings", "calendar_source_date", nullable=False)
    op.create_unique_constraint(
        "meeting_calendar_unique", "meetings", ["calendar_schedule_id", "calendar_source_date"]
    )
    op.add_column(
        "enrollments",
        sa.Column("reconfirmation_required", sa.Boolean(), nullable=False, server_default="false"),
    )
    table = op.create_table(
        "schedule_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("id = 1 AND version > 0"),
    )
    op.bulk_insert(table, [{"id": 1, "version": 1}])
    op.create_table(
        "meeting_term_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("term_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        *[
            sa.Column(name, sa.DateTime(timezone=True), nullable=False)
            for name in ("previous_starts_at", "previous_ends_at", "starts_at", "ends_at")
        ],
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", "term_version"),
        sa.CheckConstraint("action IN ('rescheduled','cancelled')"),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT version > 1 FROM schedule_state WHERE id=1")
    ) or op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM meeting_term_revisions)")):
        raise RuntimeError(
            "E5 data exists: restore a matching backup instead of a destructive downgrade"
        )
    op.drop_constraint("schedule_no_overlap", "schedule_versions")
    op.drop_column("schedule_versions", "superseded")
    op.execute(
        "ALTER TABLE schedule_versions ADD CONSTRAINT schedule_no_overlap "
        "EXCLUDE USING gist (daterange(effective_from, effective_until, '[)') WITH &&)"
    )
    op.drop_table("meeting_term_revisions")
    op.drop_table("schedule_state")
    op.drop_column("enrollments", "reconfirmation_required")
    op.drop_constraint("meeting_calendar_unique", "meetings")
    for name in (
        "previous_ends_at",
        "previous_starts_at",
        "is_exception",
        "calendar_source_date",
        "calendar_schedule_id",
    ):
        op.drop_column("meetings", name)
