"""Runtime configuration validation tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("database_url", ["", "   "])
def test_settings_rejects_empty_database_url(database_url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=database_url)
