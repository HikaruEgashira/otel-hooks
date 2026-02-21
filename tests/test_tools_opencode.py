from __future__ import annotations

import tests._path_setup  # noqa: F401

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from otel_hooks.tools import Scope
from otel_hooks.tools.opencode import OpenCodeConfig


class OpenCodeConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = OpenCodeConfig()

    def test_settings_path_uses_opencode_plugins_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch("otel_hooks.tools.opencode.Path.cwd", return_value=root):
                path = self.cfg.settings_path(Scope.PROJECT)
            self.assertEqual(path, root / ".opencode" / "plugins" / "otel-hooks.js")

    def test_load_settings_ignores_legacy_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = root / "opencode" / "plugin" / "otel-hooks.js"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("legacy-script", encoding="utf-8")

            with patch("otel_hooks.tools.opencode.Path.cwd", return_value=root):
                settings = self.cfg.load_settings(Scope.PROJECT)

            self.assertEqual(settings, {})

    def test_save_settings_writes_new_path_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = root / "opencode" / "plugin" / "otel-hooks.js"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("legacy-script", encoding="utf-8")

            with patch("otel_hooks.tools.opencode.Path.cwd", return_value=root):
                self.cfg.save_settings({"_script": "new-script"}, Scope.PROJECT)

            new_path = root / ".opencode" / "plugins" / "otel-hooks.js"
            self.assertTrue(new_path.exists())
            self.assertEqual(new_path.read_text(encoding="utf-8"), "new-script")
            self.assertTrue(legacy.exists())
            self.assertEqual(legacy.read_text(encoding="utf-8"), "legacy-script")

    def test_save_settings_delete_removes_new_file_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            new_path = root / ".opencode" / "plugins" / "otel-hooks.js"
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_text("new-script", encoding="utf-8")

            legacy = root / "opencode" / "plugin" / "otel-hooks.js"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("legacy-script", encoding="utf-8")

            with patch("otel_hooks.tools.opencode.Path.cwd", return_value=root):
                self.cfg.save_settings({"_delete": True}, Scope.PROJECT)

            self.assertFalse(new_path.exists())
            self.assertTrue(legacy.exists())


if __name__ == "__main__":
    unittest.main()
