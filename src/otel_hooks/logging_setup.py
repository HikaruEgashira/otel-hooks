"""Unified logging configuration for otel-hooks."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_PACKAGE = "otel_hooks"
_LOG_BYTES = 1 * 1024 * 1024  # 1 MiB per file
_LOG_BACKUPS = 3  # keep .log, .log.1, .log.2, .log.3


def configure(log_file: Path, *, debug: bool = False, reconfigure: bool = False) -> None:
    """Attach handlers to the otel_hooks package logger.

    Call once at each entrypoint. Idempotent unless *reconfigure* is True.
    """
    pkg_logger = logging.getLogger(_PACKAGE)
    if pkg_logger.handlers and not reconfigure:
        return
    if reconfigure:
        pkg_logger.handlers.clear()

    pkg_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # File handler — all levels, with rotation
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=_LOG_BYTES,
            backupCount=_LOG_BACKUPS,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        pkg_logger.addHandler(fh)
    except OSError as exc:
        print(
            f"otel-hooks: WARNING: could not open log file {log_file}: {exc}",
            file=sys.stderr,
        )

    # Stderr handler — WARNING and above only
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter("otel-hooks: %(message)s"))
    pkg_logger.addHandler(sh)

    pkg_logger.propagate = False
