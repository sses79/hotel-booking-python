"""Hotel booking ORM models and relational invariants."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoomType(StrEnum):
    """Supported room categories."""

    SINGLE = "single"
    DOUBLE = "double"
    DELUXE = "deluxe"


ROOM_TYPE_CHECK_SQL = "room_type IN ({})".format(
    ", ".join(f"'{room_type.value}'" for room_type in RoomType)
)


ROOM_TYPE_ENUM = Enum(
    RoomType,
    values_callable=lambda enum: [member.value for member in enum],
    native_enum=False,
    create_constraint=False,
    validate_strings=True,
    length=16,
)

BOOKING_OVERLAP_CONSTRAINT = "excl_bookings_room_date_overlap"


class Hotel(Base):
    """A hotel containing bookable rooms."""

    __tablename__ = "hotels"
    __table_args__ = (UniqueConstraint("name", name="uq_hotels_name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    rooms: Mapped[list[Room]] = relationship(
        back_populates="hotel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    bookings: Mapped[list[Booking]] = relationship(
        back_populates="hotel",
        lazy="raise",
        viewonly=True,
    )


class Room(Base):
    """A physical hotel room with a fixed capacity."""

    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("hotel_id", "room_number", name="uq_rooms_hotel_number"),
        UniqueConstraint("id", "hotel_id", name="uq_rooms_id_hotel_id"),
        CheckConstraint("capacity > 0", name="positive_capacity"),
        CheckConstraint(ROOM_TYPE_CHECK_SQL, name="valid_room_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    hotel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    room_type: Mapped[RoomType] = mapped_column(ROOM_TYPE_ENUM, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    hotel: Mapped[Hotel] = relationship(back_populates="rooms", lazy="raise")
    bookings: Mapped[list[Booking]] = relationship(
        back_populates="room",
        passive_deletes=True,
        lazy="raise",
    )


class Booking(Base):
    """A guest's reservation of one room for a half-open date range."""

    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("reference", name="uq_bookings_reference"),
        CheckConstraint("guest_count > 0", name="positive_guest_count"),
        CheckConstraint(
            "check_in_date < check_out_date",
            name="valid_date_range",
        ),
        ForeignKeyConstraint(
            ["room_id", "hotel_id"],
            ["rooms.id", "rooms.hotel_id"],
            name="fk_bookings_room_hotel_rooms",
            ondelete="CASCADE",
        ),
        ExcludeConstraint(
            ("room_id", "="),
            (text("daterange(check_in_date, check_out_date, '[)')"), "&&"),
            name=BOOKING_OVERLAP_CONSTRAINT,
            using="gist",
        ),
        Index(
            "ix_bookings_room_dates",
            "room_id",
            "check_in_date",
            "check_out_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reference: Mapped[str] = mapped_column(String(32), nullable=False)
    hotel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[UUID] = mapped_column(nullable=False)
    guest_name: Mapped[str] = mapped_column(String(200), nullable=False)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    check_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_out_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    hotel: Mapped[Hotel] = relationship(
        back_populates="bookings",
        lazy="raise",
        viewonly=True,
    )
    room: Mapped[Room] = relationship(back_populates="bookings", lazy="raise")
