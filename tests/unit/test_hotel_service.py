"""Pure hotel availability service rule tests."""

from datetime import date

import pytest

from app.core.errors import BadRequestError
from app.services.hotels import validate_stay_dates


def test_stay_may_start_today() -> None:
    today = date(2026, 9, 1)

    validate_stay_dates(today, date(2026, 9, 2), today=today)


def test_stay_rejects_past_check_in() -> None:
    with pytest.raises(BadRequestError) as error:
        validate_stay_dates(
            date(2026, 8, 31),
            date(2026, 9, 2),
            today=date(2026, 9, 1),
        )

    assert error.value.code == "check_in_in_past"
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    "check_out_date",
    [date(2026, 9, 1), date(2026, 8, 31)],
)
def test_stay_rejects_check_out_not_after_check_in(check_out_date: date) -> None:
    with pytest.raises(BadRequestError) as error:
        validate_stay_dates(
            date(2026, 9, 1),
            check_out_date,
            today=date(2026, 9, 1),
        )

    assert error.value.code == "invalid_date_range"
    assert error.value.status_code == 400
