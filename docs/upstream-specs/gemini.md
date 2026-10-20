# Gemini CLI Hooks Specification

> Source: https://geminicli.com/docs/hooks/ (payload/output schemas: https://geminicli.com/docs/hooks/reference/)
> Snapshot: 2026-10-20

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
        "sequential": false,
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
| SessionEnd | Session ends (exit, clear, logout, prompt_input_exit, other); best effort — CLI does not wait for completion and ignores flow-control fields |
| BeforeAgent | After user prompt, before planning |
| AfterAgent | Agent loop ends |
| BeforeModel | Before sending request to LLM |
| AfterModel | After receiving LLM response |
| BeforeToolSelection | Before LLM selects tools |
| BeforeTool | Before tool executes |
| AfterTool | After tool executes |
| PreCompress | Before context compression (fired asynchronously) |
| Notification | System notification occurs |

## Hook Configuration Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | string | Yes | — | Only `"command"` supported |
| `command` | string | Yes | — | Shell command to execute |
| `name` | string | No | — | Friendly identifier for logs |
| `timeout` | number | No | 60000 | Milliseconds |
| `description` | string | No | — | Purpose explanation |
| `matcher` | string | No | — | Group-level: regex filter (tools) or exact string (lifecycle) |
| `sequential` | boolean | No | — | Group-level: `true` = hooks in the group run one after another, `false` = parallel |

`matcher` and `sequential` belong to the group object, not to individual hooks.

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

## Base Input Payload (stdin)

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Unique ID for the current session |
| `transcript_path` | string | Absolute path to session transcript JSON |
| `cwd` | string | Current working directory |
| `hook_event_name` | string | The firing event (e.g. `"BeforeTool"`) |
| `timestamp` | string | ISO 8601 execution time |

## Event-Specific Input Fields

| Event | Input fields |
|-------|--------------|
| BeforeTool | `tool_name`, `tool_input`, `mcp_context`, `original_request_name` |
| AfterTool | `tool_name`, `tool_input`, `tool_response` (`llmContent`, `returnDisplay`, optional `error`), `mcp_context`, `original_request_name` |
| BeforeAgent | `prompt` |
| AfterAgent | `prompt`, `prompt_response`, `stop_hook_active` |
| BeforeModel | `llm_request` (model, messages, config) |
| BeforeToolSelection | `llm_request` |
| AfterModel | `llm_request`, `llm_response` |
| SessionStart | `source`: `startup\|resume\|clear` |
| SessionEnd | `reason`: `exit\|clear\|logout\|prompt_input_exit\|other` |
| Notification | `notification_type`: `ToolPermission`, `message`, `details` |
| PreCompress | `trigger`: `auto\|manual` |

## Common Output Fields

- `systemMessage`
- `suppressOutput`
- `continue`
- `stopReason`
- `decision`: `"allow"` or `"deny"` (alias `"block"`)
- `reason`

## CLI Management Commands

- `/hooks panel` — display all configured hooks
- `/hooks enable-all` / `/hooks disable-all` — toggle all hooks
- `/hooks enable <name>` / `/hooks disable <name>` — toggle individual hooks by name

## Security Notes

Project-level hooks undergo fingerprinting; changed hook commands trigger an untrusted warning before execution. "Hooks execute arbitrary code with your user privileges" when configured.
