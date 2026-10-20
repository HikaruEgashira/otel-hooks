# Codex CLI Hooks Specification

> Source: https://learn.chatgpt.com/docs/config-file/config-reference
> (Formerly https://developers.openai.com/codex/config-reference — 308 permanent redirect as of 2026-07-21)
> Hooks guide: https://learn.chatgpt.com/docs/hooks (formerly https://developers.openai.com/codex/hooks — 308 redirect)
> Snapshot: 2026-10-20

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

- Hooks are discovered next to active config layers. All sources load; higher-precedence layers do not replace lower-precedence hooks. If one layer has both `hooks.json` and inline `[hooks]`, Codex merges them and warns at startup.
- Non-managed hooks must be reviewed and trusted (hash-based) before running. Use `/hooks` in the CLI; `--dangerously-bypass-hook-trust` skips the check for one invocation.
- Plugin hook commands receive env vars `PLUGIN_ROOT`, `PLUGIN_DATA`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`.
- Multiple matching command hooks for the same event are launched concurrently.

Admin-enforced hook settings in `requirements.toml`:
- `hooks.managed_dir` (macOS/Linux): absolute path to managed hook scripts
- `hooks.windows_managed_dir` (Windows): absolute path to managed hook scripts
- `allow_managed_hooks_only` (boolean): when `true`, user/project/session/plugin hooks are skipped; only managed hooks run (added 2026-10-13)
- Cloud orchestration (Work Cloud with local access): where enabled, only admin-managed `mcp_tool` hooks from requirements.toml run on the cloud coordinator for supported lifecycle and tool events. Command/prompt/agent handlers, hooks from local configuration/plugins/local directories, environment-scoped hooks, and `SessionEnd` MCP hooks are unsupported there; a PreToolUse callback error, timeout, or malformed response can fail the hook without blocking the tool (added 2026-10-20)

## Hooks Feature Status

**Enabled by default (changed as of 2026-10-13 per Hooks guide).** Disable with:

```toml
[features]
hooks = false  # Disable lifecycle hooks (features.codex_hooks is a deprecated alias)
```

Note: The legacy alias `features.codex_hooks` is deprecated; use `features.hooks`.

Admins can force hooks off via `[features].hooks = false` in `requirements.toml`, or force them on (even if a user disabled them) by pinning `[features].hooks = true` alongside `[hooks]`.

## Hooks Config Schema

Hooks can be defined inline in `config.toml` (`[[hooks.<EventName>]]` / `[[hooks.<EventName>.hooks]]`) or in `.codex/hooks.json` (wrapped in a top-level `hooks` object; optional top-level `description` is metadata only and doesn't change which hooks run):

```json
{
  "description": "string (optional metadata)",
  "hooks": {
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
}
```

Note: `command` and `mcp_tool` handlers are executed (`mcp_tool` added 2026-10-13); `prompt` and `agent` types are parsed but skipped. MCP tool hooks run synchronously, do not trigger approvals or other hooks, and their errors do not block the operation.

`timeout` is in seconds; default 600 (`SessionEnd` and `Interrupt` default to 1, max 3). `matcher` is a regex; `"*"`, `""`, or omitted matches all.

`mcp_tool` `input` templates use `${field.nested}` expansion from the hook event JSON (a placeholder filling an entire value keeps its JSON type). MCP tool hooks use existing MCP connections (never start/reconnect servers) and are not supported for `SessionEnd`.

### `async` field

When `async: true`, the hook runs in the background without blocking the triggering operation. Default is `false`. `SessionEnd` always runs synchronously regardless of this setting.

- Up to 8 background hooks run concurrently per session; extra hooks wait.
- Background hooks cannot block, approve, rewrite, or otherwise control the triggering operation; their `additionalContext`/`systemMessage` is delivered at the next safe point.
- Unfinished background hooks are cancelled when the session ends.

### Output Management

The per-handler `additionalContextLimit` parameter (default: 2500 tokens) controls when oversized `additionalContext` is saved to disk (`<temp_dir>/hook_outputs/<session_id>/<uuid>.txt`) with a shortened model preview. Setting to `0` passes full output directly to the model.

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

Note: the `requirements.toml` `hooks.<Event>` reference row lists 11 events (omits `Interrupt`); the `config.toml` row and hooks guide list all 12.

## Common Input Fields (stdin JSON)

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | string | Subagent hooks use the parent session id |
| `transcript_path` | string \| null | Transcript format is not a stable interface |
| `cwd` | string | Session working directory |
| `hook_event_name` | string | Current hook event name |
| `model` | string | Codex extension; active model slug |
| `turn_id` | string | Codex extension; turn-scoped events only |
| `permission_mode` | string | `default`/`acceptEdits`/`plan`/`dontAsk`/`bypassPermissions`; on SessionStart, PreToolUse, PermissionRequest, PostToolUse, UserPromptSubmit, SubagentStart, SubagentStop, Stop, Interrupt |

## Event-specific Input Fields

| Event | Matcher filters | Extra fields |
|-------|-----------------|--------------|
| `SessionStart` | `source` | `source`: startup/resume/clear/compact/fork (fork added 2026-10-20; a resume with supplied history still reports `resume`) |
| `SessionEnd` | `reason` | `reason`: currently always `other` |
| `SubagentStart` | `agent_type` | `turn_id`, `agent_id`, `agent_type` |
| `SubagentStop` | `agent_type` | `turn_id`, `agent_id`, `agent_type`, `agent_transcript_path`, `stop_hook_active`, `last_assistant_message` |
| `PreToolUse` | `tool_name` (Bash [incl. unified exec `exec_command`], apply_patch/Edit/Write, mcp__*, other local function tools e.g. `update_plan`; `spawn_agent` also matches `Agent`) | `turn_id`, `tool_name`, `tool_use_id`, `tool_input` |
| `PermissionRequest` | `tool_name` | `turn_id`, `tool_name`, `tool_input` (`tool_input.description` optional) |
| `PostToolUse` | `tool_name` | `turn_id`, `tool_name`, `tool_use_id`, `tool_input`, `tool_response` |
| `PreCompact` / `PostCompact` | `trigger` | `turn_id`, `trigger`: manual/auto |
| `UserPromptSubmit` | (ignored) | `turn_id`, `prompt` |
| `Stop` | (ignored) | `turn_id`, `stop_hook_active`, `last_assistant_message` |
| `Interrupt` | (ignored) | `turn_id`, `permission_mode` (main thread only, not subagents) |

- `tool_input`: Bash/apply_patch use `tool_input.command`; MCP and other local function tools send their arguments.
- PostToolUse `tool_response`: MCP call result, or the model-facing output for other local function tools.
- Hosted tools (e.g. WebSearch) don't use the local function-tool hook path; PreToolUse/PostToolUse never fire for them. (Tool coverage expanded 2026-10-20)

## Output Fields

- Common (SessionStart, PreCompact, PostCompact, UserPromptSubmit, SubagentStop, Stop): `continue`, `stopReason`, `systemMessage`, `suppressOutput` (parsed, not implemented).
- `hookSpecificOutput.{hookEventName, additionalContext}`: SessionStart, SubagentStart, PreToolUse, PostToolUse, UserPromptSubmit.
- PreToolUse: `permissionDecision: "deny"` + `permissionDecisionReason`, or `"allow"` + `updatedInput`; legacy `{decision:"block", reason}`; exit code 2 + stderr. `systemMessage` supported; `permissionDecision: "ask"`, legacy `decision: "approve"`, `continue`, `stopReason`, `suppressOutput` are parsed but unsupported.
- PermissionRequest: `hookSpecificOutput.decision.behavior` = `allow`/`deny` (+ `message`); any deny wins. `systemMessage` supported; `continue`/`stopReason`/`suppressOutput` unsupported; `updatedInput`/`updatedPermissions`/`interrupt` are reserved and fail closed.
- PostToolUse: also `systemMessage`, `continue: false` (stops normal processing of the original tool result after the command ran), `stopReason`; `updatedMCPToolOutput`/`suppressOutput` are parsed but unsupported (added 2026-10-20).
- PostToolUse / UserPromptSubmit / Stop / SubagentStop: `{decision:"block", reason}` or exit code 2.
- Stop/SubagentStop require JSON on stdout; Interrupt accepts only optional `systemMessage`.

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
