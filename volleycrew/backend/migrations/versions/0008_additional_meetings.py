"""Distinguish added meetings from occurrences of the recurring schedule."""

import sqlalchemy as sa
from alembic import op

revision = "0008_additional_meetings"
down_revision = "0007_results"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "meetings",
        sa.Column("is_additional", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("meetings", "is_additional")
