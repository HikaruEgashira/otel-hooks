# Kiro Hooks Specification

> Source: https://kiro.dev/docs/cli/hooks/
> Snapshot: 2026-04-04

## Config Location

| Scope | Path |
|-------|------|
| Global | `~/.kiro/agents/default.json` |
| Project | `.kiro/agents/default.json` |

## Hook Events (5 total)

| Event | Description |
|-------|-------------|
| agentSpawn | Agent is activated |
| userPromptSubmit | User submits a prompt |
| preToolUse | Before tool execution (can block) |
| postToolUse | After tool execution with results |
| stop | Assistant finishes responding |

## Common Input Fields (all events)

```json
{
  "hook_event_name": "string",
  "cwd": "string"
}
```

## Tool-Related Events (preToolUse, postToolUse)

Additional fields:

```json
{
  "tool_name": "string",
  "tool_input": "object",
  "tool_response": "object (postToolUse only)"
}
```

## Tool Matcher Format

| Pattern | Description |
|---------|-------------|
| `fs_read` / `read` | Canonical name or alias |
| `fs_write` / `write` | File write |
| `execute_bash` / `shell` | Shell execution |
| `use_aws` / `aws` | AWS operations |
| `@git` | All git MCP tools |
| `@git/status` | Specific MCP tool |
| `@postgres/query` | Specific MCP tool |
| `*` | All tools |
| `@builtin` | Built-in tools only |
| (no matcher) | All tools |

## Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `command` | string | — | Shell command to execute |
| `timeout_ms` | number | 30000 | Execution timeout |
| `cache_ttl_seconds` | number | 0 | Cache successful results (0 = no cache) |

Note: `agentSpawn` hooks are never cached.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — stdout captured (added to context for agentSpawn/userPromptSubmit) |
| 2 | Block execution (preToolUse only) — stderr returned to LLM |
| Other | Warning — stderr shown to user |
