from __future__ import annotations

import tests._path_setup  # noqa: F401

import unittest

from otel_hooks.domain.transcript import Turn
from otel_hooks.providers.common import build_turn_payload


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
            tool_results_by_id={"t1": {"ok": True}},
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
            tool_results_by_id={"t1": long},
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
