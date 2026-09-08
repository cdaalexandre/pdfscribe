"""Logging configuration for pdfscribe.

Every module does:
    from pdfscribe.log import get_logger
    logger = get_logger(__name__)

Entrypoints call setup_logging() once at startup.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_DIR = Path.home() / ".pdfscribe"
LOG_FILE = LOG_DIR / "pdfscribe.log"

FILE_FMT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
CONSOLE_FMT = "%(message)s"
VERBOSE_CONSOLE_FMT = "%(levelname)-8s  %(name)s  %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'pdfscribe' hierarchy."""
    return logging.getLogger(name)


def setup_logging(
    *,
    level: str = "INFO",
    log_to_file: bool = True,
    verbose: bool = False,
    quiet: bool = False,
) -> None:
    """Configure the 'pdfscribe' root logger. Call ONCE from entrypoints.

    Args:
        level: Base log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_to_file: Write to ~/.pdfscribe/pdfscribe.log.
        verbose: Console shows logger name and level prefix.
        quiet: Console level is WARNING (suppresses INFO).
    """
    root = logging.getLogger("pdfscribe")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    console = logging.StreamHandler(sys.stderr)
    console_level = logging.WARNING if quiet else root.level
    console.setLevel(console_level)
    console_fmt = VERBOSE_CONSOLE_FMT if verbose else CONSOLE_FMT
    console.setFormatter(logging.Formatter(console_fmt))
    root.addHandler(console)

    if log_to_file:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter(FILE_FMT))
            root.addHandler(handler)
        except OSError:
            console.setLevel(logging.DEBUG)
            root.warning("Could not create log file at %s - console only", LOG_FILE)
