from __future__ import annotations

import tests._path_setup  # noqa: F401

import tempfile
import unittest
from pathlib import Path

from otel_hooks.runtime.state import SessionState, read_new_jsonl_lines


class RuntimeStateTest(unittest.TestCase):
    def test_read_new_jsonl_lines_handles_incremental_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.jsonl"
            path.write_text('{"a":1}\n{"b":2', encoding="utf-8")

            ss = SessionState(offset=0, buffer="", turn_count=0)
            lines, ss = read_new_jsonl_lines(path, ss)
            self.assertEqual(lines, ['{"a":1}'])
            self.assertEqual(ss.buffer, '{"b":2')

            path.write_text('{"a":1}\n{"b":2}\n{"c":3}\n', encoding="utf-8")
            lines2, ss = read_new_jsonl_lines(path, ss)
            self.assertEqual(lines2, ['{"b":2}', '{"c":3}'])
            self.assertEqual(ss.buffer, "")

    def test_read_new_jsonl_lines_returns_empty_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.jsonl"
            ss = SessionState(offset=0, buffer="", turn_count=0)
            lines, ss2 = read_new_jsonl_lines(path, ss)
            self.assertEqual(lines, [])
            self.assertEqual(ss2.offset, 0)


if __name__ == "__main__":
    unittest.main()
