"""Kiro CLI tool configuration (.kiro/agents/default.json).

Reference:
  - https://kiro.dev/docs/cli/hooks/
"""

from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool
from .json_io import load_json, save_json

AGENT_FILE = "default.json"
_HOOK_EVENTS = ("userPromptSubmit", "preToolUse", "postToolUse", "stop")



@register_tool
class KiroConfig:
    @property
    def name(self) -> str:
        return "kiro"

    def scopes(self) -> list[Scope]:
        return [Scope.GLOBAL, Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        if scope is Scope.GLOBAL:
            return Path.home() / ".kiro" / "agents" / AGENT_FILE
        return Path.cwd() / ".kiro" / "agents" / AGENT_FILE

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope))

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        hooks = settings.get("hooks", {})
        return all(
            any("otel-hooks hook" in hook.get("command", "") for hook in hooks.get(event_name, []))
            for event_name in _HOOK_EVENTS
        )

    def register_hook(self, settings: Dict[str, Any], command: str | None = None) -> Dict[str, Any]:
        base_cmd = command or "otel-hooks hook"
        cmd = f"{base_cmd} --tool kiro"
        hooks = settings.setdefault("hooks", {})
        for event_name in _HOOK_EVENTS:
            group = hooks.setdefault(event_name, [])
            if any("otel-hooks hook" in hook.get("command", "") for hook in group):
                continue
            group.append({"command": cmd})
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.get("hooks", {})
        for event_name in _HOOK_EVENTS:
            group = hooks.get(event_name, [])
            if not group:
                continue
            hooks[event_name] = [
                hook for hook in group if "otel-hooks hook" not in hook.get("command", "")
            ]
            if not hooks[event_name]:
                del hooks[event_name]
        return settings

