"""Trade service entrypoint — CLI + HTTP server."""

from __future__ import annotations

import logging
import logging.handlers
import sys

import uvicorn

from config import settings


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt))

    # File handler
    data_dir = settings.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        data_dir / "trade.log",
        maxBytes=5_242_880,
        backupCount=3,
    )
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)


def main() -> None:
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("Starting trade service on %s:%d", settings.host, settings.port)

    uvicorn.run(
        "api.app:app",
        host=settings.host,
        port=settings.port,
        timeout_keep_alive=120,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
