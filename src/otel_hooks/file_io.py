"""Secure file I/O primitives with explicit permission control."""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    """Write data atomically with explicit file permissions.

    Creates a temporary file with the given permissions, writes data,
    then atomically replaces the target path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    tmp.replace(path)
