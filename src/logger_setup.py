"""Centralized logging setup with rotating file handler + console handler."""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logger(
    log_dir: str | Path,
    file_name: str = "reporter.log",
    level: str = "INFO",
    when: str = "midnight",
    backup_count: int = 14,
) -> logging.Logger:
    """Configure root logger with timed rotation."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("servicenow_reporter")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if logger.handlers:
        return logger  # already configured

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(lineno)d | %(message)s"
    )

    file_handler = TimedRotatingFileHandler(
        log_path / file_name,
        when=when,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console)
    return logger
