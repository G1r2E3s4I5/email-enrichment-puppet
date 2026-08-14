"""Centralized logging configuration."""

import sys
import logging
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application loggers with console and file handlers.

    Args:
        log_level: Desired logging verbosity string (e.g. DEBUG, INFO, WARNING, ERROR).
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    log_format = "%(asctime)s | %(levelname)-8s | [%(name)s] | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)

    # File Handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)

    # Root Logger Config
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress verbose third-party logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger("email_enrichment")
