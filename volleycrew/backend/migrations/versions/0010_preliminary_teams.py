"""Save organizer overrides of the enrollment-based team preview."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_preliminary_teams"
down_revision = "0009_deleted_meetings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "preliminary_teams",
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("roster_token", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("team_a", postgresql.JSONB(), nullable=False),
        sa.Column("team_b", postgresql.JSONB(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision > 0"),
        sa.CheckConstraint("method IN ('random','balanced','manual')"),
    )


def downgrade():
    op.drop_table("preliminary_teams")
