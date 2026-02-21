from __future__ import annotations

import io
import json
import tempfile
import tests._path_setup  # noqa: F401
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from otel_hooks import hook


class _StubProvider:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, int]] = []
        self.flush_called = False
        self.shutdown_called = False

    def emit_turn(self, session_id: str, turn_num: int, turn, transcript_path: Path) -> None:
        self.emitted.append((session_id, turn_num))

    def flush(self) -> None:
        self.flush_called = True

    def shutdown(self) -> None:
        self.shutdown_called = True


class HookIntegrationTest(unittest.TestCase):
    def _patch_runtime_paths(self, root: Path) -> ExitStack:
        stack = ExitStack()
        state_dir = root / "state"
        stack.enter_context(patch("otel_hooks.runtime.state.STATE_DIR", state_dir))
        stack.enter_context(patch("otel_hooks.runtime.state.STATE_FILE", state_dir / "otel_hook_state.json"))
        stack.enter_context(patch("otel_hooks.runtime.state.LOCK_FILE", state_dir / "otel_hook_state.lock"))
        stack.enter_context(patch("otel_hooks.hook.STATE_DIR", state_dir))
        stack.enter_context(patch("otel_hooks.hook.LOG_FILE", state_dir / "otel_hook.log"))
        stack.enter_context(patch("otel_hooks.hook.LOCK_FILE", state_dir / "otel_hook_state.lock"))
        return stack

    def test_main_emits_once_and_skips_already_processed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "session.jsonl"
            transcript.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "message": {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "hello"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "id": "a1",
                                    "role": "assistant",
                                    "model": "gpt-5",
                                    "content": [{"type": "text", "text": "world"}],
                                },
                            }
                        ),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            payload = {"sessionId": "s-1", "transcriptPath": str(transcript)}
            stdin_data = io.StringIO(json.dumps(payload))

            provider1 = _StubProvider()
            provider2 = _StubProvider()

            with self._patch_runtime_paths(root), patch(
                "otel_hooks.config.load_config",
                return_value={"enabled": True, "provider": "langfuse", "debug": False},
            ), patch("otel_hooks.hook.create_provider", side_effect=[provider1, provider2]), patch(
                "sys.stdin", stdin_data
            ):
                rc1 = hook.main()

            self.assertEqual(rc1, 0)
            self.assertEqual(provider1.emitted, [("s-1", 1)])
            self.assertTrue(provider1.flush_called)
            self.assertTrue(provider1.shutdown_called)

            # 同一 payload を再実行しても state により再送しない
            with self._patch_runtime_paths(root), patch(
                "otel_hooks.config.load_config",
                return_value={"enabled": True, "provider": "langfuse", "debug": False},
            ), patch("otel_hooks.hook.create_provider", side_effect=[provider2]), patch(
                "sys.stdin", io.StringIO(json.dumps(payload))
            ):
                rc2 = hook.main()

            self.assertEqual(rc2, 0)
            self.assertEqual(provider2.emitted, [])
            self.assertFalse(provider2.flush_called)
            self.assertTrue(provider2.shutdown_called)

            state_file = root / "state" / "otel_hook_state.json"
            self.assertTrue(state_file.exists())
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(len(state), 1)
            saved = next(iter(state.values()))
            self.assertEqual(saved["turn_count"], 1)

    def test_main_returns_zero_when_provider_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            transcript = root / "session.jsonl"
            transcript.write_text("", encoding="utf-8")
            payload = {"sessionId": "s-1", "transcriptPath": str(transcript)}

            with self._patch_runtime_paths(root), patch(
                "otel_hooks.config.load_config",
                return_value={"enabled": True, "provider": "langfuse", "debug": False},
            ), patch("otel_hooks.hook.create_provider", return_value=None), patch(
                "sys.stdin", io.StringIO(json.dumps(payload))
            ):
                rc = hook.main()

            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
