from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_upstream_specs as checker  # noqa: E402


# A small, tool-shaped event surface.  Each tuple is
# (existing event, another existing event, newly added upstream event).
TOOL_EVENTS = {
    "claude": ("SessionStart", "Stop", "NewClaudeEvent"),
    "cursor": ("sessionStart", "stop", "newCursorEvent"),
    "codex": ("SessionStart", "Stop", "NewCodexEvent"),
    "opencode": ("session.created", "session.idle", "session.archived"),
    "gemini": ("SessionStart", "SessionEnd", "NewGeminiEvent"),
    "cline": ("session_start", "run_end", "new_cline_event"),
    "copilot": ("sessionStart", "sessionEnd", "newCopilotEvent"),
    "kiro": ("SessionStart", "Stop", "NewKiroEvent"),
}

BASE_FIELDS = ("session_id", "tool_name")


def _event_table(events: tuple[str, ...] | list[str]) -> str:
    rows = ["## Hook Events", "", "| Event | Description |", "|---|---|"]
    rows.extend(f"| `{event}` | Fixture event |" for event in events)
    return "\n".join(rows)


def _payload_block(fields: tuple[str, ...] | list[str]) -> str:
    payload = {field: "string" for field in fields}
    return "\n".join([
        "## Payload Fields",
        "",
        "```json",
        json.dumps(payload, indent=2),
        "```",
    ])


def _spec(events: tuple[str, ...] | list[str], fields: tuple[str, ...] | list[str]) -> str:
    return f"# Fixture spec\n\n{_event_table(events)}\n\n{_payload_block(fields)}\n"


def _upstream(events: tuple[str, ...] | list[str], fields: tuple[str, ...] | list[str]) -> str:
    return f"# Upstream fixture\n\n{_event_table(events)}\n\n{_payload_block(fields)}\n"


class UpstreamSpecCheckerTest(unittest.TestCase):
    def _check(
        self,
        tool: str,
        local_events: tuple[str, ...] | list[str],
        upstream_events: tuple[str, ...] | list[str],
        local_fields: tuple[str, ...] | list[str] = BASE_FIELDS,
        upstream_fields: tuple[str, ...] | list[str] = BASE_FIELDS,
    ) -> list[checker.SpecDiff]:
        with tempfile.TemporaryDirectory() as td:
            specs_dir = Path(td)
            (specs_dir / f"{tool}.md").write_text(
                _spec(local_events, local_fields), encoding="utf-8"
            )
            with patch.object(checker, "SPECS_DIR", specs_dir), patch.object(
                checker,
                "fetch_page",
                return_value=_upstream(upstream_events, upstream_fields),
            ):
                return checker.check_tool(tool)

    def test_event_patterns_cover_every_supported_tool(self) -> None:
        self.assertEqual(set(checker.EVENT_PATTERNS), set(checker.UPSTREAM_URLS))

    def test_snapshots_expose_an_event_and_payload_surface_for_every_tool(self) -> None:
        for tool in checker.UPSTREAM_URLS:
            with self.subTest(tool=tool):
                spec_path = checker.SPECS_DIR / f"{tool}.md"
                self.assertTrue(checker.extract_events_from_spec(spec_path, tool))
                self.assertTrue(checker.extract_json_fields_from_spec(spec_path))

    def test_html_nested_event_headings_exclude_other_sections(self) -> None:
        html = """
        <h2>Hook Events</h2>
        <h3>SessionStart</h3><p>Begins a session.</p>
        <h3>Stop</h3><p>Ends a session.</p>
        <h2>Configuration</h2>
        <h3>Timeout</h3><p>Maximum duration.</p>
        """
        self.assertEqual(
            checker.extract_events_from_html(html, "claude"),
            {"SessionStart", "Stop"},
        )

    def test_html_fixture_extracts_events_and_payload_fields(self) -> None:
        html = """
        <h2>Hook Events</h2>
        <table>
          <tr><th>Event</th><th>Description</th></tr>
          <tr><td><code>SessionStart</code></td><td>start</td></tr>
          <tr><td><code>NewEvent</code></td><td>new</td></tr>
        </table>
        <h2>Per-Event Input</h2>
        <pre><code>{"session_id": "string", "new_field": 1}</code></pre>
        """
        self.assertEqual(
            checker.extract_events_from_html(html, "claude"),
            {"SessionStart", "NewEvent"},
        )
        self.assertEqual(
            checker.extract_fields_from_html(html),
            {"session_id", "new_field"},
        )

    def test_html_non_content_does_not_create_spec_drift(self) -> None:
        page = """
        <SCRIPT type="application/json">{"analytics_id": 1}</SCRIPT>
        <style>body:after { content: '{"theme_id":1}'; }</style>
        <!-- <h2>Hook Events</h2><h3>GhostEvent</h3>{"comment_id":1} -->
        <h2>Hook Events</h2><h3>SessionStart</h3>
        <h2>Payload</h2><pre><code>{"session_id":"s"}</code></pre>
        """
        self.assertEqual(checker.extract_events_from_html(page, "claude"), {"SessionStart"})
        self.assertEqual(checker.extract_fields_from_html(page), {"session_id"})

    def test_snapshot_metadata_does_not_affect_drift_detection(self) -> None:
        events = ("SessionStart", "Stop")
        with tempfile.TemporaryDirectory() as td:
            specs_dir = Path(td)
            (specs_dir / "claude.md").write_text(
                "> Snapshot: 2026-01-01\n\n" + _spec(events, BASE_FIELDS),
                encoding="utf-8",
            )
            upstream = "> Snapshot: 2030-01-01\n\n" + _upstream(events, BASE_FIELDS)
            with patch.object(checker, "SPECS_DIR", specs_dir), patch.object(
                checker, "fetch_page", return_value=upstream
            ):
                diffs = checker.check_tool("claude")

        self.assertEqual(diffs, [])

    def test_added_upstream_event_is_reported_for_every_tool(self) -> None:
        for tool, (first, second, added) in TOOL_EVENTS.items():
            with self.subTest(tool=tool):
                diffs = self._check(
                    tool,
                    local_events=(first, second),
                    upstream_events=(first, second, added),
                )
                self.assertIn("new_events", {diff.category for diff in diffs})
                detail = next(d.detail for d in diffs if d.category == "new_events")
                self.assertIn(added, detail)

    def test_removed_upstream_event_is_reported_for_every_tool(self) -> None:
        for tool, (first, second, removed) in TOOL_EVENTS.items():
            with self.subTest(tool=tool):
                diffs = self._check(
                    tool,
                    local_events=(first, second, removed),
                    upstream_events=(first, second),
                )
                self.assertIn("removed_events", {diff.category for diff in diffs})
                detail = next(d.detail for d in diffs if d.category == "removed_events")
                self.assertIn(removed, detail)

    def test_added_upstream_payload_field_is_reported_for_every_tool(self) -> None:
        for tool, (first, second, _added_event) in TOOL_EVENTS.items():
            with self.subTest(tool=tool):
                diffs = self._check(
                    tool,
                    local_events=(first, second),
                    upstream_events=(first, second),
                    local_fields=BASE_FIELDS,
                    upstream_fields=(*BASE_FIELDS, "new_field"),
                )
                self.assertIn("new_fields", {diff.category for diff in diffs})
                detail = next(d.detail for d in diffs if d.category == "new_fields")
                self.assertIn("new_field", detail)

    def test_removed_upstream_payload_field_is_reported_for_every_tool(self) -> None:
        for tool, (first, second, _added_event) in TOOL_EVENTS.items():
            with self.subTest(tool=tool):
                diffs = self._check(
                    tool,
                    local_events=(first, second),
                    upstream_events=(first, second),
                    local_fields=(*BASE_FIELDS, "removed_field"),
                    upstream_fields=BASE_FIELDS,
                )
                self.assertIn("removed_fields", {diff.category for diff in diffs})
                detail = next(d.detail for d in diffs if d.category == "removed_fields")
                self.assertIn("removed_field", detail)


if __name__ == "__main__":
    unittest.main()
