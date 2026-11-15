"""Invite-bound Google registration and one-time profile/password completion."""

import sqlalchemy as sa
from alembic import op

revision = "0013_google_registration"
down_revision = "0012_password_login"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "google_flows", sa.Column("mode", sa.String(8), nullable=False, server_default="login")
    )
    op.add_column("google_flows", sa.Column("invite_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_google_flows_invite", "google_flows", "invites", ["invite_id"], ["id"]
    )
    op.execute("UPDATE google_flows SET mode = 'link' WHERE session_id IS NOT NULL")
    # Before this release, NULL credentials denote uninitialized legacy profiles.
    # They must not acquire Google-only access through a pre-transition binding.
    op.execute(
        "UPDATE auth_sessions SET revoked_at = now() WHERE revoked_at IS NULL "
        "AND player_id IN (SELECT id FROM players WHERE password_hash IS NULL)"
    )
    op.execute(
        "DELETE FROM google_identities WHERE player_id IN "
        "(SELECT id FROM players WHERE password_hash IS NULL)"
    )
    op.create_table(
        "google_action_grants",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(8), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("invite_id", sa.UUID(), sa.ForeignKey("invites.id")),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("auth_sessions.id")),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("purpose IN ('register','password')"),
        sa.CheckConstraint(
            "(purpose = 'register' AND invite_id IS NOT NULL AND session_id IS NULL) OR "
            "(purpose = 'password' AND invite_id IS NULL AND session_id IS NOT NULL)"
        ),
    )
    op.create_index("ix_google_action_grants_expires_at", "google_action_grants", ["expires_at"])


def downgrade():
    op.execute(
        "UPDATE auth_sessions SET revoked_at = now() WHERE revoked_at IS NULL "
        "AND player_id IN (SELECT id FROM players WHERE password_hash IS NULL)"
    )
    op.drop_table("google_action_grants")
    op.drop_constraint("fk_google_flows_invite", "google_flows", type_="foreignkey")
    op.drop_column("google_flows", "invite_id")
    op.drop_column("google_flows", "mode")
