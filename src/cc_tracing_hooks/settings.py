"""Read/write ~/.claude/settings.json for hook and env management."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
HOOKS_DIR = CLAUDE_DIR / "hooks"
HOOK_FILENAME = "langfuse_hook.py"
HOOK_COMMAND = f"uv run ~/.claude/hooks/{HOOK_FILENAME}"

ENV_KEYS = [
    "TRACE_TO_LANGFUSE",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
]


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


def save_settings(settings: Dict[str, Any]) -> None:
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(SETTINGS_FILE)


def get_hook_source() -> Path:
    return Path(__file__).parent / "hook.py"


def get_hook_symlink() -> Path:
    return HOOKS_DIR / HOOK_FILENAME


def is_hook_installed() -> bool:
    symlink = get_hook_symlink()
    return symlink.exists() or symlink.is_symlink()


def is_hook_registered(settings: Optional[Dict[str, Any]] = None) -> bool:
    if settings is None:
        settings = load_settings()
    stop_hooks = settings.get("hooks", {}).get("Stop", [])
    for group in stop_hooks:
        for hook in group.get("hooks", []):
            if hook.get("command", "").endswith(HOOK_FILENAME):
                return True
    return False


def is_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    if settings is None:
        settings = load_settings()
    env = settings.get("env", {})
    return (
        env.get("TRACE_TO_LANGFUSE", "").lower() == "true"
        and is_hook_installed()
        and is_hook_registered(settings)
    )


def install_hook() -> None:
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    symlink = get_hook_symlink()
    source = get_hook_source()
    if symlink.is_symlink() or symlink.exists():
        symlink.unlink()
    symlink.symlink_to(source)


def uninstall_hook() -> None:
    symlink = get_hook_symlink()
    if symlink.is_symlink() or symlink.exists():
        symlink.unlink()


def register_hook(settings: Dict[str, Any]) -> Dict[str, Any]:
    hooks = settings.setdefault("hooks", {})
    stop = hooks.setdefault("Stop", [])

    # Check if already registered
    for group in stop:
        for hook in group.get("hooks", []):
            if hook.get("command", "").endswith(HOOK_FILENAME):
                return settings

    stop.append({
        "hooks": [{"type": "command", "command": HOOK_COMMAND}]
    })
    return settings


def unregister_hook(settings: Dict[str, Any]) -> Dict[str, Any]:
    stop = settings.get("hooks", {}).get("Stop", [])
    settings["hooks"]["Stop"] = [
        group for group in stop
        if not any(
            hook.get("command", "").endswith(HOOK_FILENAME)
            for hook in group.get("hooks", [])
        )
    ]
    if not settings["hooks"]["Stop"]:
        del settings["hooks"]["Stop"]
    return settings


def set_env(settings: Dict[str, Any], key: str, value: str) -> Dict[str, Any]:
    settings.setdefault("env", {})[key] = value
    return settings


def get_env(settings: Dict[str, Any], key: str) -> Optional[str]:
    return settings.get("env", {}).get(key)


def get_env_status(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[str]]:
    if settings is None:
        settings = load_settings()
    env = settings.get("env", {})
    return {k: env.get(k) for k in ENV_KEYS}
