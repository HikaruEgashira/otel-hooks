# GitHub Copilot Hooks Specification

> Source: https://docs.github.com/en/copilot/reference/hooks-configuration
> Snapshot: 2026-10-06

## Config Location

Hooks can be defined in dedicated hook files or inline within settings files:

| Scope | Path |
|-------|------|
| Policy (Linux/macOS) | `/etc/github-copilot/policy.d/*.json` |
| Policy (Windows) | `C:\ProgramData\GitHub\Copilot\policy.d\*.json` |
| Policy (Windows Registry) | `HKLM\Software\Policies\GitHub\Copilot` (REG_SZ values) |
| Project (repository) — dedicated file | `.github/hooks/<name>.json` |
| Project (repository) — inline | `.github/copilot/settings.json`, `.github/copilot/settings.local.json`, and cross-tool `.claude/settings.json` / `.claude/settings.local.json` (under `hooks` key) |
| User (CLI) — dedicated file | `~/.copilot/hooks/*.json` (Windows: `%USERPROFILE%\.copilot\hooks\`; `$COPILOT_HOME/hooks/` if `COPILOT_HOME` set) |
| User (CLI) — inline | `~/.copilot/settings.json` (under `hooks` key) |
| Plugin-contributed | `hooks.json` or `hooks/hooks.json` in plugin install dir |

Load order: Policy → User → Project → Plugins. Hooks from all sources combine.

Cloud Agent: only `.github/hooks/*.json` files loaded; policy, user-level, and plugin hooks unavailable.
Cloud agents run in a Linux sandbox; only `bash` field honored (not `powershell`; cross-platform `command` honored as fallback); network is restricted.

Policy hooks cannot be disabled by `disableAllHooks`. Policy files (POSIX) must be root-owned and not group/world-writable.

## Config Schema

```json
{
  "version": 1,
  "hooks": {
    "<hookEventName>": [
      {
        "type": "command",
        "bash": "string (script path)",
        "powershell": "string (script path)",
        "command": "string (cross-platform path)",
        "exec": "string (executable name; used with args for exec form)",
        "args": ["string", "..."],
        "cwd": "string (optional)",
        "env": { "<key>": "<value>" },
        "timeoutSec": 30,
        "timeout": "number (alias for timeoutSec; used only when timeoutSec absent)",
        "matcher": "regex string (optional)"
      }
    ]
  },
  "disableAllHooks": true
}
```

`exec`/`args` are CLI only and must not be combined with `bash`/`powershell`/`command`.

### Hook Types

- `command` — shell script; `bash` (Linux/macOS), `powershell` (Windows), or cross-platform `command`
- `http` — POST JSON payload; fields: `url`, `headers`, `allowedEnvVars`, `timeoutSec`
- `prompt` — auto-submit text; fields: `prompt` (only supported on `sessionStart`; fires only for new interactive sessions)

**Progress Messages** (command hooks): Hooks may emit transient status updates to stdout before the final JSON output:

```json
{"type": "progress", "message": "Checking policy..."}
{"type": "progress", "message": "Routing...", "temporary": true}
```

Lines with `"type": "progress"` are consumed and displayed as status; they are excluded from hook output parsing.

### Matcher Filtering

Optional regex patterns supported for: `notification`, `permissionRequest`, `postToolUse`, `preCompact`, `preToolUse`, `subagentStart`

## Hook Events (14 total)

| Event | Has Output | Description |
|-------|-----------|-------------|
| sessionStart | Yes | New or resumed session begins; can inject `additionalContext` |
| sessionEnd | No | Session completes or terminates |
| userPromptSubmitted | Yes | User submits a prompt; can return `modifiedPrompt` (SDK hooks only) |
| userPromptTransformed | Yes | After prompt transformation, before model receives it |
| preToolUse | Yes | Before tool execution (can deny) |
| postToolUse | Yes | After tool execution (can modify result) |
| postToolUseFailure | Yes | After a tool completes with a failure; can return `additionalContext` |
| errorOccurred | No | Error during execution |
| agentStop | Yes | Main agent finishes a turn (can block; 8-consecutive-block runaway guard) |
| notification | Yes | Async system notification (CLI only); can return `additionalContext` |
| permissionRequest | Yes | Before permission service runs (CLI only) |
| preCompact | No | Context compaction is about to begin |
| subagentStart | Yes | A subagent is spawned; can inject context (cannot block) |
| subagentStop | Yes | A subagent completes (can block) |

## Per-Event Input Schemas

### Payload Formats

Two payload formats, selected by the event name used in the config:

- **camelCase** (e.g. `sessionStart`) — camelCase fields, `timestamp` is Unix ms number (schemas below)
- **VS Code compatible** (PascalCase key, e.g. `SessionStart`) — snake_case fields, `hook_event_name` present, `timestamp` is ISO 8601 string

| camelCase key | PascalCase key | snake_case field renames |
|---|---|---|
| sessionStart | SessionStart | session_id, initial_prompt |
| sessionEnd | SessionEnd | session_id |
| userPromptSubmitted | UserPromptSubmit | session_id |
| preToolUse | PreToolUse | tool_name, tool_input (parsed from JSON string when possible) |
| postToolUse | PostToolUse | tool_name, tool_input, tool_result{result_type, text_result_for_llm} |
| postToolUseFailure | PostToolUseFailure | tool_name, tool_input, error |
| agentStop | Stop | transcript_path, stop_reason, stop_hook_active |
| subagentStop | SubagentStop | transcript_path, agent_id, agent_type, agent_name, agent_display_name, last_assistant_message (= response), stop_reason |
| errorOccurred | ErrorOccurred | error_context |
| preCompact | PreCompact | transcript_path, custom_instructions |
| permissionRequest | PermissionRequest | (same as PreToolUse) |

`userPromptTransformed`, `subagentStart`, `notification` have camelCase format only.
Output field names are identical in both formats.
PascalCase `PreToolUse`/`PermissionRequest` use Claude-format matchers (`*`/empty = all; `A|B` literal alternation matched against runtime or Claude name; else regex `^(?:P)$` vs Claude name), and report `tool_name` as the Claude tool name (e.g. `Bash`).

### sessionStart

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "source": "new|resume|startup",
  "initialPrompt": "string"
}
```

Output:
```json
{
  "additionalContext": "string (optional, injected into session)"
}
```

### sessionEnd

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "reason": "complete|error|abort|timeout|user_exit"
}
```

### userPromptSubmitted

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "prompt": "string"
}
```

Output (SDK programmatic hooks only; command/HTTP hooks output is dropped):
```json
{
  "modifiedPrompt": "string"
}
```

### userPromptTransformed

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "prompt": "string",
  "transformedPrompt": "string"
}
```

Output:
```json
{
  "modifiedTransformedPrompt": "string"
}
```

### preToolUse

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "unknown"
}
```

### postToolUse

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "unknown",
  "toolResult": {
    "resultType": "success",
    "textResultForLlm": "string"
  }
}
```

### postToolUseFailure

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "unknown",
  "error": "string"
}
```

Output: no JSON output consumed; for command hooks, exit code 2 is treated as `additionalContext` (stdout appended to the failure shown to the agent).

### errorOccurred

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "error": {
    "message": "string",
    "name": "string",
    "stack": "string (optional)"
  },
  "errorContext": "model_call|tool_execution|system|user_input",
  "recoverable": "boolean"
}
```

### agentStop

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "stopReason": "end_turn",
  "stop_hook_active": "boolean (true when a previous Stop hook blocked)"
}
```

### subagentStart

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "agentName": "string",
  "agentDisplayName": "string (optional)",
  "agentDescription": "string (optional)"
}
```

### subagentStop

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "agentId": "string",
  "agentType": "string",
  "agentName": "string",
  "agentDisplayName": "string (optional)",
  "response": "string (subagent's final response text)",
  "stopReason": "end_turn"
}
```

### preCompact

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "trigger": "manual|auto",
  "customInstructions": "string"
}
```

### notification

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "hook_event_name": "Notification",
  "message": "string",
  "title": "string (optional)",
  "notification_type": "shell_completed|shell_detached_completed|agent_completed|agent_idle|permission_prompt|elicitation_dialog"
}
```

Output:
```json
{
  "additionalContext": "string (optional, injected as user message)"
}
```

## Output (events with output)

### preToolUse

```json
{
  "permissionDecision": "allow|deny|ask",
  "permissionDecisionReason": "string",
  "modifiedArgs": "object (optional)"
}
```

Note: only `deny` is processed.

### postToolUse

```json
{
  "modifiedResult": {
    "resultType": "success",
    "textResultForLlm": "string"
  },
  "additionalContext": "string (optional)"
}
```

### subagentStart

```json
{
  "additionalContext": "string (optional, prepended to subagent prompt; cannot block)"
}
```

### agentStop

```json
{
  "decision": "block|allow",
  "reason": "string"
}
```

### subagentStop

```json
{
  "decision": "block|allow",
  "reason": "string",
  "modifiedResponse": "string (optional, replaces subagent response returned to parent)"
}
```

### permissionRequest

```json
{
  "behavior": "allow|deny",
  "message": "string",
  "interrupt": "boolean"
}
```

### notification

```json
{
  "additionalContext": "string (optional, injected as user message)"
}
```

## Exit Codes (command hooks)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout parsed as JSON |
| 2 | Warning by default (stderr surfaced, execution continues). `preToolUse`/`permissionRequest`: deny (stdout JSON merged with deny). `postToolUseFailure`: stdout treated as `additionalContext` |
| Other | Logged failure — execution continues |
| Timeout | Killed after `timeoutSec`; always fail-open (including `preToolUse` and policy hooks) |

## Supported Tool Names (for `preToolUse` matcher)

`ask_user`, `bash`, `create`, `edit`, `glob`, `grep`, `powershell`, `task`, `view`, `web_fetch`, `rg`, `str_replace_editor`, `apply_patch`, `web_search`, `update_todo`

### Claude Tool Name Mappings (PascalCase matchers)

| Runtime name | Claude name |
|---|---|
| `bash`, `powershell` | `Bash` |
| `view` | `Read` |
| `create` | `Write` |
| `edit`, `str_replace_editor`, `apply_patch` | `Edit` |
| `grep`, `rg` | `Grep` |
| `glob` | `Glob` |
| `web_fetch` | `WebFetch` |
| `web_search` | `WebSearch` |
| `ask_user` | `AskUserQuestion` |
| `update_todo` | `TodoWrite` |
| `task` | `Agent` (`Task` also accepted) |

## Cloud Agent Execution Environment

| Property | Value |
|----------|-------|
| OS | Linux; only `bash` field honored (`command` as fallback) |
| Working directory | `/workspace` (repo) or `/root` |
| Filesystem | Ephemeral; discarded when job ends |
| Network | Restricted; only GitHub/Copilot reachable |
| Environment | `GITHUB_COPILOT_API_TOKEN`, `GITHUB_COPILOT_GIT_TOKEN`, `COPILOT_AGENT_PROMPT`, `HOME=/root` set; `GITHUB_TOKEN` not set |
| Interactivity | Non-interactive; all tool permissions pre-granted |
| Config | Only `.github/hooks/*.json` loaded |

## Constraints

- Default timeout: 30 seconds (`timeoutSec`; the `timeout` field is a deprecated alias)
- Multiple hooks of same type execute sequentially
- Scripts read JSON from stdin
- `disableAllHooks: true` disables all hooks in a file
- `transcriptPath` now included in `agentStop`, `subagentStart`, `subagentStop`, `preCompact`
- `preToolUse` command hooks are **fail-closed** on crash / any non-zero exit (including 2); **timeouts are always fail-open**. HTTP `preToolUse` hooks are fail-open.
- **Runaway guard**: After 8 consecutive `block` decisions from `agentStop`, the CLI overrides and ends the turn
- Hook output bounded at **10 MiB** per invocation; `additionalContext` capped at **10 KB** when multiple hooks return it
- HTTP hooks require HTTPS by default for permission events; HTTP allowed for localhost only with `COPILOT_HOOK_ALLOW_LOCALHOST=1`
