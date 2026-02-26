"""Agent-trace v0.1.0 record schema.

Spec: https://agent-trace.dev/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Range:
    start_line: int
    end_line: int


@dataclass
class Contributor:
    type: str  # "ai" | "human" | "mixed" | "unknown"
    model: str | None = None


@dataclass
class Conversation:
    contributor: Contributor
    ranges: list[Range]
    url: str | None = None


@dataclass
class FileRecord:
    path: str  # repo-root-relative, forward slashes
    conversations: list[Conversation]


@dataclass
class VcsInfo:
    type: str  # "git" | "jj" | "hg" | "svn"
    revision: str


@dataclass
class ToolInfo:
    name: str
    version: str | None = None


@dataclass
class TraceRecord:
    version: str
    id: str
    timestamp: str
    files: list[FileRecord]
    vcs: VcsInfo | None = None
    tool: ToolInfo | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "version": self.version,
            "id": self.id,
            "timestamp": self.timestamp,
            "files": [_file_to_dict(f) for f in self.files],
        }
        if self.vcs:
            d["vcs"] = {"type": self.vcs.type, "revision": self.vcs.revision}
        if self.tool:
            tool_d: dict[str, Any] = {"name": self.tool.name}
            if self.tool.version:
                tool_d["version"] = self.tool.version
            d["tool"] = tool_d
        return d


def _file_to_dict(f: FileRecord) -> dict[str, Any]:
    return {
        "path": f.path,
        "conversations": [_conv_to_dict(c) for c in f.conversations],
    }


def _conv_to_dict(c: Conversation) -> dict[str, Any]:
    contrib: dict[str, Any] = {"type": c.contributor.type}
    if c.contributor.model:
        contrib["model"] = c.contributor.model
    d: dict[str, Any] = {
        "contributor": contrib,
        "ranges": [{"start_line": r.start_line, "end_line": r.end_line} for r in c.ranges],
    }
    if c.url:
        d["url"] = c.url
    return d
