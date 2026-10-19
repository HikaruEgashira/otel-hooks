# Kiro Hooks Specification

> Source: https://kiro.dev/docs/hooks/ + https://kiro.dev/docs/hooks/types/ (formerly https://kiro.dev/docs/cli/hooks/, now a redirect)
> Snapshot: 2026-10-13

## Config Location

| Scope | Path |
|-------|------|
| Workspace | `.kiro/hooks/` (directory; each JSON file defines a hook set) |
| User | `~/.kiro/hooks/` (directory; each JSON file defines a hook set) |

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
        "question": "string (static prompt)",
        "options": [
          { "id": "string", "label": "string", "run": "string" }
        ],
        "confirmCommand": "string (optional)"
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
| `trigger` | string | Yes | — | Event type (see below) |
| `matcher` | regex | No | always-match | Filter by tool name or file path |
| `action` | object | Yes | — | Execution instructions |
| `timeout` | integer (seconds) | No | 60 | Command timeout (0 = disabled) |
| `timeout_ms` | integer (ms) | No | 30000 | Hook execution timeout (alternative to `timeout`; added 2026-07-28) |
| `cache_ttl_seconds` | integer | No | 0 | Cache successful hook results; 0 = no caching (added 2026-07-28) |
| `enabled` | boolean | No | true | Toggle hook without deletion |
| `confirm` | object | No | — | Confirmation prompt for `Stop` command hooks only: `question`, `options` (each `id`, `label`, `run`), optional `confirmCommand` (schema changed 2026-10-13; previously `message`/`default`) |

### Action Types

- `command` — `{ "type": "command", "command": "shell command" }`
- `agent` — `{ "type": "agent", "prompt": "agent prompt text" }` (timeout ignored)

### confirmCommand Output

`confirmCommand` stdout may be `{ "skip": true }` (suppress the prompt) or `{ "question": "...", "options": [...] }` (replace the static prompt). Non-zero exit, timeout, or invalid JSON falls back to the static `question`/`options`.

## Hook Events (13 total)

Authoritative list: https://kiro.dev/docs/hooks/types/

| Trigger | Activation | Matcher Type | Blockable | Platforms |
|---------|------------|--------------|-----------|-----------|
| `AgentSpawn` | Agent activates (added 2026-07-28) | N/A | No | CLI 2.x; alias of `SessionStart` in CLI V3 |
| `SessionStart` | Session begins | N/A | No | IDE, CLI V3 |
| `SessionEnd` | CLI V3 session torn down (added 2026-10-13) | N/A | No | CLI V3 only |
| `UserPromptSubmit` | User submits prompt | N/A | IDE: Yes; CLI: No | IDE, CLI |
| `Stop` | Agent completes turn | N/A | CLI V3: can force another turn | IDE, CLI |
| `PreToolUse` | Before tool executes | Tool name (regex) | Yes | IDE, CLI |
| `PostToolUse` | After tool executes | Tool name (regex) | No | IDE, CLI |
| `PreTaskExec` | Before spec task starts | N/A | Yes | IDE, CLI V3 |
| `PostTaskExec` | After spec task finishes | N/A | No | IDE, CLI V3 |
| `PostFileCreate` | File created by agent | File path (regex) | No | IDE, CLI V3 |
| `PostFileSave` | File saved by agent | File path (regex) | No | IDE, CLI V3 |
| `PostFileDelete` | File deleted by agent | File path (regex) | No | IDE, CLI V3 |
| `Manual` | On-demand hook (Web; CLI V3 lists but cannot invoke; not creatable in IDE v1) | N/A | No | Web, CLI V3 (recognized) |

CLI 2.x → V3 trigger name mapping: `agentSpawn` → `SessionStart`, `userPromptSubmit` → `UserPromptSubmit`, `preToolUse` → `PreToolUse`, `postToolUse` → `PostToolUse`, `stop` → `Stop`.

## Common Input Fields (all events)

```json
{
  "hook_event_name": "string",
  "cwd": "string",
  "session_id": "string"
}
```

Note: payload `hook_event_name` values in docs examples are camelCase (`userPromptSubmit`, `stop`, `agentSpawn`, `preToolUse`, `postToolUse`) even though config `trigger` values are PascalCase.

## Per-Event Additional Fields

### UserPromptSubmit

- `prompt`: string (user's input text)
- Prompt also exposed via `USER_PROMPT` env var for command actions

### Stop

- `assistant_response`: string (the assistant's last message text)

## Tool-Related Events (PreToolUse, PostToolUse)

Additional fields:

```json
{
  "tool_name": "string",
  "tool_input": "object",
  "tool_response": "object (PostToolUse only)",
  "tool_tags": "string[] (V2 engine only, e.g. [\"read\", \"@builtin\"]; not sent by Classic/V3 engines)"
}
```

`tool_response` shape: `{"success": bool, "result": [...]}`.

## File-Related Events (PostFileCreate, PostFileSave, PostFileDelete)

- `{{filePath}}` template variable available in `command` for file-related triggers (CLI 3.0 / IDE 1.0 format)

## Tool Matcher Format

| Pattern | Description |
|---------|-------------|
| `fs_read` / `read` | Canonical name or alias |
| `fs_write` / `write` | File write |
| `execute_bash` / `shell` | Shell execution |
| `use_aws` / `aws` | AWS operations |
| `web` | All built-in web tools |
| `spec` | All built-in spec tools |
| `@mcp` | All MCP tools (`@`-prefixes matched by regex, e.g. `@mcp.*sql.*`) |
| `@powers` | All Powers tools |
| `@git` | All git MCP tools |
| `@git/status` | Specific MCP tool |
| `@postgres/query` | Specific MCP tool |
| `*` | All tools |
| `@builtin` | Built-in tools only |
| (no matcher) | All tools |

## Exit Codes (command actions only)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout added to context for SessionStart/UserPromptSubmit |
| 2 | Block execution (PreToolUse, UserPromptSubmit, PreTaskExec only) — stderr returned to agent |
| Other | Warning displayed; execution continues |

## Constraints

- `timeout` applies to command actions only (not agent actions)
- `timeout: 0` disables the limit
- Blocking supported for: PreToolUse, UserPromptSubmit (IDE only), PreTaskExec (via exit code 2 or JSON `{"decision": "block", "reason": "..."}` output)
- CLI `UserPromptSubmit` cannot block: CLI V3 sends the prompt regardless of exit code; non-zero exit forwards hook output and exit code to the agent as context
- `Stop`: exit code 2 cannot reject the event; in CLI V3 a `Stop` command hook may exit 1 or return `{"decision":"block","reason":"..."}` to make Kiro continue for another turn
- `SessionStart` hooks are never cached
- Matcher field filters by tool name (PreToolUse/PostToolUse) or file path (PostFileCreate/PostFileSave/PostFileDelete) using regex
- File-triggered hooks respond only to agent-initiated changes, not manual edits
