from __future__ import annotations

import tests._path_setup  # noqa: F401

import unittest

from otel_hooks.domain.transcript import ToolResultRecord, Turn
from otel_hooks.providers.common import build_turn_payload


def _result(content, ts: str | None = None) -> ToolResultRecord:
    from datetime import datetime

    parsed = None
    if ts:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return ToolResultRecord(content=content, timestamp=parsed)


class ProviderCommonTest(unittest.TestCase):
    def test_build_turn_payload_collects_model_text_and_tool_io(self) -> None:
        turn = Turn(
            user_msg={
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello"}],
                },
            },
            assistant_msgs=[
                {
                    "type": "assistant",
                    "message": {
                        "id": "a1",
                        "role": "assistant",
                        "model": "gpt-5",
                        "content": [
                            {"type": "tool_use", "id": "t1", "name": "read", "input": "/tmp/a"}
                        ],
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "id": "a2",
                        "role": "assistant",
                        "model": "gpt-5",
                        "content": [{"type": "text", "text": "done"}],
                    },
                },
            ],
            tool_results_by_id={"t1": _result({"ok": True})},
        )

        payload = build_turn_payload(turn)

        self.assertEqual(payload.model, "gpt-5")
        self.assertEqual(payload.user_text, "hello")
        self.assertEqual(payload.assistant_text, "done")
        self.assertEqual(len(payload.tool_calls), 1)
        tool = payload.tool_calls[0]
        self.assertEqual(tool.id, "t1")
        self.assertEqual(tool.name, "read")
        self.assertEqual(tool.input, "/tmp/a")
        self.assertEqual(tool.output, '{"ok": true}')

    def test_build_turn_payload_extracts_duration_usage_and_project_context(self) -> None:
        turn = Turn(
            user_msg={
                "type": "user",
                "timestamp": "2026-04-28T10:00:00Z",
                "cwd": "/repo/proj",
                "gitBranch": "feat/x",
                "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]},
            },
            assistant_msgs=[
                {
                    "type": "assistant",
                    "timestamp": "2026-04-28T10:00:05Z",
                    "message": {
                        "id": "a1",
                        "role": "assistant",
                        "model": "claude-x",
                        "content": [{"type": "tool_use", "id": "t1", "name": "read", "input": {}}],
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 20,
                            "cache_read_input_tokens": 50,
                            "cache_creation_input_tokens": 10,
                        },
                    },
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-04-28T10:00:12Z",
                    "message": {
                        "id": "a2",
                        "role": "assistant",
                        "model": "claude-x",
                        "content": [{"type": "text", "text": "done"}],
                        "usage": {
                            "input_tokens": 200,
                            "output_tokens": 30,
                            "cache_read_input_tokens": 80,
                            "cache_creation_input_tokens": 5,
                        },
                    },
                },
            ],
            tool_results_by_id={"t1": _result("ok")},
        )

        payload = build_turn_payload(turn)

        self.assertEqual(payload.turn_duration_s, 12.0)
        self.assertEqual(payload.cwd, "/repo/proj")
        self.assertEqual(payload.git_branch, "feat/x")
        # output sums; input/cache take the peak.
        self.assertEqual(payload.usage["output_tokens"], 50)
        self.assertEqual(payload.usage["input_tokens"], 200)
        self.assertEqual(payload.usage["cache_read_input_tokens"], 80)
        self.assertEqual(payload.usage["cache_creation_input_tokens"], 10)
        self.assertEqual(len(payload.assistants), 2)
        self.assertEqual(payload.assistants[0].usage["input_tokens"], 100)
        self.assertEqual(payload.assistants[1].usage["input_tokens"], 200)

    def test_build_turn_payload_extracts_per_tool_duration_and_subagent_type(self) -> None:
        turn = Turn(
            user_msg={
                "type": "user",
                "timestamp": "2026-04-28T10:00:00Z",
                "message": {"role": "user", "content": [{"type": "text", "text": "go"}]},
            },
            assistant_msgs=[
                {
                    "type": "assistant",
                    "timestamp": "2026-04-28T10:00:00Z",
                    "message": {
                        "id": "a1",
                        "role": "assistant",
                        "model": "claude-x",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "task-1",
                                "name": "Task",
                                "input": {"description": "find bug", "subagent_type": "Explore"},
                            },
                            {
                                "type": "tool_use",
                                "id": "read-1",
                                "name": "Read",
                                "input": {"path": "/x"},
                            },
                        ],
                    },
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-04-28T10:00:14Z",
                    "message": {
                        "id": "a2",
                        "role": "assistant",
                        "model": "claude-x",
                        "content": [{"type": "text", "text": "done"}],
                    },
                },
            ],
            tool_results_by_id={
                "task-1": _result("explored", ts="2026-04-28T10:00:12Z"),
                "read-1": _result("body", ts="2026-04-28T10:00:00.5Z"),
            },
        )

        payload = build_turn_payload(turn)

        by_id = {tc.id: tc for tc in payload.tool_calls}
        self.assertAlmostEqual(by_id["task-1"].duration_s, 12.0, places=3)
        self.assertEqual(by_id["task-1"].subagent_type, "Explore")
        self.assertAlmostEqual(by_id["read-1"].duration_s, 0.5, places=3)
        self.assertIsNone(by_id["read-1"].subagent_type)

    def test_build_turn_payload_handles_missing_timestamps_and_usage(self) -> None:
        turn = Turn(
            user_msg={"message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}},
            assistant_msgs=[
                {
                    "message": {
                        "id": "a1",
                        "role": "assistant",
                        "model": "m",
                        "content": [{"type": "text", "text": "x"}],
                    }
                }
            ],
            tool_results_by_id={},
        )
        payload = build_turn_payload(turn)
        self.assertIsNone(payload.turn_duration_s)
        self.assertEqual(payload.usage, {})
        self.assertIsNone(payload.cwd)
        self.assertIsNone(payload.git_branch)

    def test_build_turn_payload_truncates_string_fields(self) -> None:
        long = "x" * 25050
        turn = Turn(
            user_msg={"message": {"content": [{"type": "text", "text": long}]}},
            assistant_msgs=[
                {
                    "message": {
                        "model": "m",
                        "content": [
                            {"type": "tool_use", "id": "t1", "name": "tool", "input": long},
                            {"type": "text", "text": long},
                        ],
                    }
                }
            ],
            tool_results_by_id={"t1": _result(long)},
        )

        payload = build_turn_payload(turn)

        self.assertEqual(len(payload.user_text), 20000)
        self.assertEqual(len(payload.assistant_text), 20000)
        self.assertTrue(payload.user_text_meta["truncated"])
        self.assertTrue(payload.assistant_text_meta["truncated"])
        self.assertEqual(len(payload.tool_calls[0].input), 20000)
        self.assertEqual(len(payload.tool_calls[0].output), 20000)
        self.assertTrue(payload.tool_calls[0].input_meta["truncated"])
        self.assertTrue(payload.tool_calls[0].output_meta["truncated"])


if __name__ == "__main__":
    unittest.main()
