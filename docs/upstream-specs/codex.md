# Codex CLI Hooks Specification

> Source: https://learn.chatgpt.com/docs/config-file/config-reference
> (Formerly https://developers.openai.com/codex/config-reference — 308 permanent redirect as of 2026-07-21)
> Snapshot: 2026-09-22

## Config Location

| Scope | Path |
|-------|------|
| Global | `~/.codex/config.toml` |
| Hooks (inline) | `~/.codex/config.toml` under `[hooks]` table |
| Hooks (external) | `.codex/hooks.json` |
| Admin-enforced | `requirements.toml` (managed hooks) |

Admin-enforced hook settings in `requirements.toml`:
- `hooks.managed_dir` (macOS/Linux): absolute path to managed hook scripts
- `hooks.windows_managed_dir` (Windows): absolute path to managed hook scripts

## Hooks Feature Status

**Gated behind feature flag; disabled by default.**

```toml
[features]
hooks = true  # Enable lifecycle hooks (replaces deprecated features.codex_hooks alias)
```

Note: The legacy alias `features.codex_hooks` is deprecated; use `features.hooks`.

## Hooks Config Schema

Hooks can be defined inline in `config.toml` or in `.codex/hooks.json` using the same schema:

```json
{
  "<EventName>": [
    {
      "matcher": "string",
      "hooks": [
        {
          "type": "command",
          "command": "string",
          "commandWindows": "string (Windows-specific override; TOML alias: command_windows)",
          "async": false
        }
      ]
    }
  ]
}
```

Note: Only `command` hook handlers are currently executed; `prompt` and `agent` types are parsed but skipped.

### `async` field

When `async: true`, the hook runs in the background without blocking the triggering operation. Default is `false`. `SessionEnd` always runs synchronously regardless of this setting.

### Output Management

The `additionalContextLimit` parameter (default: 2500 tokens) controls when oversized hook output is saved to disk with a shortened model preview. Setting to `0` passes full output directly to the model.

## Documented Hook Events (12)

| Event | Description |
|-------|-------------|
| `SessionStart` | Session begins |
| `SessionEnd` | Session terminates (added 2026-08-04) |
| `UserPromptSubmit` | User submits a prompt |
| `PreToolUse` | Before tool execution |
| `PermissionRequest` | Permission dialog appears |
| `PostToolUse` | After tool execution |
| `PreCompact` | Before history compaction |
| `PostCompact` | After history compaction |
| `SubagentStart` | Spawned agent startup |
| `SubagentStop` | Spawned agent shutdown |
| `Stop` | Assistant finishes responding |
| `Interrupt` | Session interrupted by user (added 2026-09-22) |

## otel-hooks Integration

otel-hooks uses Codex's native OTEL exporter configuration instead of hooks:

```toml
[otel]
# OTLP exporter settings configured directly in config.toml
exporter = { "otlp-http" = { endpoint = "https://...", protocol = "json" } }
```

Supports `otlp-http` and `otlp-grpc` exporters.

## TODO

- [ ] Monitor for full hooks.json payload schema documentation
- [ ] Track feature graduation from experimental
