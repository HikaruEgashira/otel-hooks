"""Provider interface for otel-hooks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from otel_hooks.domain.transcript import Turn

if TYPE_CHECKING:
    from otel_hooks.attribution.record import FileRecord


@runtime_checkable
class Provider(Protocol):
    def emit_turn(
        self,
        session_id: str,
        turn_num: int,
        turn: Turn,
        transcript_path: Path | None,
        source_tool: str = "",
    ) -> None: ...
    def emit_metric(
        self,
        metric_name: str,
        metric_value: float,
        attributes: dict[str, str] | None = None,
        source_tool: str = "",
        session_id: str = "",
    ) -> None: ...
    def emit_attribution(
        self,
        session_id: str,
        file_records: list["FileRecord"],
        source_tool: str = "",
    ) -> None: ...
    def flush(self) -> None: ...
    def shutdown(self) -> None: ...
