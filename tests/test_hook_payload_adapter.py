from __future__ import annotations

import tests._path_setup  # noqa: F401
import unittest
from pathlib import Path

from otel_hooks.adapters.hook_payload import parse_hook_event


class HookPayloadAdapterTest(unittest.TestCase):
    def test_parse_hook_event_for_claude_payload(self) -> None:
        payload = {
            "sessionId": "s1",
            "transcriptPath": "./transcript.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source_tool, "claude")
        self.assertEqual(event.session_id, "s1")
        self.assertEqual(event.transcript_path.name, "transcript.jsonl")

    def test_parse_hook_event_for_cursor_payload(self) -> None:
        payload = {
            "conversation_id": "c1",
            "transcript_path": "./cursor.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source_tool, "cursor")
        self.assertEqual(event.session_id, "c1")
        self.assertEqual(event.transcript_path.name, "cursor.jsonl")

    def test_parse_hook_event_warns_for_cursor_without_transcript(self) -> None:
        warnings: list[str] = []
        event = parse_hook_event({"conversation_id": "c1"}, warn_fn=warnings.append)
        self.assertIsNone(event)
        self.assertEqual(len(warnings), 1)
        self.assertIn("Cursor hook", warnings[0])

    def test_parse_hook_event_returns_none_for_unknown_payload(self) -> None:
        event = parse_hook_event({"foo": "bar"})
        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
