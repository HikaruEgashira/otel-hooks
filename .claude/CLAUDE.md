# otel-hooks

AI coding tool の操作をOpenTelemetryトレースとして記録するCLI/hookツール。

## 主要インターフェース

- **Provider Protocol** (`providers/__init__.py`): `emit_turn`, `flush`, `shutdown` — 全provider (Langfuse/OTLP/Datadog) が実装
- **ToolConfig Protocol** (`tools/__init__.py`): `@register_tool` デコレータで登録。実装パターンは3種: JSON設定+Hook / JSONコマンド配列 / スクリプトベース

## データフロー

stdin JSON → `read_hook_payload()` → `detect_tool()` → `read_new_jsonl()` (差分読み込み) → `build_turns()` → `Provider.emit_turn()` → flush/shutdown

## テスト

テストは未整備（テストファイル・pytest依存・CIテストジョブいずれも無い）
