# GitHub Copilot Hooks Specification

> Source: https://docs.github.com/en/copilot/reference/hooks-configuration
> Snapshot: 2026-06-09

## Config Location

Hooks can be defined in dedicated hook files or inline within settings files:

| Scope | Path |
|-------|------|
| Project (repository) — dedicated file | `.github/hooks/<name>.json` |
| Project (repository) — inline | `.github/copilot/settings.json` or `.github/copilot/settings.local.json` (under `hooks` key) |
| User (CLI) — dedicated file | `~/.copilot/hooks/` |
| User (CLI) — inline | `~/.copilot/settings.json` (under `hooks` key) |
| Plugin-contributed | `hooks.json` (provided by plugin) |

Cloud Agent: repository files only (`.github/hooks/*.json` and `.github/copilot/settings.json`).
Cloud agents run in a Linux sandbox; only `bash` and `command` fields honored; network restricted.

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
        "cwd": "string (optional)",
        "env": { "<key>": "<value>" },
        "timeoutSec": 30,
        "comment": "string (optional)"
      }
    ]
  },
  "disableAllHooks": true
}
```

### Hook Types

- `command` — shell script; `bash` (Linux/macOS), `powershell` (Windows), or cross-platform `command`
- `http` — POST JSON payload; fields: `url`, `headers`, `allowedEnvVars`, `timeoutSec`
- `prompt` — auto-submit text; fields: `prompt`

### Matcher Filtering

Optional regex patterns supported for: `notification`, `permissionRequest`, `preCompact`, `preToolUse`, `subagentStart`

## Hook Events (13 total)

| Event | Has Output | Description |
|-------|-----------|-------------|
| sessionStart | No | New or resumed session begins |
| sessionEnd | No | Session completes or terminates |
| userPromptSubmitted | No | User submits a prompt |
| preToolUse | Yes | Before tool execution (can deny) |
| postToolUse | No | After tool execution |
| postToolUseFailure | No | After a tool completes with a failure |
| errorOccurred | No | Error during execution |
| agentStop | Yes | Main agent finishes a turn (can block) |
| notification | No | Async system notification (CLI only) |
| permissionRequest | Yes | Before permission service runs (CLI only) |
| preCompact | No | Context compaction is about to begin |
| subagentStart | No | A subagent is spawned (before it runs) |
| subagentStop | Yes | A subagent completes (can block) |

## Per-Event Input Schemas

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

### preToolUse

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "string (JSON-stringified)"
}
```

### postToolUse

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "string (JSON-stringified)",
  "toolResult": {
    "resultType": "success|failure|denied",
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
  "toolArgs": "string (JSON-stringified)",
  "error": "string"
}
```

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
  "stopReason": "string"
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
  "agentName": "string",
  "agentDisplayName": "string (optional)",
  "stopReason": "string"
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

### agentStop / subagentStop

```json
{
  "decision": "block|allow",
  "reason": "string"
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

## Exit Codes (command hooks)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout parsed as JSON |
| 2 | Warning — stderr surfaced but execution continues |
| Other | Logged failure — execution continues |

## Supported Tool Names (for `preToolUse` matcher)

`ask_user`, `bash`, `create`, `edit`, `glob`, `grep`, `powershell`, `task`, `view`, `web_fetch`

## Constraints

- Default timeout: 30 seconds
- Multiple hooks of same type execute sequentially
- Scripts read JSON from stdin
- `disableAllHooks: true` disables all hooks in a file
- `transcriptPath` now included in `agentStop`, `subagentStart`, `subagentStop`, `preCompact`
- `preToolUse` is **fail-closed**: crashes, non-zero exits (other than 2), and timeouts all deny the tool call
