# Kiro Hooks Specification

> Source: https://kiro.dev/docs/hooks/ + https://kiro.dev/docs/hooks/types/ (formerly https://kiro.dev/docs/cli/hooks/, now a redirect)
> Snapshot: 2026-10-20

## Config Location

| Scope | Path |
|-------|------|
| Workspace | `.kiro/hooks/` (directory; each JSON file defines a hook set) |
| User | `~/.kiro/hooks/` (CLI V3 only; directory; runs alongside workspace hooks in every workspace) |
| Agent profile | inline flat `hooks` array in a CLI V3 agent profile (profile-scoped; camelCase trigger aliases accepted) |

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
          { "id": "string", "label": "string", "run": "boolean (true = run the hook command)" }
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
| `confirm` | object | No | — | Confirmation prompt for `Stop` command hooks only: `question`, `options` (each `id`: string, `label`: string button text, `run`: boolean — whether the hook's command executes when chosen), optional `confirmCommand` (schema changed 2026-10-13; previously `message`/`default`) |

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
| `Manual` | On-demand hook (CLI V3 lists but cannot invoke; IDE 0.x legacy manual hooks only; cannot be newly created) | N/A | No | CLI V3 (listed only); IDE legacy only |

Web can store Hook configuration for later local use, but Web sessions do not run any triggers.

CLI 2.x → V3 trigger name mapping: `agentSpawn` → `SessionStart`, `userPromptSubmit` → `UserPromptSubmit`, `preToolUse` → `PreToolUse`, `postToolUse` → `PostToolUse`, `stop` → `Stop`.

## Common Input Fields (all events)

```json
{
  "hook_event_name": "string",
  "cwd": "string",
  "session_id": "string"
}
```

Note: upstream payload examples (as of 2026-10-20) use PascalCase `hook_event_name` values matching the trigger names (`UserPromptSubmit`, `Stop`, `PreToolUse`, `PostToolUse`); only the legacy alias example remains camelCase (`agentSpawn`). CLI 2.x sent camelCase names.

## Per-Event Additional Fields

### UserPromptSubmit

- `prompt`: string (user's input text)
- Prompt also exposed via `USER_PROMPT` env var for command actions

### Stop

- No fields beyond the common ones are documented (upstream example as of 2026-10-20 shows only `hook_event_name`, `cwd`, `session_id`; `assistant_response` is no longer shown)
- Continue decision on stdout: `{"decision": "block", "reason": "..."}`

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

`tool_name` is the V3 tool ID (e.g. `read_file`, `grep_search`, `execute_bash` on macOS/Linux, `execute_pwsh` on Windows). MCP tools display as `@server/tool` but hook events report lowercased, sanitized IDs `mcp_<server>_<tool>`.

## File-Related Events (PostFileCreate, PostFileSave, PostFileDelete)

- `{{filePath}}` template variable available in `command` for file-related triggers (CLI 3.0 / IDE 1.0 format)

## Tool Matcher Format

| Pattern | Description |
|---------|-------------|
| `read` | Tag: file read tools |
| `write` | Tag: file write tools |
| `shell` | Tag: shell execution (`execute_bash` and `execute_pwsh` match each other) |
| `web` | Tag: all built-in web tools |
| `subagent` | Tag: subagent tools |
| `spec` | Tag: all built-in spec tools |
| `context` | Tag: context tools |
| `mcp_git_*` | Wildcard against V3 tool IDs |
| `@mcp` | All MCP tools (`@`-prefixes matched by regex, e.g. `@mcp.*sql.*`) |
| `@powers` | All Powers tools |
| `@git` | All git MCP tools |
| `@git/status` | Specific MCP tool |
| `@postgres/query` | Specific MCP tool |
| `*` / `?` | Wildcards against tool IDs and tags |
| `@builtin` | Built-in tools only |
| (no matcher) | All tools |

A matcher without regex metacharacters (`\ ^ $ ( ) [ ] | +`) is a selector: it matches a tool whose ID or tags equal it, with `*`/`?` as wildcards. A matcher containing regex metacharacters is evaluated only as an unanchored regular expression against the tool ID. V3 does not expand CLI 2.x tool names (`fs_read`, `grep` are not V3 IDs or tags; use `read` or `read_file` / `grep_search`).

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
- `AgentSpawn` (V3 alias of `SessionStart`) hooks are never cached
- Matcher field filters by tool name (PreToolUse/PostToolUse) or file path (PostFileCreate/PostFileSave/PostFileDelete) using regex
- File-triggered hooks respond only to agent-initiated changes, not manual edits
