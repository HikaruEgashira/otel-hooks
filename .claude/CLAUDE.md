# otel-hooks

CLI/hook tool that records AI coding tool operations as OpenTelemetry traces.

## Key Interfaces

- **Provider Protocol** (`providers/__init__.py`): `emit_turn`, `flush`, `shutdown` — implemented by all providers (Langfuse/OTLP/Datadog)
- **ToolConfig Protocol** (`tools/__init__.py`): registered via `@register_tool`. Three patterns: JSON settings+Hook / JSON command array / script-based

## Data Flow

stdin JSON → `read_hook_payload()` → `detect_tool()` → `read_new_jsonl()` (incremental) → `build_turns()` → `Provider.emit_turn()` → flush/shutdown

## Tests

No test infrastructure (no test files, no pytest dependency, no CI test jobs)
