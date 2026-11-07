"""Attendance, immutable private history, versioned teams and retry receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0006_room"
down_revision = "0005_schedule_changes"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("attendance_revision", "team_revision"):
        op.add_column("meetings", sa.Column(name, sa.Integer(), nullable=False, server_default="0"))
    op.add_column("meetings", sa.Column("attendance_confirmed_at", sa.DateTime(timezone=True)))
    op.create_table(
        "attendance_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *[
            sa.Column(name, sa.Uuid(), sa.ForeignKey(target), nullable=False)
            for name, target in [
                ("meeting_id", "meetings.id"),
                ("player_id", "players.id"),
                ("actor_id", "players.id"),
            ]
        ],
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column(
            "source_enrollment_event_id",
            sa.Uuid(),
            sa.ForeignKey("enrollment_events.id"),
            unique=True,
        ),
        sa.Column("correction_of", sa.Uuid(), sa.ForeignKey("attendance_events.id")),
        sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), unique=True, nullable=False),
        sa.CheckConstraint(
            "kind IN ('present','no_show','excused',"
            "'normal_cancellation','late_cancellation','late_offer_exception')"
        ),
        sa.CheckConstraint("correction_of IS NULL OR length(trim(reason)) > 0"),
    )
    op.create_index("ix_attendance_history", "attendance_events", ["player_id", "sequence"])
    op.create_index("ix_attendance_corrections", "attendance_events", ["correction_of", "sequence"])
    # Earlier cancellations already have durable source events; preserve their IDs and dates.
    op.execute(
        "INSERT INTO attendance_events (id,meeting_id,player_id,actor_id,kind,"
        "source_enrollment_event_id,created_at) "
        "SELECT id,meeting_id,player_id,actor_id,CASE details->>'cancellation_kind' "
        "WHEN 'normal' THEN 'normal_cancellation' WHEN 'late' THEN 'late_cancellation' "
        "ELSE 'late_offer_exception' END,id,created_at FROM enrollment_events "
        "WHERE kind='withdrawn' AND details->>'cancellation_kind' "
        "IN ('normal','late','late_offer_exception') "
        "ORDER BY enrollment_events.created_at,enrollment_events.id"
    )
    op.create_table(
        "attendance",
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("draft_state", sa.String(8), nullable=False, server_default="unknown"),
        sa.Column("confirmed_state", sa.String(8)),
        sa.Column("root_event_id", sa.Uuid(), sa.ForeignKey("attendance_events.id"), unique=True),
        sa.CheckConstraint("draft_state IN ('unknown','present','absent')"),
        sa.CheckConstraint("confirmed_state IS NULL OR confirmed_state IN ('present','absent')"),
    )
    op.create_table(
        "team_sheets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("attendance_revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("meeting_id", "revision"),
        sa.CheckConstraint("state IN ('draft','confirmed','archived')"),
        sa.CheckConstraint("method IN ('random','balanced','manual')"),
        sa.CheckConstraint("revision > 0 AND attendance_revision > 0"),
    )
    op.create_index(
        "ix_active_team_sheet",
        "team_sheets",
        ["meeting_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('draft','confirmed')"),
    )
    op.create_table(
        "team_members",
        sa.Column("sheet_id", sa.Uuid(), sa.ForeignKey("team_sheets.id"), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("side", sa.String(1), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("rating_snapshot", sa.Float(), nullable=False),
        sa.UniqueConstraint("sheet_id", "side", "position"),
        sa.CheckConstraint("side IN ('A','B') AND position BETWEEN 0 AND 6"),
    )
    op.create_table(
        "room_mutations",
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("key", sa.Uuid(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM attendance) OR EXISTS (SELECT 1 FROM team_sheets) "
            "OR EXISTS (SELECT 1 FROM attendance_events)"
        )
    ):
        raise RuntimeError(
            "Attendance/history exists: restore a matching backup instead of destructive downgrade"
        )
    for table in (
        "room_mutations",
        "team_members",
        "team_sheets",
        "attendance",
        "attendance_events",
    ):
        op.drop_table(table)
    for name in ("attendance_confirmed_at", "team_revision", "attendance_revision"):
        op.drop_column("meetings", name)
