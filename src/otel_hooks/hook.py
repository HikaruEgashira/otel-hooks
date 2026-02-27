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
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from openhook import EventType, OpenHookEvent
from otel_hooks.tools import parse_hook_event
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

# Event types that map to emit_metric (lifecycle events without transcript)
_METRIC_EVENT_TYPES = frozenset({EventType.PROMPT_SUBMIT, EventType.TOOL_START, EventType.TOOL_END})

_EVENT_TYPE_TO_METRIC_NAME: dict[EventType, str] = {
    EventType.PROMPT_SUBMIT: "prompt_submitted",
    EventType.TOOL_START: "tool_started",
    EventType.TOOL_END: "tool_completed",
    EventType.SESSION_END: "session_ended",
}


def _context_to_cwd(context: str | None) -> Path | None:
    """Convert an openhook file:// context URI to a filesystem Path."""
    if not context or not context.startswith("file://"):
        return None
    path = urlparse(context).path
    return Path(path) if path else None


def _derive_metric_name(event: OpenHookEvent) -> str:
    legacy = event.extensions.get("legacy_payload", {})
    if legacy.get("metric_name"):
        return str(legacy["metric_name"])
    return _EVENT_TYPE_TO_METRIC_NAME.get(event.type, str(event.type))


def _derive_metric_value(event: OpenHookEvent) -> float:
    legacy = event.extensions.get("legacy_payload", {})
    if "metric_value" in legacy:
        return float(legacy["metric_value"])
    return 1.0


def _derive_metric_attrs(event: OpenHookEvent) -> dict[str, str]:
    legacy = event.extensions.get("legacy_payload", {})
    # Explicit metric_attributes takes precedence (e.g., OpenCode plugin format)
    if isinstance(legacy.get("metric_attributes"), dict):
        return {k: str(v) for k, v in legacy["metric_attributes"].items() if v is not None}
    attrs: dict[str, str] = {}
    for key in ("tool_name", "tool_call_id", "prompt_length"):
        val = event.data.get(key)
        if val is not None:
            attrs[key] = str(val)
    cwd = _context_to_cwd(event.context)
    if cwd:
        attrs["cwd"] = str(cwd)
    return attrs


def _is_metric_event(event: OpenHookEvent) -> bool:
    """True if the event should be routed to emit_metric."""
    if event.is_trace:
        return False
    if event.type in _METRIC_EVENT_TYPES:
        return True
    # Handle explicit metric payloads (e.g., OpenCode plugin format)
    legacy = event.extensions.get("legacy_payload", {})
    return legacy.get("kind") == "metric"


def _run_attribution(turns: list, event: Any, config: dict[str, Any], provider: Any) -> None:
    """Emit agent-trace file attribution via the provider pipeline."""
    if not turns:
        return
    if not config.get("attribution", {}).get("enabled", False):
        return
    try:
        from otel_hooks.attribution import build_file_records
        from otel_hooks.attribution.extractor import detect_repo_root, extract_file_ops

        source = event.source if hasattr(event, "source") else getattr(event, "source_tool", "")
        ops = extract_file_ops(turns, source)
        if not ops:
            return

        cwd = _context_to_cwd(event.context) if hasattr(event, "context") else getattr(event, "cwd", None)
        repo_root = detect_repo_root([op.abs_path for op in ops], fallback=cwd)
        if repo_root is None:
            logger.debug("attribution: cannot detect repo root; skipping")
            return

        file_records = build_file_records(ops, repo_root.resolve())
        if not file_records:
            return

        provider.emit_attribution(event.session_id, file_records, source)
    except Exception:
        logger.debug("Attribution emit failed", exc_info=True)


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

    if event.is_trace:
        if event.transcript_path is not None and not event.transcript_path.exists():
            logger.debug("Transcript file not found; exiting.")
            return 0
        if event.transcript_path is None:
            logger.debug(
                "No transcript path for %s; session-only trace not yet supported.",
                event.source,
            )
            return 0

    provider = provider_factory(provider_name, config)
    if not provider:
        logger.warning("Failed to create provider: %s", provider_name)
        return 1

    emitted = 0
    attributed_turns: list = []
    try:
        if _is_metric_event(event):
            try:
                provider.emit_metric(
                    _derive_metric_name(event),
                    _derive_metric_value(event),
                    _derive_metric_attrs(event),
                    event.source,
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
                _derive_metric_name(event),
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
                        event.source,
                    )
                except Exception:
                    logger.warning("emit_turn failed", exc_info=True)
                    emit_failed = True
                    break
                attributed_turns.append(turn)
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

        _run_attribution(attributed_turns, event, config, provider)

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
