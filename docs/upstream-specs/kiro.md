# Kiro Hooks Specification

> Source: https://kiro.dev/docs/hooks/ (formerly https://kiro.dev/docs/cli/hooks/)
> Snapshot: 2026-09-29

## Config Location

| Scope | Path |
|-------|------|
| Workspace | `.kiro/hooks/` (directory; each JSON file defines a hook set) |
| User | `~/.kiro/hooks/` (directory; each JSON file defines a hook set) — not documented upstream as of 2026-09-29 |

Upstream: "Each hook file is a standalone JSON file at `.kiro/hooks/<id>.json`" in the project root. Any `.json` filename works; multiple hooks per file are supported; hooks activate automatically when a session starts.

The `.kiro/hooks/*.json` format was introduced in IDE 1.0 and CLI 3.0. CLI 2.x hooks were embedded in agent config (camelCase keys such as `agentSpawn`, `preToolUse`, `fileEdited`); `kiro-cli agent migrate` auto-converts them.

otel-hooks writes to `otel-hooks.json` in the relevant directory.

## Config Schema

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "string (required)",
      "description": "string (optional)",
      "trigger": "string (required)",
      "matcher": "regex string (optional)",
      "action": {
        "type": "command|agent",
        "command": "string (command type)",
        "prompt": "string (agent type)"
      },
      "timeout": 60,
      "enabled": true,
      "confirm": {
        "question": "string",
        "confirmCommand": "string (optional)",
        "options": [
          { "id": "string", "label": "string", "run": true }
        ]
      }
    }
  ]
}
```

## Hook Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Identifier for telemetry/logging |
| `description` | string | No | — | Human-readable documentation |
| `trigger` | string | Yes | — | Event type, PascalCase (see below) |
| `matcher` | regex | No | always-match | Filter by tool name or file path |
| `action` | object | Yes | — | Execution instructions |
| `timeout` | integer (seconds) | No | 60 | Command timeout (0 = disabled) |
| `timeout_ms` | integer (ms) | No | 30000 | Hook execution timeout (alternative to `timeout`; added 2026-07-28) — not documented upstream as of 2026-09-29 |
| `cache_ttl_seconds` | integer | No | 0 | Cache successful hook results; 0 = no caching (added 2026-07-28) — not documented upstream as of 2026-09-29 |
| `enabled` | boolean | No | true | Toggle hook without deletion |
| `confirm` | object | No | — | Ask for confirmation before a `Stop` command hook runs (added 2026-09-22; schema revised 2026-09-29) |

### Confirm Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | Yes | Question to ask |
| `options` | array | Yes | Buttons; each `{ "id": string, "label": string, "run": boolean }` — `run` controls whether the hook's command executes when chosen |
| `confirmCommand` | string | No | Runs before the prompt; its stdout JSON controls the prompt |

`confirmCommand` stdout:
- `{ "skip": true }` — suppresses the prompt and skips the hook for this turn
- `{ "question": "...", "options": [...] }` — replaces the static question and options
- Non-zero exit, timeout, or invalid JSON — static `question`/`options` used as fallback

### Action Types

- `command` — `{ "type": "command", "command": "shell command" }`
- `agent` — `{ "type": "agent", "prompt": "agent prompt text" }` (timeout ignored)

## Hook Events (11 total + legacy `Manual`)

| Trigger | Activation | Matcher Type | Blockable | Platforms |
|---------|------------|--------------|-----------|-----------|
| `AgentSpawn` | Agent activates (added 2026-07-28) | N/A | No | CLI only |
| `SessionStart` | Session begins | N/A | No | IDE only |
| `UserPromptSubmit` | User submits prompt | Prompt text (regex) | Yes | IDE, CLI |
| `Stop` | Agent completes turn | N/A | No | IDE, CLI |
| `PreToolUse` | Before tool executes | Tool name (regex) | Yes | IDE, CLI |
| `PostToolUse` | After tool executes | Tool name (regex) | No | IDE, CLI |
| `PreTaskExec` | Before spec task starts | N/A | Yes | IDE only |
| `PostTaskExec` | After spec task finishes | N/A | No | IDE only |
| `PostFileCreate` | File created by agent | File path (regex) | No | IDE only |
| `PostFileSave` | File saved by agent | File path (regex) | No | IDE only |
| `PostFileDelete` | File deleted by agent | File path (regex) | No | IDE only |
| `Manual` | User-triggered on demand (legacy IDE 0.x manual hooks) | N/A | No | IDE (legacy only; new Manual-trigger hooks cannot be created) |

## Common Input Fields (all events)

```json
{
  "hook_event_name": "string",
  "cwd": "string",
  "session_id": "string"
}
```

`hook_event_name` values are camelCase, e.g. `"agentSpawn"`, `"preToolUse"`. Upstream example (Agent Spawn):

```json
{
  "hook_event_name": "agentSpawn",
  "cwd": "/current/working/directory",
  "session_id": "abc123-def456-789"
}
```

## Per-Event Additional Fields

### UserPromptSubmit

- `prompt`: string (user's input text) — not documented upstream as of 2026-09-29
- `USER_PROMPT` environment variable: the user prompt, for shell command actions

### Stop

- `assistant_response`: string (the assistant's last message text) — not documented upstream as of 2026-09-29

### File Events (PostFileCreate, PostFileSave, PostFileDelete)

- The hook receives the file path and session context via STDIN (exact field name not documented upstream)
- `{{filePath}}` template variable available in `command` for file-related triggers (new in CLI 3.0)

## Tool-Related Events (PreToolUse, PostToolUse)

Additional fields:

```json
{
  "tool_name": "string",
  "tool_input": "object",
  "tool_response": "object (PostToolUse only; not documented upstream as of 2026-09-29)"
}
```

For MCP tools, `tool_name` uses the full namespaced format including the MCP server name, e.g. `"@postgres/query"`.

## Tool Matcher Format

| Pattern | Description |
|---------|-------------|
| `read` | All built-in file read tools |
| `write` | All built-in file write tools |
| `shell` | All built-in shell command-related tools |
| `web` | All built-in web tools |
| `spec` | All built-in spec tools |
| `*` | All tools (built-in and MCP) |
| `@mcp` | All MCP tools |
| `@powers` | All Powers tools |
| `@builtin` | All built-in tools |
| `@postgres/query` | Specific MCP tool (namespaced) |
| (no matcher) | All tools |

Prefixes starting with `@` are matched by regex (e.g. `@mcp.*sql.*`). The aliases `fs_read`, `fs_write`, `execute_bash`, `use_aws`/`aws`, and `@git` are not documented upstream as of 2026-09-29.

## Exit Codes (command actions only)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout added to the agent's context |
| Any non-zero | stderr sent to the agent, which is notified the hook returned an error. For `PreToolUse` the tool invocation is blocked; for `UserPromptSubmit` the prompt submission is blocked |

Agent Spawn: `0` = STDOUT added to agent's context; other = STDERR warning shown to user.

Note: the previous exit-code-2-specific blocking semantics are not documented upstream as of 2026-09-29.

## Constraints

- `timeout` applies to command actions only (not agent actions)
- `timeout: 0` disables the limit
- Blocking supported for: PreToolUse, UserPromptSubmit, PreTaskExec (JSON `{"decision": "block", "reason": "..."}` output not documented upstream as of 2026-09-29)
- Agent actions: for `UserPromptSubmit`, the hook's prompt is appended to the user prompt and the combined prompt is sent to the agent
- `Stop` event is non-blocking (fire-and-forget; previously documented as blockable)
- `SessionStart` hooks are never cached (not documented upstream as of 2026-09-29)
- Matcher field filters by tool name (PreToolUse/PostToolUse), file path (PostFileCreate/PostFileSave/PostFileDelete), or prompt text (UserPromptSubmit) using regex; not evaluated for SessionStart, Stop, PreTaskExec, PostTaskExec, Manual
- File-triggered hooks respond only to agent-initiated changes, not manual edits
