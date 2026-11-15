"""Optional Google identities and short-lived browser-bound OAuth flows."""

import sqlalchemy as sa
from alembic import op

revision = "0011_google_login"
down_revision = "0010_preliminary_teams"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "google_identities",
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("subject", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "google_flows",
        sa.Column("return_to", sa.String(512), nullable=False),
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("auth_sessions.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_google_flows_expires_at", "google_flows", ["expires_at"])


def downgrade():
    op.drop_table("google_flows")
    op.drop_table("google_identities")
