"""PostgreSQL migration setup for integration tests."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database() -> Iterator[None]:
    """Apply all migrations when PostgreSQL integration testing is enabled."""

    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        yield
        return

    project_root = Path(__file__).resolve().parents[2]
    configuration = Config(project_root / "alembic.ini")
    configuration.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(configuration, "head")
    yield
