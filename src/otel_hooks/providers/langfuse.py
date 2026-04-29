"""Langfuse provider using native SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langfuse import Langfuse, propagate_attributes

from otel_hooks.domain.transcript import MAX_CHARS_DEFAULT, Turn
from otel_hooks.providers.common import AssistantMessageInfo, build_turn_payload


_LF_USAGE_KEY_MAP = {
    "input_tokens": "input",
    "output_tokens": "output",
    "cache_read_input_tokens": "cache_read_input_tokens",
    "cache_creation_input_tokens": "cache_creation_input_tokens",
}


def _to_langfuse_usage(usage: dict[str, int]) -> dict[str, int]:
    return {_LF_USAGE_KEY_MAP[k]: v for k, v in usage.items() if k in _LF_USAGE_KEY_MAP}


class LangfuseProvider:
    def __init__(self, public_key: str, secret_key: str, host: str, *, max_chars: int = MAX_CHARS_DEFAULT) -> None:
        self._langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        self._max_chars = max_chars

    def emit_turn(self, session_id: str, turn_num: int, turn: Turn, transcript_path: Path | None, source_tool: str = "") -> None:
        payload = build_turn_payload(turn, max_chars=self._max_chars)
        metadata: dict[str, Any] = {
            "source": "otel-hooks",
            "session_id": session_id,
            "turn_number": turn_num,
            "user_text": payload.user_text_meta,
        }
        if transcript_path is not None:
            metadata["transcript_path"] = str(transcript_path)
        if source_tool:
            metadata["source_tool"] = source_tool
        if payload.turn_duration_s is not None:
            metadata["turn_duration_seconds"] = payload.turn_duration_s
        if payload.cwd:
            metadata["cwd"] = payload.cwd
        if payload.git_branch:
            metadata["git_branch"] = payload.git_branch
        if payload.usage:
            metadata["usage"] = payload.usage
        span_name = f"{source_tool} - Turn {turn_num}" if source_tool else f"AI Session - Turn {turn_num}"
        tags = ["otel-hooks"]
        if source_tool:
            tags.append(source_tool)
        with propagate_attributes(
            session_id=session_id,
            trace_name=span_name,
            tags=tags,
        ):
            with self._langfuse.start_as_current_span(
                name=span_name,
                input={"role": "user", "content": payload.user_text},
                metadata=metadata,
            ) as trace_span:
                assistants = payload.assistants or [
                    AssistantMessageInfo(
                        model=payload.model,
                        text=payload.assistant_text,
                        text_meta=payload.assistant_text_meta,
                        usage={},
                    )
                ]
                for idx, am in enumerate(assistants):
                    obs_kwargs: dict[str, Any] = {
                        "name": "Assistant Response",
                        "as_type": "generation",
                        "model": am.model,
                        "input": {"role": "user", "content": payload.user_text} if idx == 0 else None,
                        "output": {"role": "assistant", "content": am.text},
                        "metadata": {
                            "assistant_text": am.text_meta,
                            "message_index": idx,
                            "tool_count": len(payload.tool_calls) if idx == 0 else 0,
                        },
                    }
                    if am.usage:
                        obs_kwargs["usage_details"] = _to_langfuse_usage(am.usage)
                    with self._langfuse.start_as_current_observation(**obs_kwargs):
                        pass

                for tc in payload.tool_calls:
                    tool_meta: dict[str, Any] = {
                        "tool_name": tc.name,
                        "tool_id": tc.id,
                        "input_meta": tc.input_meta,
                        "output_meta": tc.output_meta,
                    }
                    if tc.duration_s is not None:
                        tool_meta["duration_seconds"] = tc.duration_s
                    if tc.subagent_type:
                        tool_meta["subagent_type"] = tc.subagent_type
                    with self._langfuse.start_as_current_observation(
                        name=f"Tool: {tc.name}",
                        as_type="tool",
                        input=tc.input,
                        metadata=tool_meta,
                    ) as tool_obs:
                        tool_obs.update(output=tc.output)

                trace_span.update(output={"role": "assistant", "content": payload.assistant_text})

    def emit_metric(
        self,
        metric_name: str,
        metric_value: float,
        attributes: dict[str, str] | None = None,
        source_tool: str = "",
        session_id: str = "",
    ) -> None:
        sid = session_id or "metrics"
        metadata: dict[str, Any] = {
            "source": "otel-hooks",
            "metric_name": metric_name,
            "metric_value": metric_value,
            "attributes": attributes or {},
        }
        if source_tool:
            metadata["source_tool"] = source_tool
        with propagate_attributes(
            session_id=sid,
            trace_name=f"Metric - {metric_name}",
            tags=["otel-hooks", "metric"],
        ):
            with self._langfuse.start_as_current_span(
                name=f"Metric - {metric_name}",
                input={"value": metric_value},
                metadata=metadata,
            ):
                pass

    def emit_attribution(
        self,
        session_id: str,
        file_records: list,
        source_tool: str = "",
    ) -> None:
        span_name = f"{source_tool} - Attribution" if source_tool else "AI Session - Attribution"
        tags = ["otel-hooks", "attribution"]
        if source_tool:
            tags.append(source_tool)

        with propagate_attributes(session_id=session_id, trace_name=span_name, tags=tags):
            with self._langfuse.start_as_current_span(
                name=span_name,
                metadata={
                    "source": "otel-hooks",
                    "session_id": session_id,
                    "source_tool": source_tool,
                    "file_count": len(file_records),
                },
            ):
                for f in file_records:
                    conv = f.conversations[0] if f.conversations else None
                    with self._langfuse.start_as_current_observation(
                        name=f"File: {f.path}",
                        as_type="span",
                        metadata={
                            "file_path": f.path,
                            "contributor": conv.contributor.type if conv else "unknown",
                            "model": conv.contributor.model if conv else None,
                            "ranges": (
                                [{"start": r.start_line, "end": r.end_line} for r in conv.ranges]
                                if conv else []
                            ),
                        },
                    ):
                        pass

    def flush(self) -> None:
        self._langfuse.flush()

    def shutdown(self) -> None:
        self._langfuse.shutdown()
