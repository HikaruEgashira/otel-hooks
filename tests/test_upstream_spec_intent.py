"""Validates that the upstream spec snapshots and checker config stay in sync.

These tests guard the invariants that the "sync upstream tool specs" change
established: the README source column must match the source line inside each
snapshot, and the checker's configured URL must agree with the snapshot.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_upstream_specs as checker  # noqa: E402

SPECS_DIR = ROOT / "docs" / "upstream-specs"
README = SPECS_DIR / "README.md"

_SOURCE_RE = re.compile(r"^>\s*Source:\s*(\S+)", re.MULTILINE)
_README_ROW_RE = re.compile(
    r"^\|\s*\[(?P<file>[a-z]+)\.md\]\((?P<file2>[a-z]+)\.md\)\s*\|\s*(?P<url>\S+)\s*\|",
    re.MULTILINE,
)


class SnapshotConsistencyTest(unittest.TestCase):
    def test_readme_lists_every_snapshot(self) -> None:
        rows = {m.group("file"): m.group("url") for m in _README_ROW_RE.finditer(README.read_text())}
        for tool in checker.UPSTREAM_URLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, rows)

    def test_every_snapshot_declares_a_source(self) -> None:
        for tool in checker.UPSTREAM_URLS:
            with self.subTest(tool=tool):
                spec = (SPECS_DIR / f"{tool}.md").read_text()
                self.assertIsNotNone(
                    _SOURCE_RE.search(spec),
                    f"{tool}.md is missing a Source line",
                )

    def test_cline_source_points_to_sdk_plugins(self) -> None:
        self.assertIn("https://docs.cline.bot/sdk/plugins", README.read_text())
        self.assertIn(
            "https://docs.cline.bot/sdk/plugins",
            (SPECS_DIR / "cline.md").read_text(),
        )
        self.assertEqual(checker.UPSTREAM_URLS["cline"], "https://docs.cline.bot/sdk/plugins")

    def test_codex_source_points_to_learn_chatgpt(self) -> None:
        url = "https://learn.chatgpt.com/docs/config-file/config-reference"
        self.assertIn(url, README.read_text())
        self.assertIn(url, (SPECS_DIR / "codex.md").read_text())
        self.assertEqual(checker.UPSTREAM_URLS["codex"], url)

    def test_kiro_source_points_to_hooks_root(self) -> None:
        url = "https://kiro.dev/docs/hooks/"
        self.assertIn(url, README.read_text())
        self.assertIn(url, (SPECS_DIR / "kiro.md").read_text())
        self.assertEqual(checker.UPSTREAM_URLS["kiro"], url)

    def test_every_snapshot_has_metadata(self) -> None:
        for tool in checker.UPSTREAM_URLS:
            with self.subTest(tool=tool):
                text = (SPECS_DIR / f"{tool}.md").read_text()
                self.assertIn("> Snapshot: 20", text)


class DraftedContentTest(unittest.TestCase):
    def test_claude_documents_managed_hooks(self) -> None:
        text = (SPECS_DIR / "claude.md").read_text()
        self.assertIn("allowManagedHooksOnly", text)
        self.assertIn("Subagent frontmatter", text)

    def test_copilot_documents_vscode_payload_format(self) -> None:
        text = (SPECS_DIR / "copilot.md").read_text()
        self.assertIn("VS Code compatible", text)
        self.assertIn("hook_event_name", text)

    def test_codex_documents_mcp_tool_handlers(self) -> None:
        text = (SPECS_DIR / "codex.md").read_text()
        self.assertIn("mcp_tool", text)


if __name__ == "__main__":
    unittest.main()
