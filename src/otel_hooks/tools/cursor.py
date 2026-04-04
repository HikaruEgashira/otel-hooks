"""Cursor tool configuration (.cursor/hooks.json).

Reference:
  - https://cursor.com/ja/docs/hooks
"""

from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "otel-hooks hook --tool cursor"
_HOOK_EVENTS = ("sessionStart", "preToolUse", "postToolUse", "stop")


@register_tool
class CursorConfig:
    @property
    def name(self) -> str:
        return "cursor"

    def scopes(self) -> list[Scope]:
        return [Scope.GLOBAL, Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        if scope is Scope.GLOBAL:
            return Path.home() / ".cursor" / "hooks.json"
        return Path.cwd() / ".cursor" / "hooks.json"

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope), default={"version": 1, "hooks": {}})

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        hooks = settings.get("hooks", {})
        return all(
            any("otel-hooks hook" in h.get("command", "") for h in hooks.get(event, []))
            for event in _HOOK_EVENTS
        )

    def register_hook(self, settings: Dict[str, Any], command: str | None = None) -> Dict[str, Any]:
        cmd = command or HOOK_COMMAND
        settings.setdefault("version", 1)
        hooks = settings.setdefault("hooks", {})
        for event in _HOOK_EVENTS:
            group = hooks.setdefault(event, [])
            if any("otel-hooks hook" in h.get("command", "") for h in group):
                continue
            group.append({"command": cmd})
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.get("hooks", {})
        for event in _HOOK_EVENTS:
            group = hooks.get(event, [])
            if not group:
                continue
            hooks[event] = [
                h for h in group if "otel-hooks hook" not in h.get("command", "")
            ]
            if not hooks[event]:
                del hooks[event]
        return settings

