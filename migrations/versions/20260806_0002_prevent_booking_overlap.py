"""Prevent overlapping bookings for the same room.

Revision ID: 20260806_0002
Revises: 20260804_0001
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260806_0002"
down_revision: str | None = "20260804_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "excl_bookings_room_date_overlap"


def upgrade() -> None:
    """Add the PostgreSQL extension and half-open overlap constraint."""

    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        f"""
        ALTER TABLE bookings
        ADD CONSTRAINT {CONSTRAINT_NAME}
        EXCLUDE USING gist (
            room_id WITH =,
            daterange(check_in_date, check_out_date, '[)') WITH &&
        )
        """
    )


def downgrade() -> None:
    """Remove the overlap constraint and its supporting extension."""

    op.execute(f"ALTER TABLE bookings DROP CONSTRAINT {CONSTRAINT_NAME}")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
