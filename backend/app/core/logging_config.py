from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_directory: Path, level: str = "INFO") -> None:
    log_directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_directory / "application.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[console_handler, file_handler],
        force=True,
    )
