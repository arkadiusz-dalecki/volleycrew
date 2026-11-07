"""Versioned results and atomic materialized rating replay."""

import sqlalchemy as sa
from alembic import op

revision = "0007_results"
down_revision = "0006_room"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "team_members",
        "rating_snapshot",
        type_=sa.Numeric(),
        existing_type=sa.Float(),
        postgresql_using="rating_snapshot::numeric",
    )
    op.create_table(
        "result_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("sheet_id", sa.Uuid(), sa.ForeignKey("team_sheets.id"), nullable=False),
        sa.Column("sets_a", sa.Integer(), nullable=False),
        sa.Column("sets_b", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("algorithm", sa.String(32), nullable=False),
        sa.UniqueConstraint("meeting_id", "revision"),
        sa.CheckConstraint("revision > 0 AND sets_a >= 0 AND sets_b >= 0"),
        sa.CheckConstraint("revision = 1 OR (reason IS NOT NULL AND length(trim(reason)) > 0)"),
    )
    op.create_index(
        "ix_active_result",
        "result_revisions",
        ["meeting_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "rating_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1 AND version > 0"),
    )
    op.execute("INSERT INTO rating_state (id,version) VALUES (1,1)")
    op.create_table(
        "player_ratings",
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("points", sa.Numeric(), nullable=False),
        sa.Column("meetings", sa.Integer(), nullable=False),
    )
    op.create_table(
        "rating_entries",
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("result_id", sa.Uuid(), sa.ForeignKey("result_revisions.id"), nullable=False),
        sa.Column("side", sa.String(1), nullable=False),
        *[sa.Column(name, sa.Numeric(), nullable=False) for name in ["before", "delta", "after"]],
        sa.CheckConstraint("side IN ('A','B')"),
    )
    op.create_table(
        "rating_calculations",
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("result_id", sa.Uuid(), sa.ForeignKey("result_revisions.id"), nullable=False),
        *[
            sa.Column(name, sa.Numeric(), nullable=False)
            for name in ["mean_a", "mean_b", "expected_a", "delta_a", "delta_b"]
        ],
        sa.Column("share_a", sa.Numeric()),
    )
    op.create_table(
        "result_mutations",
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("key", sa.Uuid(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM result_revisions)")):
        raise RuntimeError("Results exist: restore a matching backup instead of deleting history")
    for table in [
        "result_mutations",
        "rating_calculations",
        "rating_entries",
        "player_ratings",
        "rating_state",
        "result_revisions",
    ]:
        op.drop_table(table)
    op.alter_column(
        "team_members",
        "rating_snapshot",
        type_=sa.Float(),
        existing_type=sa.Numeric(),
        postgresql_using="rating_snapshot::double precision",
    )
