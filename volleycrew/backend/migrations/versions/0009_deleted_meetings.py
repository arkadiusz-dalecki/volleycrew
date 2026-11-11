"""Keep deleted occurrence markers without exposing cancelled calendar entries."""

import sqlalchemy as sa
from alembic import op

revision = "0009_deleted_meetings"
down_revision = "0008_additional_meetings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("meetings", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("meetings", "deleted_at")
