"""Shared JSON file helpers for tool configurations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from otel_hooks.file_io import atomic_write


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default.copy() if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default.copy() if default is not None else {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
