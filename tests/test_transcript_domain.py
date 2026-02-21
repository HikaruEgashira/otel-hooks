from __future__ import annotations

import tests._path_setup  # noqa: F401

import hashlib
import unittest

from otel_hooks.domain import transcript


class TranscriptDomainTest(unittest.TestCase):
    def test_build_turns_groups_user_assistant_and_tool_results(self) -> None:
        messages = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "question"}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "id": "a1",
                    "role": "assistant",
                    "model": "claude-3",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "search",
                            "input": {"q": "otel"},
                        }
                    ],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "ok",
                        }
                    ],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "id": "a1",
                    "role": "assistant",
                    "model": "claude-3",
                    "content": [{"type": "text", "text": "final answer"}],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "next"}],
                },
            },
        ]

        turns = transcript.build_turns(messages)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].tool_results_by_id["tool-1"], "ok")
        # 同一 assistant id は最新版に置き換わる
        assistant_text = transcript.extract_text(transcript.get_content(turns[0].assistant_msgs[0]))
        self.assertEqual(assistant_text, "final answer")

    def test_decode_jsonl_lines_skips_invalid_json(self) -> None:
        lines = ['{"type":"user"}', "", "not-json", '{"type":"assistant"}']
        parsed = transcript.decode_jsonl_lines(lines)
        self.assertEqual(parsed, [{"type": "user"}, {"type": "assistant"}])

    def test_truncate_text_returns_hash_metadata(self) -> None:
        raw = "abcdef"
        truncated, meta = transcript.truncate_text(raw, max_chars=3)
        self.assertEqual(truncated, "abc")
        self.assertTrue(meta["truncated"])
        self.assertEqual(meta["orig_len"], 6)
        self.assertEqual(meta["kept_len"], 3)
        self.assertEqual(meta["sha256"], hashlib.sha256(raw.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    unittest.main()
