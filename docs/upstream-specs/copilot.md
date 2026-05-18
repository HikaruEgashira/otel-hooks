# GitHub Copilot Hooks Specification

> Source: https://docs.github.com/en/copilot/reference/hooks-configuration
> Snapshot: 2026-05-18

## Config Location

| Scope | Path |
|-------|------|
| Project (repository) | `.github/hooks/<name>.json` |
| User (CLI) | `~/.copilot/hooks/` |

Cloud Agent: repository only (`.github/hooks/*.json`).
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
  "errorContext": "string",
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
  "cwd": "string"
}
```

### subagentStop

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "transcriptPath": "string",
  "stopReason": "string"
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

## Constraints

- Default timeout: 30 seconds
- Multiple hooks of same type execute sequentially
- Scripts read JSON from stdin
- `disableAllHooks: true` disables all hooks in a file
- No `transcript_path` in most payloads (metrics-only tool except agentStop/subagentStop)
