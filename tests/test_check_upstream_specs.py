from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "upstream-specs"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_upstream_specs as checker  # noqa: E402


BASE_FIELDS = ("session_id", "hook_event_name")
EVENT_FIXTURES = {
    "claude": ("NewClaudeEvent", "<h3>NewClaudeEvent</h3>", "<h3>Stop</h3>"),
    "cursor": ("newCursorEvent", "<h4>newCursorEvent</h4>", "<h4>sessionStart</h4>"),
    "gemini": ("NewGeminiEvent", "<tr><td><code>NewGeminiEvent</code></td><td>new</td></tr>",
               "<tr><td><code>AfterTool</code></td><td>A tool completes</td></tr>"),
    "opencode": ("session.restored", "<li><code>session.restored</code></li>",
                 "<li><code>tool.execute.before</code></li>"),
    "copilot": ("newCopilotEvent", "<tr><td><code>newCopilotEvent</code></td><td>new</td></tr>",
                "<tr><td><code>sessionStart</code></td><td>A new session starts</td></tr>"),
}
PAYLOAD_FIXTURES = {
    "claude": ("new_claude_field", "<tr><td><code>new_claude_field</code></td><td>new</td></tr>",
               "<tr><td><code>hook_event_name</code></td><td>Firing event</td></tr>"),
    "cursor": ("newCursorField", ',"newCursorField":"x"', ',"generation_id":"g"'),
    "copilot": ("newField", "\n  newField?: string;", "  sessionId: string;"),
}


def _event_table(events: tuple[str, ...] | list[str]) -> str:
    rows = ["## Hook Events", "", "| Event | Description |", "|---|---|"]
    rows.extend(f"| `{event}` | Fixture event |" for event in events)
    return "\n".join(rows)


def _payload_block(fields: tuple[str, ...] | list[str]) -> str:
    payload = {field: "string" for field in fields}
    return "\n".join([
        "## Common Input Fields",
        "",
        "```json",
        json.dumps(payload, indent=2),
        "```",
    ])


def _spec(events: tuple[str, ...] | list[str], fields: tuple[str, ...] | list[str]) -> str:
    return f"# Fixture spec\n\n{_event_table(events)}\n\n{_payload_block(fields)}\n"


def _upstream(events: tuple[str, ...] | list[str], fields: tuple[str, ...] | list[str]) -> str:
    rows = ["## Common Input Fields", "", "| Field | Description |", "|---|---|"]
    rows.extend(f"| `{field}` | Fixture field |" for field in fields)
    payload = "\n".join(rows)
    return f"# Upstream fixture\n\n{_event_table(events)}\n\n{payload}\n"


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

    def test_every_tool_is_checked_or_explicitly_unsupported(self) -> None:
        for tool in checker.UPSTREAM_URLS:
            with self.subTest(tool=tool):
                fixture = (FIXTURES / f"{tool}.html").read_text()
                events = checker._event_surface(fixture, tool)
                payload = checker._payload_surface(fixture, tool)
                self.assertTrue(events.values or events.reason)
                self.assertTrue(payload.values or payload.reason)
                if tool in EVENT_FIXTURES:
                    self.assertTrue(events.values, events.reason)
                else:
                    self.assertIsNone(events.values)
                    self.assertTrue(events.reason)
                if tool in PAYLOAD_FIXTURES:
                    self.assertTrue(payload.values, payload.reason)
                    if tool in {"claude", "cursor"}:
                        self.assertIn("event-specific", payload.reason)
                else:
                    self.assertIsNone(payload.values)
                    self.assertTrue(payload.reason)

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
        <h2>Hook input and output</h2>
        <h3>Common input fields</h3>
        <table><tr><th>Field</th><th>Description</th></tr>
          <tr><td><code>session_id</code></td><td>Current session</td></tr>
          <tr><td><code>new_field</code></td><td>New field</td></tr>
        </table>
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
        <h2>Hook input and output</h2>
        <h3>Common input fields</h3>
        <table><tr><th>Field</th><th>Description</th></tr>
          <tr><td><code>session_id</code></td><td>Current session</td></tr></table>
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

        self.assertEqual({diff.category for diff in diffs}, {"unsupported_payload"})

    def test_added_and_removed_upstream_events_are_reported_for_structured_surfaces(self) -> None:
        for tool, (added_name, addition, removal) in EVENT_FIXTURES.items():
            with self.subTest(tool=tool):
                fixture = (FIXTURES / f"{tool}.html").read_text()
                baseline = checker._event_surface(fixture, tool)
                self.assertTrue(baseline.values, baseline.reason)
                added = checker._event_surface(fixture.replace(removal, removal + addition, 1), tool)
                removed = checker._event_surface(fixture.replace(removal, "", 1), tool)
                self.assertIn(added_name, added.values - baseline.values)
                self.assertTrue(baseline.values - removed.values)

    def test_added_and_removed_payload_fields_are_reported_for_scoped_surfaces(self) -> None:
        for tool, (added_name, addition, removal) in PAYLOAD_FIXTURES.items():
            with self.subTest(tool=tool):
                fixture = (FIXTURES / f"{tool}.html").read_text()
                baseline = checker._payload_surface(fixture, tool)
                self.assertTrue(baseline.values, baseline.reason)
                added = checker._payload_surface(fixture.replace(removal, removal + addition, 1), tool)
                removed = checker._payload_surface(fixture.replace(removal, "", 1), tool)
                self.assertIn(added_name, added.values - baseline.values)
                self.assertTrue(baseline.values - removed.values)

    def test_unstructured_pages_are_reported_unsupported_instead_of_removed(self) -> None:
        for tool in ("codex", "cline", "kiro"):
            with self.subTest(tool=tool), patch.object(checker, "fetch_page",
                                                       return_value=(FIXTURES / f"{tool}.html").read_text()):
                diffs = checker.check_tool(tool)
            categories = {diff.category for diff in diffs}
            self.assertIn("unsupported_events", categories)
            self.assertIn("unsupported_payload", categories)
            self.assertFalse(any(category.startswith("removed_") for category in categories))

    def test_event_parser_ignores_payload_rows_and_navigation_prose(self) -> None:
        cursor = checker._event_surface((FIXTURES / "cursor.html").read_text(), "cursor")
        cline = checker._event_surface((FIXTURES / "cline.html").read_text(), "cline")
        opencode_html = (FIXTURES / "opencode.html").read_text()
        opencode = checker._event_surface(
            opencode_html + '<h3>Plugin example</h3><pre><code>{"fake.unlisted.event": async () => {}}</code></pre>',
            "opencode",
        )
        self.assertEqual(cursor.values, {"preToolUse", "sessionStart"})
        self.assertIsNone(cline.values)
        self.assertIn("registry", cline.reason)
        self.assertIn("experimental.session.compacting", opencode.values)
        self.assertNotIn("fake.unlisted.event", opencode.values)

    def test_short_event_table_row_is_reported_unsupported(self) -> None:
        html = """
        <h2>Hook Events</h2>
        <table>
          <tr><th>Description</th><th>Event</th></tr>
          <tr><td>only one cell</td></tr>
        </table>
        """
        surface = checker._event_surface(html, "claude")
        self.assertIsNone(surface.values)
        self.assertIn("missing its event column", surface.reason)

    def test_partial_payloads_are_never_reported_as_fully_checked(self) -> None:
        claude = checker._payload_surface((FIXTURES / "claude.html").read_text(), "claude")
        cursor = checker._payload_surface((FIXTURES / "cursor.html").read_text(), "cursor")
        self.assertEqual(claude.values, {"session_id", "hook_event_name"})
        self.assertIn("event-specific", claude.reason)
        self.assertIn("event-specific", cursor.reason)

    def test_payload_fields_after_escaped_table_pipes_are_kept(self) -> None:
        fields = checker._extract_table_fields([
            "| Event | Additional fields |",
            "|---|---|",
            r"| PreCompact | `trigger`: `manual\|auto`, `custom_instructions` |",
        ])
        self.assertEqual(fields, {"trigger", "custom_instructions"})


if __name__ == "__main__":
    unittest.main()
