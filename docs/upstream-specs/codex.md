# Codex CLI Hooks Specification

> Source: https://learn.chatgpt.com/docs/config-file/config-reference
> (Formerly https://developers.openai.com/codex/config-reference — 308 permanent redirect as of 2026-07-21)
> Snapshot: 2026-10-13

## Config Location

| Scope | Path |
|-------|------|
| Global | `~/.codex/config.toml` |
| Project | `<repo>/.codex/config.toml` (loaded only when project is trusted; ignores `otel`) |
| Hooks (inline) | `~/.codex/config.toml` / `<repo>/.codex/config.toml` under `[hooks]` table |
| Hooks (external, user) | `~/.codex/hooks.json` |
| Hooks (external, project) | `<repo>/.codex/hooks.json` |
| Hooks (plugin) | `hooks/hooks.json` in plugin root, or `hooks` entry in `.codex-plugin/plugin.json` |
| Admin-enforced | `requirements.toml` (managed hooks) |

Admin-enforced hook settings in `requirements.toml`:
- `hooks.managed_dir` (macOS/Linux): absolute path to managed hook scripts
- `hooks.windows_managed_dir` (Windows): absolute path to managed hook scripts
- `allow_managed_hooks_only` (boolean): when `true`, user/project/session/plugin hooks are skipped; only managed hooks run (added 2026-10-13)

Non-managed hooks must be reviewed and trusted (via `/hooks`) before they run.

## Hooks Feature Status

**Enabled by default (changed as of 2026-10-13 per Hooks guide).** Disable with:

```toml
[features]
hooks = false  # Disable lifecycle hooks (features.codex_hooks is a deprecated alias)
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
          "async": false,
          "timeout": 600,
          "statusMessage": "string (optional)",
          "additionalContextLimit": 2500
        },
        {
          "type": "mcp_tool",
          "server": "string (required; already-connected MCP server)",
          "tool": "string (required)",
          "input": { "arg": "${field.nested}" },
          "timeout": 600,
          "statusMessage": "string (optional)"
        }
      ]
    }
  ]
}
```

Note: `command` and `mcp_tool` handlers are executed (`mcp_tool` added 2026-10-13); `prompt` and `agent` types are parsed but skipped. MCP tool hooks run synchronously, do not trigger approvals or other hooks, and their errors do not block the operation.

`timeout` is in seconds; default 600 (`SessionEnd` and `Interrupt` default to 1, max 3). `matcher` is a regex; `"*"`, `""`, or omitted matches all.

### `async` field

When `async: true`, the hook runs in the background without blocking the triggering operation. Default is `false`. `SessionEnd` always runs synchronously regardless of this setting. Max 8 background hooks run concurrently per session.

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

## Hook Input Payload

Common fields: `session_id`, `transcript_path` (nullable), `cwd`, `hook_event_name`, `model`, `permission_mode` (most events).

| Event | Additional fields |
|-------|-------------------|
| `SessionStart` | `source` |
| `SessionEnd` | `reason` |
| `SubagentStart` | `turn_id`, `agent_id`, `agent_type` |
| `PreToolUse` | `turn_id`, `tool_name`, `tool_use_id`, `tool_input` |
| `PermissionRequest` | `turn_id`, `tool_name`, `tool_input` |
| `PostToolUse` | `turn_id`, `tool_name`, `tool_use_id`, `tool_input`, `tool_response` |
| `PreCompact` / `PostCompact` | `turn_id`, `trigger` |
| `UserPromptSubmit` | `turn_id`, `prompt` |
| `SubagentStop` | `turn_id`, `agent_id`, `agent_type`, `agent_transcript_path`, `stop_hook_active`, `last_assistant_message` |
| `Stop` | `turn_id`, `stop_hook_active`, `last_assistant_message` |
| `Interrupt` | `turn_id` |

## otel-hooks Integration

otel-hooks uses Codex's native OTEL exporter configuration instead of hooks:

```toml
[otel]
# OTLP exporter settings configured directly in config.toml
exporter = { "otlp-http" = { endpoint = "https://...", protocol = "json" } }
```

Supports `otlp-http` and `otlp-grpc` exporters.

## TODO

- [x] Monitor for full hooks.json payload schema documentation (documented 2026-10-13)
- [ ] Track feature graduation from experimental
