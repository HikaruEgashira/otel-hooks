"""Transcript domain model and parsing utilities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

MAX_CHARS_DEFAULT = 20000


@dataclass
class Turn:
    user_msg: dict[str, Any]
    assistant_msgs: list[dict[str, Any]]
    tool_results_by_id: dict[str, Any]


def get_content(msg: dict[str, Any]) -> Any:
    if not isinstance(msg, dict):
        return None
    if "message" in msg and isinstance(msg.get("message"), dict):
        return msg["message"].get("content")
    return msg.get("content")


def get_role(msg: dict[str, Any]) -> str | None:
    t = msg.get("type")
    if t in ("user", "assistant"):
        return t
    m = msg.get("message")
    if isinstance(m, dict):
        r = m.get("role")
        if r in ("user", "assistant"):
            return r
    return None


def is_tool_result(msg: dict[str, Any]) -> bool:
    if get_role(msg) != "user":
        return False
    content = get_content(msg)
    if not isinstance(content, list):
        return False
    return any(isinstance(x, dict) and x.get("type") == "tool_result" for x in content)


def iter_tool_results(content: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(content, list):
        for x in content:
            if isinstance(x, dict) and x.get("type") == "tool_result":
                out.append(x)
    return out


def iter_tool_uses(content: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(content, list):
        for x in content:
            if isinstance(x, dict) and x.get("type") == "tool_use":
                out.append(x)
    return out


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for x in content:
            if isinstance(x, dict) and x.get("type") == "text":
                parts.append(x.get("text", ""))
            elif isinstance(x, str):
                parts.append(x)
        return "\n".join([p for p in parts if p])
    return ""


def truncate_text(s: str, max_chars: int = MAX_CHARS_DEFAULT) -> tuple[str, dict[str, Any]]:
    if s is None:
        return "", {"truncated": False, "orig_len": 0}
    orig_len = len(s)
    if orig_len <= max_chars:
        return s, {"truncated": False, "orig_len": orig_len}
    head = s[:max_chars]
    return head, {
        "truncated": True,
        "orig_len": orig_len,
        "kept_len": len(head),
        "sha256": hashlib.sha256(s.encode("utf-8")).hexdigest(),
    }


def get_model(msg: dict[str, Any], default: str = "unknown") -> str:
    m = msg.get("message")
    if isinstance(m, dict):
        return m.get("model") or default
    return default


def get_message_id(msg: dict[str, Any]) -> str | None:
    m = msg.get("message")
    if isinstance(m, dict):
        mid = m.get("id")
        if isinstance(mid, str) and mid:
            return mid
    return None



def build_turns(messages: list[dict[str, Any]]) -> list[Turn]:
    turns: list[Turn] = []
    current_user: dict[str, Any] | None = None
    assistant_order: list[str] = []
    assistant_latest: dict[str, dict[str, Any]] = {}
    tool_results_by_id: dict[str, Any] = {}

    def flush_turn() -> None:
        nonlocal current_user, assistant_order, assistant_latest, tool_results_by_id
        if current_user is None or not assistant_latest:
            return
        assistants = [assistant_latest[mid] for mid in assistant_order if mid in assistant_latest]
        turns.append(
            Turn(
                user_msg=current_user,
                assistant_msgs=assistants,
                tool_results_by_id=dict(tool_results_by_id),
            )
        )

    for msg in messages:
        role = get_role(msg)
        if is_tool_result(msg):
            for tr in iter_tool_results(get_content(msg)):
                tid = tr.get("tool_use_id")
                if tid:
                    tool_results_by_id[str(tid)] = tr.get("content")
            continue
        if role == "user":
            flush_turn()
            current_user = msg
            assistant_order = []
            assistant_latest = {}
            tool_results_by_id = {}
            continue
        if role == "assistant":
            if current_user is None:
                continue
            mid = get_message_id(msg) or f"noid:{len(assistant_order)}"
            if mid not in assistant_latest:
                assistant_order.append(mid)
            assistant_latest[mid] = msg

    flush_turn()
    return turns


def decode_jsonl_lines(lines: list[str]) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            msgs.append(json.loads(line))
        except Exception:
            continue
    return msgs
