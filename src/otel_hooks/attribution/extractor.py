"""Extract file attribution data from Turn tool calls."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from otel_hooks.domain.transcript import Turn, get_content, get_model, iter_tool_uses

logger = logging.getLogger(__name__)

# Tool names that perform full-file writes (line_count deterministic from content)
_WRITE_TOOLS = frozenset({"Write", "write"})
# Tool names that perform partial edits (exact line range requires file read)
_EDIT_TOOLS = frozenset({"Edit", "edit", "MultiEdit", "multi_edit"})

# models.dev provider prefix by source_tool
_MODEL_PREFIXES: dict[str, str] = {
    "claude": "anthropic",
    "gemini": "google",
    "codex": "openai",
    "opencode": "openai",
}


@dataclass
class FileOp:
    """A single AI file-write or file-edit operation within a session."""

    abs_path: Path
    kind: str         # "write" | "edit"
    model: str        # models.dev convention, e.g. "anthropic/claude-sonnet-4-6"
    line_count: int | None  # populated for "write"; None for "edit"


def normalize_model(model: str, source_tool: str) -> str:
    """Convert raw model string to models.dev convention."""
    if model in ("unknown", ""):
        return model
    prefix = _MODEL_PREFIXES.get(source_tool)
    if prefix and not model.startswith(f"{prefix}/"):
        return f"{prefix}/{model}"
    return model


def extract_file_ops(turns: list[Turn], source_tool: str = "") -> list[FileOp]:
    """Scan turns for Write/Edit tool calls and return ordered FileOp list."""
    ops: list[FileOp] = []
    for turn in turns:
        model_raw = get_model(turn.assistant_msgs[0]) if turn.assistant_msgs else "unknown"
        model = normalize_model(model_raw, source_tool)

        for am in turn.assistant_msgs:
            for tu in iter_tool_uses(get_content(am)):
                name = tu.get("name") or ""
                inp = tu.get("input")
                if not isinstance(inp, dict):
                    continue

                path_str = inp.get("file_path") or inp.get("path")
                if not isinstance(path_str, str) or not path_str:
                    continue

                abs_path = Path(path_str).expanduser().resolve()

                if name in _WRITE_TOOLS:
                    content: str = inp.get("content") or ""
                    # splitlines() correctly handles trailing newlines: "a\nb\n" → 2
                    line_count = len(content.splitlines()) or None
                    ops.append(FileOp(abs_path, "write", model, line_count))
                elif name in _EDIT_TOOLS:
                    ops.append(FileOp(abs_path, "edit", model, None))

    return ops


def detect_repo_root(file_paths: list[Path], fallback: Path | None = None) -> Path | None:
    """Detect git repository root from absolute file paths via git rev-parse."""
    candidates: set[Path] = set()

    search_dirs = [p.parent for p in file_paths if p.is_absolute()]
    if fallback:
        search_dirs.append(fallback)

    for d in search_dirs:
        root = _git_toplevel(d)
        if root:
            candidates.add(root)

    if not candidates:
        return None
    # If multiple repos detected (unlikely), prefer the deepest common ancestor
    return min(candidates, key=lambda p: len(p.parts))


def get_git_revision(repo_root: Path) -> str | None:
    """Return the current HEAD commit SHA, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception as e:
        logger.debug("git rev-parse HEAD failed: %s", e)
    return None


def _git_toplevel(directory: Path) -> Path | None:
    if not directory.is_dir():
        directory = directory.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            toplevel = result.stdout.strip()
            return Path(toplevel) if toplevel else None
    except Exception as e:
        logger.debug("git rev-parse --show-toplevel failed in %s: %s", directory, e)
    return None
