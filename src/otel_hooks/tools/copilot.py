"""GitHub Copilot tool configuration (.github/hooks/otel-hooks.json).

Works with both GitHub Copilot CLI and VS Code Copilot agent.

Reference:
  - https://docs.github.com/en/copilot/reference/hooks-configuration
  - https://docs.github.com/en/copilot/how-tos/copilot-cli/use-hooks
  - https://code.visualstudio.com/docs/copilot/customization/hooks
"""

from pathlib import Path
from typing import Any, Dict

from . import HookEvent, Scope, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "otel-hooks hook"
HOOKS_FILE = "otel-hooks.json"


@register_tool
class CopilotConfig:
    @property
    def name(self) -> str:
        return "copilot"

    def scopes(self) -> list[Scope]:
        return [Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        return Path.cwd() / ".github" / "hooks" / HOOKS_FILE

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope), default={"version": 1, "hooks": {}})

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        session_end = settings.get("hooks", {}).get("sessionEnd", [])
        return any(HOOK_COMMAND in h.get("bash", "") for h in session_end)

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        return self.is_hook_registered(settings)

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        settings.setdefault("version", 1)
        hooks = settings.setdefault("hooks", {})
        session_end = hooks.setdefault("sessionEnd", [])
        if any(HOOK_COMMAND in h.get("bash", "") for h in session_end):
            return settings
        session_end.append({
            "type": "command",
            "bash": HOOK_COMMAND,
            "comment": "otel-hooks: emit tracing data",
        })
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        session_end = settings.get("hooks", {}).get("sessionEnd", [])
        if not session_end:
            return settings
        settings["hooks"]["sessionEnd"] = [
            h for h in session_end if HOOK_COMMAND not in h.get("bash", "")
        ]
        if not settings["hooks"]["sessionEnd"]:
            del settings["hooks"]["sessionEnd"]
        return settings

    def parse_event(self, payload: Dict[str, Any]) -> HookEvent | None:
        # Copilot uses camelCase toolName; no public session_id
        if "toolName" not in payload and "toolResult" not in payload:
            return None
        return None
