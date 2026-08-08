"""Pure booking service behavior tests."""

import re

import pytest
from pydantic import ValidationError

from app.schemas.bookings import BookingCreate
from app.services.bookings import generate_booking_reference


def test_booking_reference_is_128_bit_uppercase_hex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def token_hex(number_of_bytes: int) -> str:
        assert number_of_bytes == 16
        return "ab" * number_of_bytes

    monkeypatch.setattr("app.services.bookings.secrets.token_hex", token_hex)

    reference = generate_booking_reference()

    assert reference == "AB" * 16
    assert re.fullmatch(r"[A-F0-9]{32}", reference)


@pytest.mark.parametrize("guest_name", ["", "   "])
def test_booking_request_rejects_blank_guest_name(guest_name: str) -> None:
    with pytest.raises(ValidationError):
        BookingCreate.model_validate(
            {
                "hotel_id": "00000000-0000-0000-0000-000000000001",
                "guest_name": guest_name,
                "guest_count": 1,
                "check_in_date": "2027-09-01",
                "check_out_date": "2027-09-02",
            }
        )
