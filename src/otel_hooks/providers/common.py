"""Shared provider payload building logic."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from otel_hooks.domain.transcript import (
    MAX_CHARS_DEFAULT,
    ToolResultRecord,
    Turn,
    extract_text,
    get_content,
    get_cwd,
    get_git_branch,
    get_model,
    get_timestamp,
    get_usage,
    iter_tool_uses,
    truncate_text,
)

_SUBAGENT_TOOL_NAMES = frozenset({"Task", "Agent"})


@dataclass
class ToolCall:
    id: str
    name: str
    input: Any
    output: str | None
    input_meta: dict[str, Any] | None
    output_meta: dict[str, Any] | None
    duration_s: float | None = None
    subagent_type: str | None = None


@dataclass
class AssistantMessageInfo:
    """Per-assistant-message metrics for granular generation observations."""

    model: str
    text: str
    text_meta: dict[str, Any]
    usage: dict[str, int]


@dataclass
class TurnPayload:
    user_text: str
    user_text_meta: dict[str, Any]
    assistant_text: str
    assistant_text_meta: dict[str, Any]
    model: str
    tool_calls: list[ToolCall]
    turn_duration_s: float | None = None
    usage: dict[str, int] = field(default_factory=dict)
    assistants: list[AssistantMessageInfo] = field(default_factory=list)
    cwd: str | None = None
    git_branch: str | None = None


def _tool_calls_from_assistants(assistant_msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for am in assistant_msgs:
        request_ts = get_timestamp(am)
        for tu in iter_tool_uses(get_content(am)):
            tid = tu.get("id") or ""
            name = tu.get("name") or "unknown"
            raw_input = tu.get("input")
            input_obj = raw_input if isinstance(raw_input, (dict, list, str, int, float, bool)) else {}
            subagent_type: str | None = None
            if name in _SUBAGENT_TOOL_NAMES and isinstance(raw_input, dict):
                st = raw_input.get("subagent_type")
                if isinstance(st, str) and st:
                    subagent_type = st
            calls.append(
                {
                    "id": str(tid),
                    "name": name,
                    "input": input_obj,
                    "request_ts": request_ts,
                    "subagent_type": subagent_type,
                }
            )
    return calls


def _aggregate_usage(per_msg: list[dict[str, int]]) -> dict[str, int]:
    """Sum output_tokens across assistant messages, take MAX of input/cache (monotonic per turn).

    Within a turn, the assistant input grows as tool_results accumulate, so the *peak* input
    represents that turn's true context-window load. Output tokens are produced incrementally,
    so they are summed.
    """
    if not per_msg:
        return {}
    agg: dict[str, int] = {}
    for u in per_msg:
        for k, v in u.items():
            if k == "output_tokens":
                agg[k] = agg.get(k, 0) + v
            else:
                agg[k] = max(agg.get(k, 0), v)
    return agg


def build_turn_payload(turn: Turn, *, max_chars: int = MAX_CHARS_DEFAULT) -> TurnPayload:
    user_text_raw = extract_text(get_content(turn.user_msg))
    user_text, user_text_meta = truncate_text(user_text_raw, max_chars)

    last_assistant = turn.assistant_msgs[-1]
    assistant_text_raw = extract_text(get_content(last_assistant))
    assistant_text, assistant_text_meta = truncate_text(assistant_text_raw, max_chars)

    model = get_model(turn.assistant_msgs[0])
    raw_tool_calls = _tool_calls_from_assistants(turn.assistant_msgs)

    tool_calls: list[ToolCall] = []
    for c in raw_tool_calls:
        input_obj = c["input"]
        input_meta: dict[str, Any] | None = None
        if isinstance(input_obj, str):
            input_obj, input_meta = truncate_text(input_obj, max_chars)

        output: str | None = None
        output_meta: dict[str, Any] | None = None
        duration_s: float | None = None
        if c["id"] and c["id"] in turn.tool_results_by_id:
            record: ToolResultRecord = turn.tool_results_by_id[c["id"]]
            out_raw = record.content
            out_str = out_raw if isinstance(out_raw, str) else json.dumps(out_raw, ensure_ascii=False)
            output, output_meta = truncate_text(out_str, max_chars)
            req_ts = c.get("request_ts")
            if req_ts is not None and record.timestamp is not None:
                delta = (record.timestamp - req_ts).total_seconds()
                if delta >= 0:
                    duration_s = delta

        tool_calls.append(
            ToolCall(
                id=c["id"],
                name=c["name"],
                input=input_obj,
                output=output,
                input_meta=input_meta,
                output_meta=output_meta,
                duration_s=duration_s,
                subagent_type=c.get("subagent_type"),
            )
        )

    assistants: list[AssistantMessageInfo] = []
    per_msg_usage: list[dict[str, int]] = []
    for am in turn.assistant_msgs:
        usage = get_usage(am)
        per_msg_usage.append(usage)
        text_raw = extract_text(get_content(am))
        text, text_meta = truncate_text(text_raw, max_chars)
        assistants.append(
            AssistantMessageInfo(
                model=get_model(am),
                text=text,
                text_meta=text_meta,
                usage=usage,
            )
        )

    user_ts = get_timestamp(turn.user_msg)
    last_ts = get_timestamp(last_assistant)
    duration: float | None = None
    if user_ts and last_ts and last_ts >= user_ts:
        duration = (last_ts - user_ts).total_seconds()

    return TurnPayload(
        user_text=user_text,
        user_text_meta=user_text_meta,
        assistant_text=assistant_text,
        assistant_text_meta=assistant_text_meta,
        model=model,
        tool_calls=tool_calls,
        turn_duration_s=duration,
        usage=_aggregate_usage(per_msg_usage),
        assistants=assistants,
        cwd=get_cwd(turn.user_msg),
        git_branch=get_git_branch(turn.user_msg),
    )
