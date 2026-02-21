from __future__ import annotations

import argparse
import json
import os
import tempfile
import tests._path_setup  # noqa: F401
import tomllib
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

from otel_hooks import cli
from otel_hooks.tools import Scope, get_tool


def _args(
    *,
    tool: str,
    provider: str = "datadog",
    project: bool = True,
    global_: bool = False,
    local: bool = False,
    yes: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        tool=tool,
        provider=provider,
        project=project,
        global_=global_,
        local=local,
        yes=yes,
    )


@contextmanager
def _pushd(path: Path) -> Iterator[None]:
    before = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(before)


class ToolsEndToEndTest(unittest.TestCase):
    def test_enable_disable_project_tools_round_trip(self) -> None:
        tools = ["claude", "cursor", "gemini", "cline", "copilot", "kiro", "opencode"]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project_cfg = {
                "provider": "datadog",
                "datadog": {
                    "service": "otel-hooks-e2e",
                    "env": "test",
                },
            }
            (root / ".otel-hooks.json").write_text(
                json.dumps(project_cfg, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            with _pushd(root), patch("otel_hooks.config.Path.home", return_value=root):
                for tool_name in tools:
                    rc_enable = cli.cmd_enable(
                        _args(tool=tool_name, provider="datadog", project=True)
                    )
                    self.assertEqual(rc_enable, 0, msg=f"enable failed: {tool_name}")

                    tool_cfg = get_tool(tool_name)
                    settings = tool_cfg.load_settings(Scope.PROJECT)
                    self.assertTrue(
                        tool_cfg.is_hook_registered(settings),
                        msg=f"hook not registered: {tool_name}",
                    )
                    self.assertTrue(
                        tool_cfg.settings_path(Scope.PROJECT).exists(),
                        msg=f"settings not written: {tool_name}",
                    )

                saved_project_cfg = json.loads(
                    (root / ".otel-hooks.json").read_text(encoding="utf-8")
                )
                self.assertEqual(saved_project_cfg["provider"], "datadog")
                self.assertEqual(saved_project_cfg["datadog"]["service"], "otel-hooks-e2e")
                self.assertEqual(saved_project_cfg["datadog"]["env"], "test")

                for tool_name in tools:
                    rc_disable = cli.cmd_disable(_args(tool=tool_name, project=True))
                    self.assertEqual(rc_disable, 0, msg=f"disable failed: {tool_name}")

                    tool_cfg = get_tool(tool_name)
                    settings = tool_cfg.load_settings(Scope.PROJECT)
                    self.assertFalse(
                        tool_cfg.is_hook_registered(settings),
                        msg=f"hook still registered: {tool_name}",
                    )

    def test_enable_disable_codex_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            global_cfg_path = root / ".config" / "otel-hooks" / "config.json"
            global_cfg_path.parent.mkdir(parents=True, exist_ok=True)
            global_cfg_path.write_text(
                json.dumps(
                    {
                        "provider": "otlp",
                        "otlp": {
                            "endpoint": "http://collector:4318/v1/traces",
                            "headers": "authorization=Bearer token,x-test=1",
                        },
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            codex_cfg_path = root / ".codex" / "config.toml"
            with _pushd(root), patch("otel_hooks.config.Path.home", return_value=root), patch(
                "otel_hooks.tools.codex.CONFIG_PATH",
                codex_cfg_path,
            ):
                rc_enable = cli.cmd_enable(
                    _args(tool="codex", provider="otlp", project=False, global_=True)
                )
                self.assertEqual(rc_enable, 0)
                self.assertTrue(codex_cfg_path.exists())

                codex_toml = tomllib.loads(codex_cfg_path.read_text(encoding="utf-8"))
                exporter = codex_toml["otel"]["exporter"]["otlp-http"]
                self.assertEqual(exporter["endpoint"], "http://collector:4318/v1/traces")
                self.assertEqual(exporter["protocol"], "json")
                self.assertEqual(
                    exporter["headers"],
                    {
                        "authorization": "Bearer token",
                        "x-test": "1",
                    },
                )

                rc_disable = cli.cmd_disable(
                    _args(tool="codex", provider="otlp", project=False, global_=True)
                )
                self.assertEqual(rc_disable, 0)

                codex_after_disable = tomllib.loads(codex_cfg_path.read_text(encoding="utf-8"))
                self.assertNotIn("otel", codex_after_disable)

    def test_enable_disable_all_round_trip(self) -> None:
        tools = ["claude", "cursor", "gemini", "cline", "copilot", "kiro", "opencode", "codex"]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            provider_cfg = {
                "provider": "otlp",
                "otlp": {
                    "endpoint": "http://collector:4318/v1/traces",
                    "headers": "authorization=Bearer token,x-test=1",
                },
            }
            (root / ".otel-hooks.json").write_text(
                json.dumps(provider_cfg, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            codex_cfg_path = root / ".codex" / "config.toml"
            with _pushd(root), patch("otel_hooks.config.Path.home", return_value=root), patch(
                "otel_hooks.tools.codex.CONFIG_PATH",
                codex_cfg_path,
            ):
                rc_enable = cli.cmd_enable(
                    _args(tool="all", provider="otlp", project=True, global_=False)
                )
                self.assertEqual(rc_enable, 0)

                for tool_name in tools:
                    tool_cfg = get_tool(tool_name)
                    scope = Scope.GLOBAL if tool_name == "codex" else Scope.PROJECT
                    settings = tool_cfg.load_settings(scope)
                    self.assertTrue(
                        tool_cfg.is_hook_registered(settings),
                        msg=f"hook not registered: {tool_name}",
                    )

                rc_disable = cli.cmd_disable(
                    _args(tool="all", provider="otlp", project=True, global_=False)
                )
                self.assertEqual(rc_disable, 0)

                for tool_name in tools:
                    tool_cfg = get_tool(tool_name)
                    scope = Scope.GLOBAL if tool_name == "codex" else Scope.PROJECT
                    settings = tool_cfg.load_settings(scope)
                    self.assertFalse(
                        tool_cfg.is_hook_registered(settings),
                        msg=f"hook still registered: {tool_name}",
                    )


if __name__ == "__main__":
    unittest.main()
