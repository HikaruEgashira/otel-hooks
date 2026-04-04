# GitHub Copilot Hooks Specification

> Source: https://docs.github.com/en/copilot/reference/hooks-configuration
> Snapshot: 2026-04-04

## Config Location

| Scope | Path |
|-------|------|
| Project | `.github/hooks/<name>.json` |

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
        "cwd": "string (optional)",
        "timeoutSec": 30,
        "comment": "string (optional)"
      }
    ]
  }
}
```

## Hook Events (6 total)

| Event | Has Output | Description |
|-------|-----------|-------------|
| sessionStart | No | New session begins or resumes |
| sessionEnd | No | Session completes or terminates |
| userPromptSubmitted | No | User submits a prompt |
| preToolUse | Yes | Before tool execution (can deny) |
| postToolUse | No | After tool execution |
| errorOccurred | No | Error during execution |

## Per-Event Input Schemas

### sessionStart

```json
{
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "source": "new|resume|startup",
  "initialPrompt": "string"
}
```

### sessionEnd

```json
{
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "reason": "complete|error|abort|timeout|user_exit"
}
```

### userPromptSubmitted

```json
{
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "prompt": "string"
}
```

### preToolUse

```json
{
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "string (JSON-stringified)"
}
```

### postToolUse

```json
{
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

### errorOccurred

```json
{
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "error": {
    "message": "string",
    "name": "string",
    "stack": "string (optional)"
  }
}
```

## preToolUse Output (only event with output)

```json
{
  "permissionDecision": "allow|deny|ask",
  "permissionDecisionReason": "string"
}
```

Note: only `deny` is processed.

## Constraints

- Default timeout: 30 seconds
- Multiple hooks of same type execute sequentially
- Scripts read JSON from stdin
- Exit code 0 for success
- No `session_id` or `transcript_path` in payload (metrics-only tool)
