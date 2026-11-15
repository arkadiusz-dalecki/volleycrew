"""Replace PIN credentials with private, unique usernames and passwords."""

import sqlalchemy as sa
from alembic import op

revision = "0012_password_login"
down_revision = "0011_google_login"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("players", "pin_hash", new_column_name="password_hash", nullable=True)
    op.add_column("players", sa.Column("username", sa.String(32), nullable=True))
    # A six-digit PIN must never become a valid password. Preserve profiles/history.
    op.execute("UPDATE players SET password_hash = NULL")
    op.create_unique_constraint("uq_players_username", "players", ["username"])
    op.create_check_constraint(
        "player_credentials_pair", "players", "(username IS NULL) = (password_hash IS NULL)"
    )
    op.create_check_constraint(
        "player_username_format", "players", "username ~ '^[a-z0-9][a-z0-9._-]{2,31}$'"
    )
    op.rename_table("pin_reset_grants", "password_reset_grants")
    op.execute(
        "ALTER INDEX ix_pin_reset_grants_player_id RENAME TO ix_password_reset_grants_player_id"
    )
    op.execute("UPDATE auth_sessions SET revoked_at = now() WHERE revoked_at IS NULL")
    op.execute("UPDATE password_reset_grants SET used_at = now() WHERE used_at IS NULL")
    op.execute("UPDATE bootstrap_grants SET used_at = now(), expires_at = now()")
    op.execute("DELETE FROM google_flows")


def downgrade():
    # PIN hashes cannot be recovered. Restore a matching pre-upgrade backup to roll back access.
    op.execute("UPDATE auth_sessions SET revoked_at = now() WHERE revoked_at IS NULL")
    op.execute(
        "UPDATE players SET password_hash = 'password-rollback-requires-reset' "
        "WHERE password_hash IS NULL"
    )
    op.drop_constraint("player_credentials_pair", "players", type_="check")
    op.drop_constraint("player_username_format", "players", type_="check")
    op.drop_constraint("uq_players_username", "players", type_="unique")
    op.drop_column("players", "username")
    op.alter_column("players", "password_hash", new_column_name="pin_hash", nullable=False)
    op.rename_table("password_reset_grants", "pin_reset_grants")
    op.execute(
        "ALTER INDEX ix_password_reset_grants_player_id RENAME TO ix_pin_reset_grants_player_id"
    )
