# Kiro Hooks Specification

> Source: https://kiro.dev/docs/hooks/
> Snapshot: 2026-04-20

## Config Location

Hooks are configured via the **Kiro IDE panel** (UI-based, not JSON files).
Access: "Agent Hooks" section in the Kiro panel, or Command Palette → `Kiro: Open Kiro Hook UI`.

> Note: The `~/.kiro/agents/default.json` / `.kiro/agents/default.json` paths from earlier
> versions may still exist but the primary interface is now the UI form.

## Hook Events (8+ total)

### Agent Events (confirmed)

| Event | Description |
|-------|-------------|
| agentSpawn | Agent is activated |
| userPromptSubmit | User submits a prompt |
| preToolUse | Before tool execution (can block) |
| postToolUse | After tool execution with results |
| stop | Assistant finishes responding |

### New Event Categories (UI labels; exact event names TBD)

| Category | UI Label | Description |
|----------|----------|-------------|
| File | File Save / File Create / File Delete | File operations trigger |
| Task | Pre Task Execution / Post Task Execution | Before/after spec task runs |
| Manual | Manual Trigger | On-demand execution |

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

## Configuration Options (JSON / legacy)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `command` | string | — | Shell command to execute |
| `timeout_ms` | number | 30000 | Execution timeout |
| `cache_ttl_seconds` | number | 0 | Cache successful results (0 = no cache) |

Note: `agentSpawn` hooks are never cached.

## Configuration Options (UI form)

| Field | Description |
|-------|-------------|
| `title` | Short identifier for the hook |
| `description` | Explanation of hook functionality |
| `event` | Trigger (File Save, Pre Tool Use, Pre Task Execution, Manual, …) |
| `tool_name` | Tool filter (for Pre/Post Tool Use hooks) |
| `file_pattern` | Glob pattern (for file event hooks) |
| `action` | `Ask Kiro` (agent prompt) or `Run Command` (shell) |
| `instructions` | Prompt text (for Ask Kiro action) |
| `command` | Shell command (for Run Command action) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — stdout captured (added to context for agentSpawn/userPromptSubmit) |
| 2 | Block execution (preToolUse only) — stderr returned to LLM |
| Other | Warning — stderr shown to user |
