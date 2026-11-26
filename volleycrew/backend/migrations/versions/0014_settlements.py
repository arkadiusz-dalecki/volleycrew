"""Meeting prices, private receipt details and settlement history."""

import sqlalchemy as sa
from alembic import op

revision = "0014_settlements"
down_revision = "0013_google_registration"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("schedule_versions", "meetings"):
        op.add_column(
            table, sa.Column("cost_grosz", sa.Integer(), nullable=False, server_default="0")
        )
        op.create_check_constraint(
            f"{table}_valid_cost", table, "cost_grosz BETWEEN 0 AND 100000000"
        )
    op.add_column(
        "meetings",
        sa.Column("cost_overridden", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("players", sa.Column("blik_phone", sa.String(12)))
    op.add_column("players", sa.Column("revolut_link", sa.String(200)))
    op.create_table(
        "meeting_charges",
        sa.Column("meeting_id", sa.UUID(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("player_id", sa.UUID(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 0"),
    )
    op.create_index("ix_meeting_charges_player_id", "meeting_charges", ["player_id"])
    op.create_table(
        "charge_revisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("meeting_id", sa.UUID(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("player_id", sa.UUID(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("actor_id", sa.UUID(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_charge_revisions_meeting_id", "charge_revisions", ["meeting_id"])
    op.create_table(
        "payment_reports",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("player_id", sa.UUID(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("recipient_id", sa.UUID(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer_id", sa.UUID(), sa.ForeignKey("players.id")),
        sa.Column("reason", sa.String(500)),
        sa.CheckConstraint("status IN ('pending','paid','rejected')"),
    )
    op.create_index("ix_payment_reports_player_id", "payment_reports", ["player_id"])
    op.create_table(
        "payment_allocations",
        sa.Column("report_id", sa.UUID(), sa.ForeignKey("payment_reports.id"), primary_key=True),
        sa.Column("meeting_id", sa.UUID(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount > 0"),
    )


def downgrade():
    for table in ("payment_allocations", "payment_reports", "charge_revisions", "meeting_charges"):
        op.drop_table(table)
    op.drop_column("players", "revolut_link")
    op.drop_column("players", "blik_phone")
    op.drop_column("meetings", "cost_overridden")
    for table in ("meetings", "schedule_versions"):
        op.drop_constraint(f"{table}_valid_cost", table)
        op.drop_column(table, "cost_grosz")
