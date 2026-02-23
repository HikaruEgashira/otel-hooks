# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Tracing hook entrypoint."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from otel_hooks.tools import SupportKind, parse_hook_event
from otel_hooks.domain.transcript import build_turns, decode_jsonl_lines
from otel_hooks.providers.factory import create_provider
from otel_hooks.runtime.state import (
    DEFAULT_STATE_DIR,
    FileLock,
    StatePaths,
    build_state_paths,
    load_session_state,
    load_state,
    read_new_jsonl_lines,
    save_state,
    state_key,
    write_session_state,
)


def _resolve_state_paths(config: dict[str, Any]) -> StatePaths:
    configured = config.get("state_dir")
    if configured:
        base = Path(str(configured)).expanduser().resolve()
        return build_state_paths(base)
    return build_state_paths(DEFAULT_STATE_DIR)


def read_hook_payload() -> dict[str, Any]:
    """Read JSON payload from stdin (provided by parent AI tool process)."""
    try:
        data = sys.stdin.read()
        payload: dict[str, Any] = {}
        if data.strip():
            payload = json.loads(data)
        return payload
    except Exception:
        logger.warning("Failed to read hook payload from stdin", exc_info=True)
        return {}


def run_hook(
    payload: dict[str, Any],
    config: dict[str, Any],
    *,
    provider_factory=create_provider,
) -> int:
    start = time.time()
    debug_enabled = bool(config.get("debug", False))
    runtime_state_paths = _resolve_state_paths(config)
    log_file = runtime_state_paths.state_dir / "otel_hook.log"

    from otel_hooks.logging_setup import configure

    configure(log_file, debug=debug_enabled, reconfigure=True)

    provider_name = config.get("provider")
    if not provider_name:
        logger.debug("No --provider flag; exiting.")
        return 0

    event = parse_hook_event(payload)

    if event is None:
        logger.debug("No matching adapter for payload; exiting.")
        return 0

    if event.kind is SupportKind.TRACE:
        if event.transcript_path is not None and not event.transcript_path.exists():
            logger.debug("Transcript file not found; exiting.")
            return 0
        if event.transcript_path is None:
            logger.debug(
                "No transcript path for %s; session-only trace not yet supported.",
                event.source_tool,
            )
            return 0

    provider = provider_factory(provider_name, config)
    if not provider:
        logger.warning("Failed to create provider: %s", provider_name)
        return 1

    emitted = 0
    try:
        if event.kind is SupportKind.METRICS:
            try:
                provider.emit_metric(
                    event.metric_name,
                    event.metric_value,
                    event.metric_attributes or {},
                    event.source_tool,
                    event.session_id,
                )
                emitted = 1
            except Exception:
                logger.warning("emit_metric failed", exc_info=True)
                return 1
            try:
                provider.flush()
            except Exception:
                logger.warning("flush failed", exc_info=True)
                return 1
            duration = time.time() - start
            logger.info(
                "Processed metric %s in %.2fs (session=%s, provider=%s)",
                event.metric_name,
                duration,
                event.session_id or "-",
                provider_name,
            )
            return 0

        with FileLock(runtime_state_paths.lock_file):
            state = load_state(runtime_state_paths.state_file)
            key = state_key(event.session_id, str(event.transcript_path))
            ss = load_session_state(state, key)
            prev_offset = ss.offset
            prev_buffer = ss.buffer
            prev_turn_count = ss.turn_count

            lines, ss = read_new_jsonl_lines(event.transcript_path, ss)
            if not lines:
                write_session_state(state, key, ss)
                save_state(state, runtime_state_paths.state_file)
                return 0

            msgs = decode_jsonl_lines(lines)
            turns = build_turns(msgs)
            if not turns:
                write_session_state(state, key, ss)
                save_state(state, runtime_state_paths.state_file)
                return 0

            emit_failed = False
            for turn in turns:
                turn_num = ss.turn_count + emitted + 1
                try:
                    provider.emit_turn(
                        event.session_id,
                        turn_num,
                        turn,
                        event.transcript_path,
                        event.source_tool,
                    )
                except Exception:
                    logger.warning("emit_turn failed", exc_info=True)
                    emit_failed = True
                    break
                emitted += 1

            if emit_failed:
                ss.offset = prev_offset
                ss.buffer = prev_buffer
                ss.turn_count = prev_turn_count
            else:
                ss.turn_count += emitted
            write_session_state(state, key, ss)
            save_state(state, runtime_state_paths.state_file)

        try:
            provider.flush()
        except Exception:
            logger.warning("flush failed", exc_info=True)
            return 1

        duration = time.time() - start
        if emit_failed:
            logger.warning(
                "Partial failure: %d turns emitted in %.2fs (session=%s, provider=%s)",
                emitted,
                duration,
                event.session_id,
                provider_name,
            )
            return 1
        logger.info(
            "Processed %d turns in %.2fs (session=%s, provider=%s)",
            emitted,
            duration,
            event.session_id,
            provider_name,
        )
        return 0
    except Exception:
        logger.warning("Unexpected failure", exc_info=True)
        return 1
    finally:
        try:
            provider.shutdown()
        except Exception:
            logger.warning("provider.shutdown() failed", exc_info=True)


def _parse_flag(name: str) -> str | None:
    """Extract --<name> <value> from sys.argv without interfering with stdin."""
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == f"--{name}" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(f"--{name}="):
            return arg.split("=", 1)[1]
    return None


def main() -> int:
    from otel_hooks.logging_setup import configure
    from otel_hooks.config import load_config

    configure(build_state_paths(DEFAULT_STATE_DIR).state_dir / "otel_hook.log")

    config = load_config()

    provider = _parse_flag("provider")
    if provider:
        config["provider"] = provider

    payload = read_hook_payload()

    tool_hint = _parse_flag("tool")
    if tool_hint and "source_tool" not in payload:
        payload["source_tool"] = tool_hint

    return run_hook(payload, config)


if __name__ == "__main__":
    sys.exit(main())
