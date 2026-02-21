from __future__ import annotations

import tests._path_setup  # noqa: F401

import unittest

from otel_hooks.tools.copilot import CopilotConfig, HOOK_COMMAND as COPILOT_HOOK_COMMAND
from otel_hooks.tools.kiro import KiroConfig, HOOK_COMMAND as KIRO_HOOK_COMMAND


class MetricsHookRegistrationTest(unittest.TestCase):
    def test_copilot_registers_all_metric_events(self) -> None:
        cfg = CopilotConfig()
        settings: dict[str, object] = {"version": 1, "hooks": {}}

        updated = cfg.register_hook(settings)
        hooks = updated["hooks"]

        for event_name in ("userPromptSubmitted", "preToolUse", "postToolUse", "sessionEnd"):
            self.assertIn(event_name, hooks)
            self.assertTrue(
                any("otel-hooks hook" in item.get("bash", "") for item in hooks[event_name])
            )

        self.assertTrue(cfg.is_hook_registered(updated))

    def test_copilot_is_not_registered_when_only_session_end_exists(self) -> None:
        cfg = CopilotConfig()
        settings = {
            "version": 1,
            "hooks": {"sessionEnd": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}]},
        }
        self.assertFalse(cfg.is_hook_registered(settings))

    def test_copilot_unregister_removes_registered_command_from_all_events(self) -> None:
        cfg = CopilotConfig()
        settings = {
            "version": 1,
            "hooks": {
                "userPromptSubmitted": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "preToolUse": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "postToolUse": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
                "sessionEnd": [{"type": "command", "bash": COPILOT_HOOK_COMMAND}],
            },
        }

        updated = cfg.unregister_hook(settings)
        self.assertEqual(updated["hooks"], {})

    def test_kiro_registers_all_metric_events(self) -> None:
        cfg = KiroConfig()
        settings: dict[str, object] = {"hooks": {}}

        updated = cfg.register_hook(settings)
        hooks = updated["hooks"]

        for event_name in ("userPromptSubmit", "preToolUse", "postToolUse", "stop"):
            self.assertIn(event_name, hooks)
            self.assertTrue(
                any("otel-hooks hook" in item.get("command", "") for item in hooks[event_name])
            )

        self.assertTrue(cfg.is_hook_registered(updated))

    def test_kiro_is_not_registered_when_only_stop_exists(self) -> None:
        cfg = KiroConfig()
        settings = {"hooks": {"stop": [{"command": KIRO_HOOK_COMMAND}]}}
        self.assertFalse(cfg.is_hook_registered(settings))

    def test_kiro_unregister_removes_registered_command_from_all_events(self) -> None:
        cfg = KiroConfig()
        settings = {
            "hooks": {
                "userPromptSubmit": [{"command": KIRO_HOOK_COMMAND}],
                "preToolUse": [{"command": KIRO_HOOK_COMMAND}],
                "postToolUse": [{"command": KIRO_HOOK_COMMAND}],
                "stop": [{"command": KIRO_HOOK_COMMAND}],
            }
        }

        updated = cfg.unregister_hook(settings)
        self.assertEqual(updated["hooks"], {})


if __name__ == "__main__":
    unittest.main()
