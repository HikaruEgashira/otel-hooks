"""CLI for cc-tracing-hooks."""

import argparse
import sys

from . import settings as s


def cmd_enable(args: argparse.Namespace) -> int:
    print("Enabling Claude Code tracing hooks...")

    # Install symlink
    s.install_hook()
    print(f"  Symlink: {s.get_hook_symlink()} -> {s.get_hook_source()}")

    # Register hook in settings.json
    cfg = s.load_settings()
    cfg = s.register_hook(cfg)

    # Set env defaults
    if not s.get_env(cfg, "TRACE_TO_LANGFUSE"):
        cfg = s.set_env(cfg, "TRACE_TO_LANGFUSE", "true")
    elif s.get_env(cfg, "TRACE_TO_LANGFUSE") != "true":
        cfg = s.set_env(cfg, "TRACE_TO_LANGFUSE", "true")

    for key in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"]:
        if not s.get_env(cfg, key):
            value = input(f"  {key}: ").strip()
            if value:
                cfg = s.set_env(cfg, key, value)

    s.save_settings(cfg)
    print("Enabled.")
    return 0


def cmd_disable(_args: argparse.Namespace) -> int:
    print("Disabling Claude Code tracing hooks...")

    cfg = s.load_settings()
    cfg = s.unregister_hook(cfg)
    cfg = s.set_env(cfg, "TRACE_TO_LANGFUSE", "false")
    s.save_settings(cfg)

    s.uninstall_hook()
    print("Disabled.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    cfg = s.load_settings()
    enabled = s.is_enabled(cfg)

    print(f"Status: {'enabled' if enabled else 'disabled'}")
    print(f"Hook installed: {s.is_hook_installed()}")
    print(f"Hook registered: {s.is_hook_registered(cfg)}")
    print()
    print("Environment:")
    for key, value in s.get_env_status(cfg).items():
        masked = _mask(value) if "SECRET" in key and value else value
        print(f"  {key}: {masked or '(not set)'}")
    return 0


def cmd_update(_args: argparse.Namespace) -> int:
    if not s.is_hook_installed():
        print("Hook is not installed. Run 'cc-tracing-hooks enable' first.")
        return 1
    s.install_hook()
    print(f"Updated: {s.get_hook_symlink()} -> {s.get_hook_source()}")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    cfg = s.load_settings()
    issues: list[str] = []

    if not s.is_hook_installed():
        issues.append("Hook symlink missing")
    elif s.get_hook_symlink().is_symlink() and not s.get_hook_symlink().resolve().exists():
        issues.append("Hook symlink is broken (target does not exist)")

    if not s.is_hook_registered(cfg):
        issues.append("Hook not registered in settings.json")

    env = s.get_env_status(cfg)
    if env.get("TRACE_TO_LANGFUSE") != "true":
        issues.append("TRACE_TO_LANGFUSE is not 'true'")
    if not env.get("LANGFUSE_PUBLIC_KEY"):
        issues.append("LANGFUSE_PUBLIC_KEY not set")
    if not env.get("LANGFUSE_SECRET_KEY"):
        issues.append("LANGFUSE_SECRET_KEY not set")

    if not issues:
        print("No issues found.")
        return 0

    print(f"Found {len(issues)} issue(s):")
    for issue in issues:
        print(f"  - {issue}")

    answer = input("\nFix automatically? [y/N] ").strip().lower()
    if answer != "y":
        return 1

    s.install_hook()
    cfg = s.register_hook(cfg)
    if env.get("TRACE_TO_LANGFUSE") != "true":
        cfg = s.set_env(cfg, "TRACE_TO_LANGFUSE", "true")
    for key in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
        if not env.get(key):
            value = input(f"  {key}: ").strip()
            if value:
                cfg = s.set_env(cfg, key, value)
    s.save_settings(cfg)
    print("Fixed.")
    return 0


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cc-tracing-hooks",
        description="Claude Code tracing hooks for Langfuse observability",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("enable", help="Enable tracing hooks")
    sub.add_parser("disable", help="Disable tracing hooks")
    sub.add_parser("status", help="Show current status")
    sub.add_parser("update", help="Update hook to latest version")
    sub.add_parser("doctor", help="Check and fix configuration issues")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "enable": cmd_enable,
        "disable": cmd_disable,
        "status": cmd_status,
        "update": cmd_update,
        "doctor": cmd_doctor,
    }
    sys.exit(commands[args.command](args))
