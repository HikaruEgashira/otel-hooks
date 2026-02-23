"""Tests for otel_hooks.logging_setup."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from otel_hooks.logging_setup import configure, _PACKAGE


@pytest.fixture(autouse=True)
def _clean_logger():
    """Reset the package logger between tests."""
    pkg = logging.getLogger(_PACKAGE)
    pkg.handlers.clear()
    pkg.setLevel(logging.WARNING)
    yield
    pkg.handlers.clear()
    pkg.setLevel(logging.WARNING)


class TestConfigure:
    def test_attaches_file_and_stderr_handlers(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        configure(log_file, debug=True)
        pkg = logging.getLogger(_PACKAGE)
        assert len(pkg.handlers) == 2
        handler_types = {type(h).__name__ for h in pkg.handlers}
        assert "RotatingFileHandler" in handler_types
        assert "StreamHandler" in handler_types

    def test_idempotent_without_reconfigure(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        configure(log_file)
        configure(log_file)  # second call should be no-op
        pkg = logging.getLogger(_PACKAGE)
        assert len(pkg.handlers) == 2

    def test_reconfigure_replaces_handlers(self, tmp_path: Path):
        log_file1 = tmp_path / "first.log"
        log_file2 = tmp_path / "second.log"
        configure(log_file1)
        configure(log_file2, reconfigure=True)
        pkg = logging.getLogger(_PACKAGE)
        assert len(pkg.handlers) == 2

    def test_debug_false_sets_info_level(self, tmp_path: Path):
        configure(tmp_path / "test.log", debug=False)
        pkg = logging.getLogger(_PACKAGE)
        assert pkg.level == logging.INFO

    def test_debug_true_sets_debug_level(self, tmp_path: Path):
        configure(tmp_path / "test.log", debug=True)
        pkg = logging.getLogger(_PACKAGE)
        assert pkg.level == logging.DEBUG

    def test_file_handler_failure_prints_to_stderr(self, tmp_path: Path, capsys):
        bad_path = Path("/nonexistent/deeply/nested/dir/test.log")
        with patch("otel_hooks.logging_setup.Path.mkdir", side_effect=OSError("permission denied")):
            configure(bad_path)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "permission denied" in captured.err
        # stderr handler should still be attached
        pkg = logging.getLogger(_PACKAGE)
        assert len(pkg.handlers) == 1  # only stderr handler

    def test_writes_to_log_file(self, tmp_path: Path):
        log_file = tmp_path / "test.log"
        configure(log_file, debug=True)
        test_logger = logging.getLogger(f"{_PACKAGE}.test_module")
        test_logger.info("test message")
        # Force flush
        for h in logging.getLogger(_PACKAGE).handlers:
            h.flush()
        content = log_file.read_text()
        assert "test message" in content

    def test_propagate_is_false(self, tmp_path: Path):
        configure(tmp_path / "test.log")
        pkg = logging.getLogger(_PACKAGE)
        assert pkg.propagate is False
