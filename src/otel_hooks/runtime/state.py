"""Runtime session-state persistence and lock utilities."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = Path.home() / ".config" / "otel-hooks" / "state"


@dataclass(frozen=True)
class StatePaths:
    state_dir: Path
    state_file: Path
    lock_file: Path


def build_state_paths(state_dir: Path) -> StatePaths:
    return StatePaths(
        state_dir=state_dir,
        state_file=state_dir / "otel_hook_state.json",
        lock_file=state_dir / "otel_hook_state.lock",
    )


class FileLock:
    def __init__(self, path: Path, timeout_s: float = 2.0):
        self.path = path
        self.timeout_s = timeout_s
        self._fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+", encoding="utf-8")
        try:
            import fcntl

            deadline = time.time() + self.timeout_s
            while True:
                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.time() > deadline:
                        break
                    time.sleep(0.05)
        except Exception:
            logger.debug("File locking unavailable", exc_info=True)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            logger.debug("File unlock failed", exc_info=True)
        try:
            self._fh.close()
        except Exception:
            logger.debug("File close failed", exc_info=True)


@dataclass
class SessionState:
    offset: int = 0
    buffer: str = ""
    turn_count: int = 0


def state_key(session_id: str, transcript_path: str) -> str:
    raw = f"{session_id}::{transcript_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_state(state_file: Path) -> dict[str, Any]:
    try:
        if not state_file.exists():
            return {}
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Failed to load state from %s", state_file, exc_info=True)
        return {}


def save_state(state: dict[str, Any], state_file: Path) -> None:
    try:
        from otel_hooks.file_io import atomic_write

        atomic_write(state_file, json.dumps(state, indent=2, sort_keys=True).encode("utf-8"))
    except Exception:
        logger.warning("Failed to save state to %s", state_file, exc_info=True)




def load_session_state(global_state: dict[str, Any], key: str) -> SessionState:
    s = global_state.get(key, {})
    return SessionState(
        offset=int(s.get("offset", 0)),
        buffer=str(s.get("buffer", "")),
        turn_count=int(s.get("turn_count", 0)),
    )


def write_session_state(global_state: dict[str, Any], key: str, ss: SessionState) -> None:
    global_state[key] = {
        "offset": ss.offset,
        "buffer": ss.buffer,
        "turn_count": ss.turn_count,
        "updated": datetime.now(timezone.utc).isoformat(),
    }


def read_new_jsonl_lines(transcript_path: Path, ss: SessionState) -> tuple[list[str], SessionState]:
    if not transcript_path.exists():
        return [], ss
    try:
        with open(transcript_path, "rb") as f:
            f.seek(ss.offset)
            chunk = f.read()
            new_offset = f.tell()
    except Exception:
        logger.debug("Failed to read transcript %s", transcript_path, exc_info=True)
        return [], ss

    if not chunk:
        return [], ss

    try:
        text = chunk.decode("utf-8", errors="replace")
    except Exception:
        text = chunk.decode(errors="replace")

    combined = ss.buffer + text
    lines = combined.split("\n")
    ss.buffer = lines[-1]
    ss.offset = new_offset
    return lines[:-1], ss
