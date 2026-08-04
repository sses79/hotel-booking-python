"""Application logging setup."""

import logging


def configure_logging(level: str) -> None:
    """Configure a predictable baseline logger for local and container use."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
