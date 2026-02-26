"""Agent-trace file attribution extraction.

Extracts file-write/edit operations from Turn tool calls and builds
FileRecord objects.  Emission is handled by the Provider pipeline.

Usage (from hook.py):
    ops = extract_file_ops(turns, source_tool)
    repo_root = detect_repo_root([op.abs_path for op in ops], fallback=cwd)
    records = build_file_records(ops, repo_root.resolve())
    provider.emit_attribution(session_id, records, source_tool)
"""

from __future__ import annotations

import logging
from pathlib import Path

from otel_hooks.attribution.extractor import FileOp
from otel_hooks.attribution.record import (
    Contributor,
    Conversation,
    FileRecord,
    Range,
)

logger = logging.getLogger(__name__)


def build_file_records(ops: list[FileOp], repo_root: Path) -> list[FileRecord]:
    """Convert ordered FileOp list into agent-trace FileRecords.

    - Groups ops by file; last Write wins for line count.
    - Falls back to reading current file on disk for edit-only files.
    - Files outside repo_root are silently skipped.
    """
    # Group ops by file, preserving first-seen order
    file_ops: dict[Path, list[FileOp]] = {}
    for op in ops:
        file_ops.setdefault(op.abs_path, []).append(op)

    records: list[FileRecord] = []
    for abs_path, path_ops in file_ops.items():
        try:
            rel_path = abs_path.relative_to(repo_root).as_posix()
        except ValueError:
            logger.debug("attribution: %s outside repo root %s; skipping", abs_path, repo_root)
            continue

        line_count = _resolve_line_count(abs_path, path_ops)
        if not line_count:
            continue

        model = path_ops[-1].model or None
        if model == "unknown":
            model = None

        records.append(
            FileRecord(
                path=rel_path,
                conversations=[
                    Conversation(
                        contributor=Contributor(type="ai", model=model),
                        ranges=[Range(start_line=1, end_line=line_count)],
                    )
                ],
            )
        )

    return records


def _resolve_line_count(abs_path: Path, ops: list[FileOp]) -> int | None:
    """Return authoritative line count: last Write > current file on disk."""
    for op in reversed(ops):
        if op.kind == "write" and op.line_count is not None:
            return op.line_count

    if abs_path.exists():
        try:
            lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
            return len(lines) or None
        except OSError as e:
            logger.debug("attribution: cannot read %s: %s", abs_path, e)

    return None
