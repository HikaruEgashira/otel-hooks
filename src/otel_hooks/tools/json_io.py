"""Shared JSON file helpers for tool configurations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default.copy() if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default.copy() if default is not None else {}


def save_json(path: Path, data: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    tmp.replace(path)
