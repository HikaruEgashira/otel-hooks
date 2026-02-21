from __future__ import annotations

import tests._path_setup  # noqa: F401
import unittest

from otel_hooks.tools import parse_hook_event


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

    def test_parse_hook_event_cursor_without_transcript(self) -> None:
        event = parse_hook_event({"conversation_id": "c1"})
        self.assertIsNotNone(event)
        self.assertEqual(event.source_tool, "cursor")
        self.assertEqual(event.session_id, "c1")
        self.assertIsNone(event.transcript_path)

    def test_parse_hook_event_returns_none_for_unknown_payload(self) -> None:
        event = parse_hook_event({"foo": "bar"})
        self.assertIsNone(event)

    def test_parse_hook_event_for_cline_payload(self) -> None:
        payload = {"taskId": "t1", "clineVersion": "3.36"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source_tool, "cline")
        self.assertEqual(event.session_id, "t1")
        self.assertIsNone(event.transcript_path)

    def test_parse_hook_event_for_codex_payload(self) -> None:
        payload = {"thread-id": "th1", "type": "agent-turn-complete"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source_tool, "codex")
        self.assertEqual(event.session_id, "th1")
        self.assertIsNone(event.transcript_path)

    def test_parse_hook_event_for_gemini_payload(self) -> None:
        payload = {"session_id": "g1", "timestamp": "2025-01-01T00:00:00Z", "transcript_path": ""}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source_tool, "gemini")
        self.assertEqual(event.session_id, "g1")
        self.assertIsNone(event.transcript_path)


if __name__ == "__main__":
    unittest.main()
