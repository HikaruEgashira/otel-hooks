# Claude Code Hooks Specification

> Source: https://code.claude.com/docs/en/hooks
> Snapshot: 2026-04-06

## Config Location

| Scope | Path |
|-------|------|
| Global | `~/.claude/settings.json` |
| Project | `.claude/settings.json` |
| Local | `.claude/settings.local.json` |

## Config Schema

```json
{
  "hooks": {
    "<HookEventName>": [
      {
        "matcher": "regex_pattern_or_*",
        "hooks": [
          {
            "type": "command",
            "command": "string",
            "async": false,
            "shell": "bash",
            "timeout": 600,
            "statusMessage": "string",
            "once": false,
            "if": "permission_rule_syntax"
          }
        ]
      }
    ]
  },
  "disableAllHooks": false
}
```

### Hook Types

- `command` — shell command (`command`, `async`, `shell`)
- `http` — POST request (`url`, `headers`, `allowedEnvVars`)
- `prompt` — LLM prompt (`prompt`, `model`)
- `agent` — agent invocation (`prompt`, `model`)

## Hook Events (26 total)

| Event | Blockable | Matcher Target |
|-------|-----------|----------------|
| SessionStart | No | source: `startup\|resume\|clear\|compact` |
| InstructionsLoaded | No | load_reason: `session_start\|nested_traversal\|path_glob_match\|include\|compact` |
| UserPromptSubmit | Yes (exit 2) | — |
| PreToolUse | Yes (exit 2) | tool_name |
| PermissionRequest | Yes (exit 2) | tool_name |
| PermissionDenied | No | tool_name |
| PostToolUse | No | tool_name |
| PostToolUseFailure | No | tool_name |
| Notification | No | notification_type |
| SubagentStart | No | agent_type |
| SubagentStop | Yes (exit 2) | agent_type |
| TaskCreated | Yes (exit 2) | — |
| TaskCompleted | Yes (exit 2) | — |
| Stop | Yes (exit 2) | — |
| StopFailure | No | error_type |
| TeammateIdle | Yes (exit 2) | — |
| ConfigChange | Yes (exit 2) | config_source |
| CwdChanged | No | — |
| FileChanged | No | filename (basename) |
| WorktreeCreate | Yes (exit 2) | — |
| WorktreeRemove | No | — |
| PreCompact | No | compaction_trigger: `manual\|auto` |
| PostCompact | No | compaction_trigger: `manual\|auto` |
| Elicitation | Yes (exit 2) | mcp_server name |
| ElicitationResult | Yes (exit 2) | mcp_server name |
| SessionEnd | No | end_reason: `clear\|resume\|logout\|prompt_input_exit\|bypass_permissions_disabled\|other` |

## Common Input Fields (all events)

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "default|plan|acceptEdits|auto|dontAsk|bypassPermissions",
  "hook_event_name": "string",
  "agent_id": "string (subagent only)",
  "agent_type": "string (subagent/--agent only)"
}
```

## Per-Event Input Fields

### SessionStart

- `source`: `startup|resume|clear|compact`
- `model`: string
- `agent_type`: string (optional)

### InstructionsLoaded

- `file_path`: string
- `memory_type`: `User|Project|Local|Managed`
- `load_reason`: `session_start|nested_traversal|path_glob_match|include|compact`
- `globs`: string[] (path_glob_match only)
- `trigger_file_path`: string (lazy loads only)
- `parent_file_path`: string (include loads only)

### UserPromptSubmit

- `prompt`: string

### PreToolUse / PostToolUse / PostToolUseFailure / PermissionRequest / PermissionDenied

- `tool_name`: string
- `tool_input`: object (tool-specific)
- `tool_use_id`: string
- `tool_response`: object (PostToolUse only)
- `error`: string (PostToolUseFailure only)
- `is_interrupt`: boolean (PostToolUseFailure only)
- `reason`: string (PermissionDenied only)
- `permission_suggestions`: array (PermissionRequest only)

### Notification

- `message`: string
- `title`: string (optional)
- `notification_type`: `permission_prompt|idle_prompt|auth_success|elicitation_dialog`

### SubagentStart / SubagentStop

- `agent_id`: string
- `agent_type`: string
- `stop_hook_active`: boolean (SubagentStop)
- `agent_transcript_path`: string (SubagentStop)
- `last_assistant_message`: string (SubagentStop)

### TaskCreated / TaskCompleted

- `task_id`: string
- `task_subject`: string
- `task_description`: string (optional)
- `teammate_name`: string (optional)
- `team_name`: string (optional)

### FileChanged

- `file_path`: string
- `change_type`: `modified|created|deleted`

### ConfigChange

- `config_source`: `user_settings|project_settings|local_settings|policy_settings|skills`
- `changes`: object (optional)

### WorktreeCreate

- `worktree_path`: string
- `isolation_mode`: string (optional)

### WorktreeRemove

- `worktree_path`: string
- `reason`: `session_exit|subagent_finish` (optional)

### PreCompact / PostCompact

- `compaction_trigger`: `manual|auto`
- `summary`: string (optional)

### Elicitation / ElicitationResult

- `mcp_server`: string
- `tool_name`: string
- `form_fields`: array (Elicitation)
- `user_response`: object (ElicitationResult)

### StopFailure

- `error_type`: `rate_limit|authentication_failed|billing_error|invalid_request|server_error|max_output_tokens|unknown`
- `error_message`: string

### TeammateIdle

- `teammate_name`: string
- `team_name`: string (optional)

### Stop

- `stop_reason`: `end_turn|max_tokens|tool_use|stop_sequence`

### SessionEnd

- `end_reason`: `clear|resume|logout|prompt_input_exit|bypass_permissions_disabled|other`

## Common Output Fields

```json
{
  "continue": true,
  "stopReason": "string",
  "suppressOutput": false,
  "systemMessage": "string"
}
```

## Per-Event Output

### PreToolUse

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask|defer",
    "permissionDecisionReason": "string",
    "updatedInput": {},
    "additionalContext": "string"
  }
}
```

### UserPromptSubmit / PostToolUse / Stop / TaskCreated / TaskCompleted

- `decision`: `"block"` (optional)
- `reason`: string

### PermissionRequest

- `hookSpecificOutput.decision.behavior`: `allow|deny`
- `hookSpecificOutput.decision.updatedInput`: object
- `hookSpecificOutput.decision.updatedPermissions`: array
- `hookSpecificOutput.decision.message`: string (deny)
- `hookSpecificOutput.decision.interrupt`: boolean (deny)

### PermissionDenied

- `hookSpecificOutput.retry`: boolean

### Elicitation / ElicitationResult

- `hookSpecificOutput.action`: `accept|decline|cancel`
- `hookSpecificOutput.content`: object (accept only)

## Exit Codes (command hooks)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout parsed as JSON |
| 2 | Block/deny — stderr as rejection reason |
| Other | Non-blocking warning |

## Environment Variables

- `$CLAUDE_PROJECT_DIR` — project root
- `$CLAUDE_PLUGIN_ROOT` — plugin install dir
- `$CLAUDE_PLUGIN_DATA` — plugin data dir
- `$CLAUDE_CODE_REMOTE` — `"true"` in web environments
- `$CLAUDE_ENV_FILE` — env persist file (SessionStart, CwdChanged, FileChanged only)

## Constraints

- Hook output capped at 10,000 characters
- All matching hooks run in parallel
- Identical handlers deduplicated by command/URL
- JSON-only stdout on exit 0
