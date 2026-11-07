"""Seat reservations/offers, private enrollment history and retry receipts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_enrollment"
down_revision = "0003_meetings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("enrollments", sa.Column("reservation_kind", sa.String(16)))
    op.execute("UPDATE enrollments SET reservation_kind='offer' WHERE allocation='reserved'")
    op.create_check_constraint(
        "enrollment_reservation_kind",
        "enrollments",
        "(allocation = 'reserved') = (reservation_kind IS NOT NULL) "
        "AND (reservation_kind IS NULL OR reservation_kind IN ('offer','reconfirmation'))",
    )
    op.create_table(
        "seat_offers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("enrollment_sequence", sa.BigInteger(), nullable=False),
        sa.Column("term_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True)),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("players.id")),
        sa.CheckConstraint(
            "state IN ('reserved','pending','accepted','declined','closed','revoked')"
        ),
        sa.CheckConstraint("term_version > 0"),
    )
    op.create_index(
        "ix_offer_active_player",
        "seat_offers",
        ["meeting_id", "player_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('reserved','pending')"),
    )
    op.create_index("ix_offer_player", "seat_offers", ["player_id", "meeting_id"])
    op.create_table(
        "enrollment_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_enrollment_history", "enrollment_events", ["player_id", "meeting_id", "created_at"]
    )
    op.create_table(
        "enrollment_mutations",
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id"), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), primary_key=True),
        sa.Column("key", sa.Uuid(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("enrollment_mutations")
    op.drop_table("enrollment_events")
    op.drop_table("seat_offers")
    op.drop_constraint("enrollment_reservation_kind", "enrollments")
    op.drop_column("enrollments", "reservation_kind")
