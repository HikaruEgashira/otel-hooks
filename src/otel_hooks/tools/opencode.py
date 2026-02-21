"""OpenCode tool configuration (opencode.json).

Reference:
  - https://opencode.ai/docs/config/
  - https://opencode.ai/docs/plugins/
"""

from pathlib import Path
from typing import Any, Dict

from . import Scope, register_tool
from .json_io import load_json, save_json

HOOK_COMMAND = "otel-hooks hook"


@register_tool
class OpenCodeConfig:
    @property
    def name(self) -> str:
        return "opencode"

    def scopes(self) -> list[Scope]:
        return [Scope.PROJECT]

    def settings_path(self, scope: Scope) -> Path:
        return Path.cwd() / "opencode.json"

    def load_settings(self, scope: Scope) -> Dict[str, Any]:
        return load_json(self.settings_path(scope))

    def save_settings(self, settings: Dict[str, Any], scope: Scope) -> None:
        save_json(self.settings_path(scope), settings)

    def is_hook_registered(self, settings: Dict[str, Any]) -> bool:
        hooks = settings.get("experimental", {}).get("hook", {}).get("session_completed", [])
        return any(HOOK_COMMAND in " ".join(h.get("command", [])) for h in hooks)

    def is_enabled(self, settings: Dict[str, Any]) -> bool:
        return self.is_hook_registered(settings)

    def register_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        experimental = settings.setdefault("experimental", {})
        hook = experimental.setdefault("hook", {})
        session_completed = hook.setdefault("session_completed", [])
        if any(HOOK_COMMAND in " ".join(h.get("command", [])) for h in session_completed):
            return settings
        session_completed.append({"command": ["otel-hooks", "hook"]})
        return settings

    def unregister_hook(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        hooks = settings.get("experimental", {}).get("hook", {}).get("session_completed", [])
        if not hooks:
            return settings
        settings["experimental"]["hook"]["session_completed"] = [
            h for h in hooks if HOOK_COMMAND not in " ".join(h.get("command", []))
        ]
        if not settings["experimental"]["hook"]["session_completed"]:
            del settings["experimental"]["hook"]["session_completed"]
        return settings
