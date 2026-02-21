# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Tracing hook entrypoint."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from typing import Any

from otel_hooks.adapters.hook_payload import parse_hook_event
from otel_hooks.domain.transcript import build_turns, decode_jsonl_lines
from otel_hooks.providers.factory import create_provider
from otel_hooks.runtime.state import (
    FileLock,
    LOCK_FILE,
    STATE_DIR,
    load_session_state,
    load_state,
    read_new_jsonl_lines,
    save_state,
    state_key,
    write_session_state,
)

LOG_FILE = STATE_DIR / "otel_hook.log"
DEBUG = False


def _log(level: str, message: str) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] {message}\n")
    except Exception:
        pass


def debug(msg: str) -> None:
    if DEBUG:
        _log("DEBUG", msg)


def info(msg: str) -> None:
    _log("INFO", msg)


def warn(msg: str) -> None:
    _log("WARN", msg)


def read_hook_payload() -> dict[str, Any]:
    try:
        data = sys.stdin.read()
        if not data.strip():
            return {}
        return json.loads(data)
    except Exception:
        return {}


def main() -> int:
    global DEBUG

    start = time.time()
    try:
        from otel_hooks.config import load_config

        config = load_config()
    except Exception:
        config = {}

    DEBUG = config.get("debug", False)

    if not config.get("enabled", False):
        return 0

    provider_name = config.get("provider", "")
    if not provider_name:
        return 0

    provider = create_provider(provider_name, config)
    if not provider:
        return 0

    payload = read_hook_payload()
    event = parse_hook_event(payload, warn_fn=warn)

    if event is None or not event.transcript_path.exists():
        debug("Missing session_id/transcript_path or transcript not found; exiting.")
        return 0

    emitted = 0
    try:
        with FileLock(LOCK_FILE):
            state = load_state()
            key = state_key(event.session_id, str(event.transcript_path))
            ss = load_session_state(state, key)

            lines, ss = read_new_jsonl_lines(event.transcript_path, ss)
            if not lines:
                write_session_state(state, key, ss)
                save_state(state)
                return 0

            msgs = decode_jsonl_lines(lines)
            turns = build_turns(msgs)
            if not turns:
                write_session_state(state, key, ss)
                save_state(state)
                return 0

            for turn in turns:
                emitted += 1
                turn_num = ss.turn_count + emitted
                try:
                    provider.emit_turn(event.session_id, turn_num, turn, event.transcript_path)
                except Exception as e:
                    debug(f"emit_turn failed: {e}")

            ss.turn_count += emitted
            write_session_state(state, key, ss)
            save_state(state)

        try:
            provider.flush()
        except Exception:
            pass

        duration = time.time() - start
        info(
            f"Processed {emitted} turns in {duration:.2f}s "
            f"(session={event.session_id}, provider={provider_name})"
        )
        return 0
    except Exception as e:
        debug(f"Unexpected failure: {e}")
        return 0
    finally:
        try:
            provider.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
