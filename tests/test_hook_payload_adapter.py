from __future__ import annotations

import tests._path_setup  # noqa: F401
import unittest

from openhook import EventType
from otel_hooks.tools import parse_hook_event


class HookPayloadAdapterTest(unittest.TestCase):
    def test_parse_hook_event_for_claude_payload(self) -> None:
        payload = {
            "sessionId": "s1",
            "transcriptPath": "./transcript.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "claude-code")
        self.assertIsNotNone(event.transcript_path)
        self.assertEqual(event.transcript_path.name, "transcript.jsonl")
        self.assertEqual(event.session_id, "s1")

    def test_parse_hook_event_for_cursor_payload(self) -> None:
        payload = {
            "conversation_id": "c1",
            "transcript_path": "./cursor.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cursor")
        self.assertIsNotNone(event.transcript_path)
        self.assertEqual(event.transcript_path.name, "cursor.jsonl")
        self.assertEqual(event.session_id, "c1")

    def test_parse_hook_event_prefers_cursor_when_payload_is_ambiguous(self) -> None:
        payload = {
            "conversation_id": "cursor-1",
            "sessionId": "claude-1",
            "transcriptPath": "./shared.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cursor")
        self.assertEqual(event.session_id, "cursor-1")

    def test_parse_hook_event_cursor_without_transcript(self) -> None:
        event = parse_hook_event({"conversation_id": "c1"})
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cursor")
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.session_id, "c1")

    def test_parse_hook_event_returns_none_for_unknown_payload(self) -> None:
        event = parse_hook_event({"foo": "bar"})
        self.assertIsNone(event)

    def test_parse_hook_event_for_cline_payload(self) -> None:
        payload = {"taskId": "t1", "clineVersion": "3.36"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "cline")
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.session_id, "t1")

    def test_parse_hook_event_for_codex_payload(self) -> None:
        payload = {"thread-id": "th1", "type": "agent-turn-complete"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "codex")
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.session_id, "th1")

    def test_parse_hook_event_for_gemini_payload(self) -> None:
        payload = {"session_id": "g1", "timestamp": "2025-01-01T00:00:00Z", "transcript_path": ""}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "gemini")
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.session_id, "g1")

    def test_parse_hook_event_for_copilot_metrics_payload(self) -> None:
        payload = {"hook_event_name": "PreToolUse", "tool_name": "bash", "cwd": "/tmp"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.TOOL_START)
        self.assertIsNone(event.transcript_path)
        self.assertEqual(event.data.get("tool_name"), "bash")

    def test_parse_hook_event_for_copilot_metrics_payload_lower_camel(self) -> None:
        payload = {
            "source_tool": "copilot",
            "hook_event_name": "preToolUse",
            "tool_name": "bash",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "copilot")
        self.assertEqual(event.type, EventType.TOOL_START)
        self.assertEqual(event.data.get("tool_name"), "bash")

    def test_parse_hook_event_uses_source_tool_hint_for_ambiguous_payload(self) -> None:
        payload = {
            "source_tool": "kiro",
            "hook_event_name": "preToolUse",
            "tool_name": "bash",
            "cwd": "/tmp",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")

    def test_parse_hook_event_for_kiro_metrics_payload(self) -> None:
        payload = {"hook_event_name": "userPromptSubmit", "prompt": "hello", "cwd": "/tmp"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "kiro")
        self.assertEqual(event.type, EventType.PROMPT_SUBMIT)
        self.assertIsNone(event.transcript_path)

    def test_parse_hook_event_for_opencode_plugin_trace_payload(self) -> None:
        payload = {
            "source_tool": "opencode",
            "opencode_event_type": "message.part.updated",
            "session_id": "o1",
            "transcript_path": "./opencode.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "opencode")
        self.assertIsNotNone(event.transcript_path)
        self.assertEqual(event.transcript_path.name, "opencode.jsonl")
        self.assertEqual(event.session_id, "o1")

    def test_parse_hook_event_for_opencode_plugin_metric_payload(self) -> None:
        payload = {
            "source_tool": "opencode",
            "kind": "metric",
            "session_id": "o1",
            "metric_name": "tool_completed",
            "metric_value": 1,
            "metric_attributes": {"tool_name": "read"},
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "opencode")
        self.assertIsNone(event.transcript_path)
        # Legacy payload preserved in extensions
        legacy = event.extensions.get("legacy_payload", {})
        self.assertEqual(legacy.get("metric_name"), "tool_completed")
        self.assertEqual(legacy.get("metric_attributes", {}).get("tool_name"), "read")

    def test_parse_hook_event_prefers_gemini_over_claude_when_session_id_and_timestamp_exist(self) -> None:
        payload = {
            "session_id": "g2",
            "timestamp": "2025-01-01T00:00:00Z",
            "transcript_path": "./gemini.jsonl",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertEqual(event.source, "gemini")
        self.assertEqual(event.session_id, "g2")
        self.assertEqual(event.transcript_path.name, "gemini.jsonl")


if __name__ == "__main__":
    unittest.main()
