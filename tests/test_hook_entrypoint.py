from __future__ import annotations

import io
import tests._path_setup  # noqa: F401
import unittest
from unittest.mock import patch

from otel_hooks.hook import main, read_hook_payload


class HookEntrypointTest(unittest.TestCase):
    def test_tool_flag_injects_source_tool(self) -> None:
        with patch("sys.argv", ["hook", "--tool", "copilot"]), patch(
            "sys.stdin", io.StringIO("")
        ), patch("otel_hooks.hook.run_hook", return_value=0) as mock_run:
            main()

        payload = mock_run.call_args[0][0]
        self.assertEqual(payload["source_tool"], "copilot")

    def test_stdin_source_tool_not_overwritten_by_flag(self) -> None:
        with patch("sys.argv", ["hook", "--tool", "copilot"]), patch(
            "sys.stdin", io.StringIO('{"source_tool":"kiro"}')
        ), patch("otel_hooks.hook.run_hook", return_value=0) as mock_run:
            main()

        payload = mock_run.call_args[0][0]
        self.assertEqual(payload["source_tool"], "kiro")

    def test_read_hook_payload_no_env_var_fallback(self) -> None:
        """Env var OTEL_HOOKS_SOURCE_TOOL is no longer read."""
        import os

        with patch("sys.stdin", io.StringIO("")), patch.dict(
            os.environ, {"OTEL_HOOKS_SOURCE_TOOL": "copilot"}, clear=False
        ):
            payload = read_hook_payload()

        self.assertNotIn("source_tool", payload)


if __name__ == "__main__":
    unittest.main()
