# Cline Hooks Specification

> Source: https://docs.cline.bot/customization/hooks
> Snapshot: 2026-04-27

## Config Location

| Scope | Path |
|-------|------|
| Global | `~/Documents/Cline/Hooks/` |
| Project | `.clinerules/hooks/` |

Both execute when present; global runs first.

## File Format

Hooks are **executable scripts** (not JSON config):

- macOS/Linux: extensionless executables (e.g., `PreToolUse`), `chmod +x` required
- Windows: PowerShell scripts (e.g., `PreToolUse.ps1`)

## Hook Events (8 total)

| Event | Description |
|-------|-------------|
| TaskStart | New task initialization |
| TaskResume | Resuming interrupted task |
| TaskCancel | User cancels running task |
| TaskComplete | Task finishes successfully |
| PreToolUse | Before tool execution |
| PostToolUse | After tool execution |
| UserPromptSubmit | User sends message |
| PreCompact | Before conversation history truncation |

## Common Input Payload (all events)

```json
{
  "taskId": "string",
  "hookName": "string",
  "clineVersion": "string",
  "timestamp": "string (milliseconds since epoch)",
  "workspaceRoots": ["string"],
  "userId": "string",
  "model": {
    "provider": "string",
    "slug": "string"
  }
}
```

## Per-Event Input Fields

### TaskStart / TaskResume / TaskCancel / TaskComplete

```json
{
  "taskStart": {
    "taskMetadata": {
      "taskId": "string",
      "ulid": "string",
      "initialTask": "string"
    }
  }
}
```

(Field key matches event name in camelCase; `taskMetadata` is nested inside)

### PreToolUse

```json
{
  "preToolUse": {
    "toolName": "string",
    "parameters": "object"
  }
}
```

### PostToolUse

```json
{
  "postToolUse": {
    "toolName": "string",
    "parameters": "object",
    "result": "string",
    "success": "boolean",
    "executionTimeMs": "number"
  }
}
```

### UserPromptSubmit

```json
{
  "userPromptSubmit": {
    "prompt": "string",
    "attachments": ["string"]
  }
}
```

### PreCompact

```json
{
  "preCompact": {
    "taskId": "string",
    "ulid": "string",
    "contextSize": "number",
    "compactionStrategy": "string",
    "tokensIn": "number",
    "tokensOut": "number",
    "tokensInCache": "number",
    "tokensOutCache": "number"
  }
}
```

## Output Payload (all events)

```json
{
  "cancel": false,
  "contextModification": "string (optional)",
  "errorMessage": "string (optional)"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `cancel` | boolean | Stops operation if true |
| `contextModification` | string | Text injected into conversation |
| `errorMessage` | string | User-facing error message |

## Communication

- Input: JSON via stdin
- Output: single-line JSON via stdout
- Debug: stderr

## Constraints

- If either global or project hook returns `cancel: true`, operation stops
- PostToolUse cannot undo already-executed tools
- Output must be valid single-line JSON
