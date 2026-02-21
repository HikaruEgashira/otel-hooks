"""Hook payload adapters to normalize tool-specific payloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class HookEvent:
    source_tool: str
    session_id: str
    transcript_path: Path


class PayloadAdapter(Protocol):
    name: str

    def matches(self, payload: dict[str, Any]) -> bool: ...

    def to_event(self, payload: dict[str, Any]) -> HookEvent | None: ...


class CursorPayloadAdapter:
    name = "cursor"

    def matches(self, payload: dict[str, Any]) -> bool:
        return "conversation_id" in payload

    def to_event(self, payload: dict[str, Any]) -> HookEvent | None:
        session_id = payload.get("conversation_id")
        transcript_path = _extract_transcript_path(payload)
        if not isinstance(session_id, str) or not session_id or transcript_path is None:
            return None
        return HookEvent(source_tool=self.name, session_id=session_id, transcript_path=transcript_path)


class ClaudeLikePayloadAdapter:
    name = "claude"

    def matches(self, payload: dict[str, Any]) -> bool:
        return any(k in payload for k in ("sessionId", "session_id")) or isinstance(
            payload.get("session"), dict
        )

    def to_event(self, payload: dict[str, Any]) -> HookEvent | None:
        session_id = (
            payload.get("sessionId")
            or payload.get("session_id")
            or payload.get("session", {}).get("id")
        )
        transcript_path = _extract_transcript_path(payload)
        if not isinstance(session_id, str) or not session_id or transcript_path is None:
            return None
        return HookEvent(source_tool=self.name, session_id=session_id, transcript_path=transcript_path)


_ADAPTERS: tuple[PayloadAdapter, ...] = (
    CursorPayloadAdapter(),
    ClaudeLikePayloadAdapter(),
)


def parse_hook_event(
    payload: dict[str, Any], warn_fn: Callable[[str], None] | None = None
) -> HookEvent | None:
    """Parse tool payload into a normalized HookEvent."""
    for adapter in _ADAPTERS:
        if not adapter.matches(payload):
            continue
        event = adapter.to_event(payload)
        if event is not None:
            return event
        if adapter.name == "cursor" and warn_fn is not None:
            warn_fn("Cursor hook: transcript path not available in payload. Tracing skipped.")
        return None
    return None


def _extract_transcript_path(payload: dict[str, Any]) -> Path | None:
    transcript = (
        payload.get("transcriptPath")
        or payload.get("transcript_path")
        or payload.get("transcript", {}).get("path")
    )
    if not transcript:
        return None
    try:
        return Path(transcript).expanduser().resolve()
    except Exception:
        return None
