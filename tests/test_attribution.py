"""Tests for the agent-trace attribution module."""

from __future__ import annotations

import tests._path_setup  # noqa: F401

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from otel_hooks.attribution.extractor import (
    FileOp,
    extract_file_ops,
    normalize_model,
)
from otel_hooks.attribution.record import (
    Contributor,
    Conversation,
    FileRecord,
    Range,
    ToolInfo,
    TraceRecord,
    VcsInfo,
)
from otel_hooks.attribution import build_file_records
from otel_hooks.domain.transcript import Turn


def _make_turn(tool_calls: list[dict], model: str = "claude-sonnet-4-6") -> Turn:
    """Build a minimal Turn containing the given tool_use blocks."""
    content = [
        {"type": "tool_use", "id": f"t{i}", "name": tc["name"], "input": tc["input"]}
        for i, tc in enumerate(tool_calls)
    ]
    return Turn(
        user_msg={"type": "user", "message": {"role": "user", "content": "go"}},
        assistant_msgs=[
            {
                "type": "assistant",
                "message": {
                    "id": "a1",
                    "role": "assistant",
                    "model": model,
                    "content": content,
                },
            }
        ],
        tool_results_by_id={},
    )


class NormalizeModelTest(unittest.TestCase):
    def test_claude_prefix(self) -> None:
        self.assertEqual(normalize_model("claude-sonnet-4-6", "claude"), "anthropic/claude-sonnet-4-6")

    def test_already_prefixed(self) -> None:
        self.assertEqual(normalize_model("anthropic/claude-sonnet-4-6", "claude"), "anthropic/claude-sonnet-4-6")

    def test_gemini_prefix(self) -> None:
        self.assertEqual(normalize_model("gemini-2.0-flash", "gemini"), "google/gemini-2.0-flash")

    def test_codex_prefix(self) -> None:
        self.assertEqual(normalize_model("gpt-4o", "codex"), "openai/gpt-4o")

    def test_unknown_passthrough(self) -> None:
        self.assertEqual(normalize_model("unknown", "claude"), "unknown")

    def test_no_prefix_for_unknown_tool(self) -> None:
        self.assertEqual(normalize_model("some-model", "kiro"), "some-model")


class ExtractFileOpsTest(unittest.TestCase):
    def test_write_tool_extracted(self) -> None:
        turn = _make_turn([
            {"name": "Write", "input": {"file_path": "/repo/src/main.py", "content": "line1\nline2\nline3"}}
        ])
        ops = extract_file_ops([turn], source_tool="claude")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].kind, "write")
        self.assertEqual(ops[0].abs_path, Path("/repo/src/main.py"))
        self.assertEqual(ops[0].line_count, 3)
        self.assertEqual(ops[0].model, "anthropic/claude-sonnet-4-6")

    def test_edit_tool_extracted_no_line_count(self) -> None:
        turn = _make_turn([
            {"name": "Edit", "input": {"file_path": "/repo/src/util.py", "old_string": "x", "new_string": "y"}}
        ])
        ops = extract_file_ops([turn], source_tool="claude")
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].kind, "edit")
        self.assertIsNone(ops[0].line_count)

    def test_non_file_tools_ignored(self) -> None:
        turn = _make_turn([
            {"name": "Bash", "input": {"command": "ls -la"}},
            {"name": "Read", "input": {"file_path": "/repo/src/main.py"}},
        ])
        ops = extract_file_ops([turn], source_tool="claude")
        self.assertEqual(ops, [])

    def test_missing_file_path_skipped(self) -> None:
        turn = _make_turn([{"name": "Write", "input": {"content": "hello"}}])
        ops = extract_file_ops([turn], source_tool="claude")
        self.assertEqual(ops, [])

    def test_multiple_turns_accumulate(self) -> None:
        t1 = _make_turn([{"name": "Write", "input": {"file_path": "/repo/a.py", "content": "x\ny"}}])
        t2 = _make_turn([{"name": "Write", "input": {"file_path": "/repo/b.py", "content": "z"}}])
        ops = extract_file_ops([t1, t2], source_tool="claude")
        self.assertEqual(len(ops), 2)
        self.assertEqual({op.abs_path.name for op in ops}, {"a.py", "b.py"})


class BuildFileRecordsTest(unittest.TestCase):
    def test_write_produces_full_range(self) -> None:
        ops = [FileOp(Path("/repo/src/foo.py"), "write", "anthropic/claude-sonnet-4-6", 10)]
        records = build_file_records(ops, Path("/repo"))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].path, "src/foo.py")
        conv = records[0].conversations[0]
        self.assertEqual(conv.contributor.type, "ai")
        self.assertEqual(conv.contributor.model, "anthropic/claude-sonnet-4-6")
        self.assertEqual(conv.ranges[0].start_line, 1)
        self.assertEqual(conv.ranges[0].end_line, 10)

    def test_outside_repo_root_skipped(self) -> None:
        ops = [FileOp(Path("/other/repo/file.py"), "write", "anthropic/model", 5)]
        records = build_file_records(ops, Path("/repo"))
        self.assertEqual(records, [])

    def test_unknown_model_omitted(self) -> None:
        ops = [FileOp(Path("/repo/src/foo.py"), "write", "unknown", 5)]
        records = build_file_records(ops, Path("/repo"))
        self.assertIsNone(records[0].conversations[0].contributor.model)

    def test_last_write_wins_for_line_count(self) -> None:
        ops = [
            FileOp(Path("/repo/src/foo.py"), "write", "anthropic/model", 5),
            FileOp(Path("/repo/src/foo.py"), "edit", "anthropic/model", None),
            FileOp(Path("/repo/src/foo.py"), "write", "anthropic/model", 20),
        ]
        records = build_file_records(ops, Path("/repo"))
        self.assertEqual(records[0].conversations[0].ranges[0].end_line, 20)


class TraceRecordSerializationTest(unittest.TestCase):
    def test_to_dict_minimal(self) -> None:
        record = TraceRecord(
            version="0.1.0",
            id="session-1",
            timestamp="2026-01-01T00:00:00+00:00",
            files=[
                FileRecord(
                    path="src/main.py",
                    conversations=[
                        Conversation(
                            contributor=Contributor(type="ai", model="anthropic/claude-sonnet-4-6"),
                            ranges=[Range(start_line=1, end_line=50)],
                        )
                    ],
                )
            ],
        )
        d = record.to_dict()
        self.assertEqual(d["version"], "0.1.0")
        self.assertEqual(d["id"], "session-1")
        self.assertNotIn("vcs", d)
        self.assertNotIn("tool", d)
        file_d = d["files"][0]
        self.assertEqual(file_d["path"], "src/main.py")
        conv_d = file_d["conversations"][0]
        self.assertEqual(conv_d["contributor"]["type"], "ai")
        self.assertEqual(conv_d["contributor"]["model"], "anthropic/claude-sonnet-4-6")
        self.assertEqual(conv_d["ranges"][0], {"start_line": 1, "end_line": 50})

    def test_to_dict_with_vcs_and_tool(self) -> None:
        record = TraceRecord(
            version="0.1.0",
            id="s1",
            timestamp="2026-01-01T00:00:00+00:00",
            files=[],
            vcs=VcsInfo(type="git", revision="abc123"),
            tool=ToolInfo(name="claude-code"),
        )
        d = record.to_dict()
        self.assertEqual(d["vcs"], {"type": "git", "revision": "abc123"})
        self.assertEqual(d["tool"], {"name": "claude-code"})

    def test_contributor_without_model_omits_model_key(self) -> None:
        record = TraceRecord(
            version="0.1.0",
            id="s1",
            timestamp="2026-01-01T00:00:00+00:00",
            files=[
                FileRecord(
                    path="a.py",
                    conversations=[
                        Conversation(
                            contributor=Contributor(type="ai"),
                            ranges=[Range(1, 10)],
                        )
                    ],
                )
            ],
        )
        d = record.to_dict()
        self.assertNotIn("model", d["files"][0]["conversations"][0]["contributor"])


class RunAttributionTest(unittest.TestCase):
    """Tests for the hook._run_attribution orchestration."""

    @patch("otel_hooks.attribution.extractor.detect_repo_root")
    def test_calls_provider_emit_attribution(self, mock_root: MagicMock) -> None:
        import tempfile
        from otel_hooks.hook import _run_attribution

        with tempfile.TemporaryDirectory() as d:
            repo_root = Path(d).resolve()
            src = repo_root / "src"
            src.mkdir()
            target = src / "main.py"
            target.write_text("line1\nline2\n")

            mock_root.return_value = repo_root

            provider = MagicMock()
            event = MagicMock()
            event.source = "claude"
            event.session_id = "session-xyz"
            event.context = f"file://{repo_root}"

            turn = _make_turn([
                {"name": "Write", "input": {"file_path": str(target), "content": "line1\nline2\n"}}
            ])
            config = {"attribution": {"enabled": True}}
            _run_attribution([turn], event, config, provider)

            provider.emit_attribution.assert_called_once()
            call_args = provider.emit_attribution.call_args
            self.assertEqual(call_args[0][0], "session-xyz")          # session_id
            file_records = call_args[0][1]
            self.assertEqual(len(file_records), 1)
            self.assertEqual(file_records[0].path, "src/main.py")
            self.assertEqual(file_records[0].conversations[0].ranges[0].end_line, 2)

    def test_disabled_by_default_no_provider_call(self) -> None:
        from otel_hooks.hook import _run_attribution

        provider = MagicMock()
        event = MagicMock()
        event.source = "claude"
        event.session_id = "s1"
        event.context = None

        turn = _make_turn([
            {"name": "Write", "input": {"file_path": "/repo/x.py", "content": "hello"}}
        ])
        _run_attribution([turn], event, {}, provider)
        provider.emit_attribution.assert_not_called()

    def test_no_file_ops_no_provider_call(self) -> None:
        from otel_hooks.hook import _run_attribution

        provider = MagicMock()
        event = MagicMock()
        event.source = "claude"
        event.session_id = "s1"
        event.context = None

        # Turn with no Write/Edit tools
        turn = _make_turn([{"name": "Bash", "input": {"command": "ls"}}])
        _run_attribution([turn], event, {"attribution": {"enabled": True}}, provider)
        provider.emit_attribution.assert_not_called()


class HookEventCwdTest(unittest.TestCase):
    def test_cwd_extracted_from_claude_payload(self) -> None:
        from otel_hooks.tools import parse_hook_event
        from otel_hooks.hook import _context_to_cwd

        payload = {
            "sessionId": "s1",
            "transcriptPath": "/tmp/t.jsonl",
            "cwd": "/home/user/project",
        }
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertIsNotNone(event.context)
        # cwd is stored as file:// URI in event.context
        cwd = _context_to_cwd(event.context)
        self.assertIsNotNone(cwd)
        self.assertEqual(cwd, Path("/home/user/project"))

    def test_cwd_none_when_absent(self) -> None:
        from otel_hooks.tools import parse_hook_event
        from otel_hooks.hook import _context_to_cwd

        payload = {"sessionId": "s1", "transcriptPath": "/tmp/t.jsonl"}
        event = parse_hook_event(payload)
        self.assertIsNotNone(event)
        self.assertIsNone(_context_to_cwd(event.context))


if __name__ == "__main__":
    unittest.main()
