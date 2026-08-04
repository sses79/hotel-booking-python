"""Create the hotel booking schema.

Revision ID: 20260804_0001
Revises:
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create hotels, rooms, bookings, constraints, and lookup indexes."""

    op.create_table(
        "hotels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_hotels"),
        sa.UniqueConstraint("name", name="uq_hotels_name"),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hotel_id", sa.Uuid(), nullable=False),
        sa.Column("room_number", sa.String(length=20), nullable=False),
        sa.Column("room_type", sa.String(length=16), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.CheckConstraint("capacity > 0", name="ck_rooms_positive_capacity"),
        sa.CheckConstraint(
            "room_type IN ('single', 'double', 'deluxe')",
            name="ck_rooms_valid_room_type",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotels.id"],
            name="fk_rooms_hotel_id_hotels",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rooms"),
        sa.UniqueConstraint(
            "hotel_id",
            "room_number",
            name="uq_rooms_hotel_number",
        ),
    )
    op.create_index("ix_rooms_hotel_id", "rooms", ["hotel_id"], unique=False)
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reference", sa.String(length=32), nullable=False),
        sa.Column("hotel_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("guest_name", sa.String(length=200), nullable=False),
        sa.Column("guest_count", sa.Integer(), nullable=False),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("check_out_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "check_in_date < check_out_date",
            name="ck_bookings_valid_date_range",
        ),
        sa.CheckConstraint(
            "guest_count > 0",
            name="ck_bookings_positive_guest_count",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotels.id"],
            name="fk_bookings_hotel_id_hotels",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name="fk_bookings_room_id_rooms",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bookings"),
        sa.UniqueConstraint("reference", name="uq_bookings_reference"),
    )
    op.create_index(
        "ix_bookings_hotel_id",
        "bookings",
        ["hotel_id"],
        unique=False,
    )
    op.create_index(
        "ix_bookings_room_dates",
        "bookings",
        ["room_id", "check_in_date", "check_out_date"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the initial hotel booking schema."""

    op.drop_index("ix_bookings_room_dates", table_name="bookings")
    op.drop_index("ix_bookings_hotel_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_rooms_hotel_id", table_name="rooms")
    op.drop_table("rooms")
    op.drop_table("hotels")
