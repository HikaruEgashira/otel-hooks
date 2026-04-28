# Gemini CLI Hooks Specification

> Source: https://geminicli.com/docs/hooks/
> Snapshot: 2026-04-27

## Config Location

| Scope | Path |
|-------|------|
| System | `/etc/gemini-cli/settings.json` |
| Global | `~/.gemini/settings.json` |
| Project | `.gemini/settings.json` |

Precedence: Project > Global > System > Extensions

## Config Schema

```json
{
  "hooks": {
    "<EventName>": [
      {
        "matcher": "string",
        "hooks": [
          {
            "name": "string (optional)",
            "type": "command",
            "command": "string",
            "timeout": 60000,
            "description": "string (optional)"
          }
        ]
      }
    ]
  }
}
```

## Hook Events (11 total)

| Event | Description |
|-------|-------------|
| SessionStart | Session begins (startup, resume, clear) |
| SessionEnd | Session ends (exit, clear) |
| BeforeAgent | After user prompt, before planning |
| AfterAgent | Agent loop ends |
| BeforeModel | Before sending request to LLM |
| AfterModel | After receiving LLM response |
| BeforeToolSelection | Before LLM selects tools |
| BeforeTool | Before tool executes |
| AfterTool | After tool executes |
| PreCompress | Before context compression |
| Notification | System notification occurs |

## Hook Configuration Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | Yes | — | Only `"command"` supported |
| `command` | string | Yes | — | Shell command to execute |
| `name` | string | No | — | Friendly identifier for logs |
| `timeout` | number | No | 60000 | Milliseconds |
| `description` | string | No | — | Purpose explanation |
| `matcher` | string | No | — | Regex filter (tools) or exact string (lifecycle) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — JSON parsed from stdout |
| 2 | System block — stderr as rejection reason |
| Other | Warning — non-fatal |

## Environment Variables

- `GEMINI_PROJECT_DIR` — project root
- `GEMINI_PLANS_DIR` — plans directory path
- `GEMINI_SESSION_ID` — session identifier
- `GEMINI_CWD` — current working directory
- `CLAUDE_PROJECT_DIR` — alias for compatibility

## Communication Contract

- stdin/stdout with strict JSON protocol
- No plain text to stdout other than final JSON object
- Use stderr exclusively for debugging
