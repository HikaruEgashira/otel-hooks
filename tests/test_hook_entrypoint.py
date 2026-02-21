from __future__ import annotations

import io
import os
import tests._path_setup  # noqa: F401
import unittest
from unittest.mock import patch

from otel_hooks.hook import read_hook_payload


class HookEntrypointTest(unittest.TestCase):
    def test_read_hook_payload_injects_source_tool_from_env(self) -> None:
        with patch("sys.stdin", io.StringIO("")), patch.dict(
            os.environ, {"OTEL_HOOKS_SOURCE_TOOL": "copilot"}, clear=False
        ):
            payload = read_hook_payload()

        self.assertEqual(payload["source_tool"], "copilot")

    def test_read_hook_payload_keeps_source_tool_from_stdin(self) -> None:
        with patch("sys.stdin", io.StringIO('{"source_tool":"kiro"}')), patch.dict(
            os.environ, {"OTEL_HOOKS_SOURCE_TOOL": "copilot"}, clear=False
        ):
            payload = read_hook_payload()

        self.assertEqual(payload["source_tool"], "kiro")


if __name__ == "__main__":
    unittest.main()
