# Claude Code Hooks Specification

> Source: https://code.claude.com/docs/en/hooks
> Snapshot: 2026-10-13

## Config Location

| Scope | Path |
|-------|------|
| Global | `~/.claude/settings.json` |
| Project | `.claude/settings.json` |
| Local | `.claude/settings.local.json` |
| Managed | Managed policy settings (organization-wide, admin-controlled) |
| Plugin | `hooks/hooks.json` (when plugin enabled) |
| Skill frontmatter | Rest of the session once the skill is invoked |
| Subagent frontmatter | While that subagent is running |

Hook entries merge across settings levels. `allowManagedHooksOnly` (managed settings) blocks user, project, local, and plugin hooks; hooks from plugins force-enabled in managed `enabledPlugins` are exempt.

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
            "asyncRewake": false,
            "shell": "bash",
            "timeout": 600,
            "statusMessage": "string",
            "once": false,
            "if": "permission_rule_syntax",
            "onFailure": "continue|block"
          }
        ]
      }
    ]
  },
  "disableAllHooks": false,
  "allowManagedHooksOnly": false
}
```

- `if`: exactly one permission rule; only evaluated on tool events (`PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied`). On other events a hook with `if` set never runs.
- `once`: removes the hook after its first successful run. Only honored for hooks declared in skill frontmatter; ignored in settings files and agent frontmatter.

### Hook Types

- `command` — shell command (`command`, `args`, `async`, `asyncRewake`, `shell`: `bash|powershell`, `onFailure`: `continue|block` (v2.1.295+)); when `args` present uses exec form (no shell)
- `http` — POST request (`url`, `headers`, `allowedEnvVars`, `onFailure`)
- `mcp_tool` — MCP tool call (`server`, `tool`, `input` with `${path}` substitution)
- `prompt` — LLM prompt (`prompt`, `model`)
- `agent` — agent invocation (`prompt`, `model`) [experimental]

## Hook Events (33 total)

| Event | Blockable | Matcher Target |
|-------|-----------|----------------|
| SessionStart | No | source: `startup\|resume\|clear\|compact\|fork` |
| Setup | No | trigger: `init\|maintenance` |
| InstructionsLoaded | No | load_reason: `session_start\|nested_traversal\|path_glob_match\|include\|compact` |
| UserPromptSubmit | Yes (exit 2) | — |
| UserPromptExpansion | Yes (exit 2) | command_name |
| PreToolUse | Yes (exit 2) | tool_name |
| PermissionRequest | Yes (exit 2) | tool_name |
| PermissionDenied | No | tool_name |
| PostToolUse | Yes (exit 2) | tool_name |
| PostToolUseFailure | Yes (exit 2) | tool_name |
| PostToolBatch | Yes (exit 2) | — |
| Notification | No | notification_type: `permission_prompt\|idle_prompt\|auth_success\|elicitation_dialog\|elicitation_url_dialog\|elicitation_complete\|elicitation_response\|agent_needs_input\|agent_completed\|quota_auto_resume_fired\|quota_auto_resume_stale\|quota_auto_resume_disabled` |
| MessageDisplay | No | — |
| SubagentStart | No | agent_type |
| SubagentStop | Yes (exit 2) | agent_type |
| TaskCreated | Yes (exit 2) | — |
| TaskCompleted | Yes (exit 2) | — |
| Stop | Yes (exit 2) | — |
| StopFailure | No | error: `rate_limit\|overloaded\|authentication_failed\|account_on_hold\|...` |
| TeammateIdle | Yes (exit 2) | — |
| ConfigChange | Yes (exit 2; not for `policy_settings`) | source: `user_settings\|project_settings\|local_settings\|policy_settings\|skills` |
| CwdChanged | No | — |
| DirectoryAdded | No | addition method: `slash_command\|register_repo_root` |
| FileChanged | No | filename (basename) |
| WorktreeCreate | Yes (exit 2) | — |
| WorktreeRemove | Yes (exit 2) | — |
| PreCompact | Yes (exit 2) | trigger: `manual\|auto` |
| PostCompact | No | trigger: `manual\|auto` |
| PreModelSwitch | Yes (exit 2) | model name (regex) |
| PostModelSwitch | No | model name (regex) |
| Elicitation | Yes (exit 2) | mcp_server name |
| ElicitationResult | Yes (exit 2) | mcp_server name |
| SessionEnd | No | reason: `clear\|resume\|logout\|prompt_input_exit\|other` (`bypass_permissions_disabled` removed v2.1.234) |

## Common Input Fields (all events)

```json
{
  "session_id": "string",
  "prompt_id": "uuid",
  "transcript_path": "string",
  "cwd": "string",
  "scratchpad_dir": "string (v2.1.257+)",
  "permission_mode": "default|plan|acceptEdits|auto|dontAsk|bypassPermissions",
  "hook_event_name": "string",
  "effort": {
    "level": "low|medium|high|xhigh|max"
  },
  "agent_id": "string (subagent only)",
  "agent_type": "string (subagent/--agent only)"
}
```

## Per-Event Input Fields

### SessionStart

- `source`: `startup|resume|clear|compact|fork`
- `model`: string (optional; may be omitted, e.g. after `/clear`)
- `agent_type`: string (optional; with `claude --agent <name>`)
- `session_title`: string (optional)
- `seconds_since_last_response`: number (resume/fork with prior response only, v2.1.251+)
- `context_tokens`: number (resume/fork with prior response only, v2.1.251+)
- `prompt_cache_likely_expired`: boolean (resume/fork with prior response only, v2.1.251+)
- `estimated_cache_write_usd`: number (resume/fork with prior response only, v2.1.251+)

### Setup

- `trigger`: `init|maintenance`

### InstructionsLoaded

- `file_path`: string
- `memory_type`: `User|Project|Local|Managed`
- `load_reason`: `session_start|nested_traversal|path_glob_match|include|compact`
- `globs`: string[] (path_glob_match only)
- `trigger_file_path`: string (lazy loads only)
- `parent_file_path`: string (include loads only)

### UserPromptSubmit

- `prompt`: string
- `session_title`: string (optional)

### UserPromptExpansion

- `expansion_type`: `slash_command|mcp_prompt`
- `command_name`: string
- `command_args`: string
- `command_source`: string (e.g. `plugin`)
- `prompt`: string (original unexpanded prompt)

### PreToolUse

- `tool_name`: string
- `tool_input`: object (tool-specific; file tool `file_path` always absolute)
- `tool_use_id`: string
- `mcp_server`: `{ name, source }` (MCP tools only; v2.1.274+)

### PermissionRequest

- `tool_name`: string
- `tool_input`: object (tool-specific)
- `permission_suggestions`: array of permission update entries (optional)
- `mcp_server`: `{ name, source }` (MCP tools only)
- (no `tool_use_id`)

### PermissionDenied

- `tool_name`: string
- `tool_input`: object (tool-specific)
- `tool_use_id`: string
- `reason`: string (denial reason, e.g. `[Data Exfiltration]`)
- `mcp_server`: `{ name, source }` (MCP tools only)

### PostToolUse

- `tool_name`: string
- `tool_input`: object (tool-specific)
- `tool_response`: object (tool's structured output)
- `tool_use_id`: string
- `duration_ms`: number (optional)
- `mcp_server`: `{ name, source }` (MCP tools only)

### PostToolUseFailure

- `tool_name`: string
- `tool_input`: object (tool-specific)
- `tool_use_id`: string
- `error`: string
- `is_interrupt`: boolean (optional)
- `duration_ms`: number (optional)
- `mcp_server`: `{ name, source }` (MCP tools only)

### PostToolBatch

- `tool_calls`: array of `{ tool_name, tool_input, tool_use_id, tool_response }` (`tool_response` is serialized tool_result content)

### Notification

- `message`: string
- `title`: string (optional)
- `notification_type`: `permission_prompt|idle_prompt|auth_success|elicitation_dialog|elicitation_url_dialog|elicitation_complete|elicitation_response|agent_needs_input|agent_completed|quota_auto_resume_fired|quota_auto_resume_stale|quota_auto_resume_disabled` (`quota_auto_resume_*` v2.1.234+)

### SubagentStart

- `agent_id`: string
- `agent_type`: string

### SubagentStop

- `stop_hook_active`: boolean
- `agent_id`: string
- `agent_type`: string (empty string for internal agents when the session has no agent)
- `agent_transcript_path`: string
- `last_assistant_message`: string (with `SubagentHandback` tool (v2.1.271+) the report is in that tool call's `tool_input.message`, not here)
- `background_tasks`, `session_crons`: arrays (same shape as Stop)

### TaskCreated / TaskCompleted

- `task_id`: string
- `task_subject`: string
- `task_description`: string (optional)
- `teammate_name`: string (optional)
- `team_name`: string (deprecated)
- `agent_id`: string (optional, v2.1.290+)

### CwdChanged

- `old_cwd`: string
- `new_cwd`: string

### DirectoryAdded

- `directory`: string (absolute path of newly added directory)
- `source`: `slash_command|register_repo_root`

### FileChanged

- `file_path`: string (absolute path)
- `event`: `change|add|unlink` (modified|created|deleted)

### ConfigChange

- `source`: `user_settings|project_settings|local_settings|policy_settings|skills`
- `file_path`: string (optional)

### WorktreeCreate

- `name`: string (worktree slug, e.g. `bold-oak-a3f2`)

### WorktreeRemove

- `worktree_path`: string (absolute path)

### PreCompact

- `trigger`: `manual|auto`
- `custom_instructions`: string|null (manual `/compact` args; null for auto)

### PostCompact

- `trigger`: `manual|auto`
- `compact_summary`: string

### PreModelSwitch (v2.1.251+)

- `from_model`: string (model ID switching from)
- `to_model`: string (model ID switching to; matcher compares its canonical name)
- `requested_model`: string|null (alias or model ID; null for default)
- `source`: `command|picker|sdk`
- `context_tokens`: number
- `prompt_cache_warm`: boolean
- `cache_ttl`: `5m|1h`
- `estimated_cache_write_usd`: number
- `pricing`: `configured|catalog|default`

### PostModelSwitch (v2.1.251+)

- Same fields as PreModelSwitch; `source` additionally `auto|resume` (`requested_model` null when `auto`)

### Elicitation

- `mcp_server_name`: string
- `message`: string
- `mode`: string (optional)
- `url`: string (optional)
- `elicitation_id`: string (optional)
- `requested_schema`: object (optional, JSON Schema)

### ElicitationResult

- `mcp_server_name`: string
- `action`: `accept|decline|cancel`
- `mode`: string (optional)
- `elicitation_id`: string (optional)
- `content`: object (optional)

### StopFailure

- `error`: `rate_limit|overloaded|authentication_failed|oauth_org_not_allowed|account_on_hold|billing_error|invalid_request|model_not_found|server_error|max_output_tokens|cloud_credential_error|unknown` (`cloud_credential_error` added v2.1.267+)
- `error_details`: string (optional)
- `last_assistant_message`: string (optional)

### TeammateIdle

- `teammate_name`: string
- `team_name`: string (deprecated)
- `agent_id`: string (optional, v2.1.290+)

### MessageDisplay

- `turn_id`: string
- `message_id`: string
- `index`: number
- `final`: boolean
- `delta`: string (content being displayed to user)

### Stop

- `stop_hook_active`: boolean
- `last_assistant_message`: string (Claude's full response text; formerly `response`, before that `assistant_message`)
- `background_tasks`: array of `{ id, type, status, description, command?, agent_type?, server?, tool?, name? }`
- `session_crons`: array of `{ id, schedule, recurring, prompt }`

### SessionEnd

- `reason`: `clear|resume|logout|prompt_input_exit|other` (`bypass_permissions_disabled` removed v2.1.234)

## Common Output Fields

```json
{
  "continue": true,
  "stopReason": "string",
  "suppressOutput": false,
  "systemMessage": "string",
  "terminalSequence": "string (OSC/BEL escape sequences only)"
}
```

## Per-Event Output

### SessionStart

- `additionalContext`: string (injected before first prompt)
- `initialUserMessage`: string (optional, overrides initial user message)
- `sessionTitle`: string (optional, sets session title)
- `watchPaths`: string[] (optional, paths to monitor for FileChanged events)
- `reloadSkills`: boolean (optional)

### CwdChanged / FileChanged

- `watchPaths`: string[] (replaces dynamic watch list)

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

### UserPromptSubmit / UserPromptExpansion

- `decision`: `"block"` (optional)
- `reason`: string
- `additionalContext`: string (optional)
- `sessionTitle`: string (UserPromptSubmit only, optional)
- `suppressOriginalPrompt`: boolean (UserPromptSubmit only, optional)

### PostToolUse

- `decision`: `"block"` (optional)
- `reason`: string
- `hookSpecificOutput.updatedToolOutput`: value matching tool output shape (optional, replaces tool output seen by Claude)
- `hookSpecificOutput.updatedMCPToolOutput`: MCP tools only (optional)
- `hookSpecificOutput.additionalContext`: string (optional, appended context for Claude)
- `hookSpecificOutput.classifierContext`: string (optional, v2.1.236+)

### PostToolUseFailure

- `hookSpecificOutput.additionalContext`: string (optional)

### PreModelSwitch

- `hookSpecificOutput.permissionDecision`: `allow|deny|ask` (no `defer`)
- `hookSpecificOutput.permissionDecisionReason`: string
- `decision`: `"block"` (optional)

### PostModelSwitch

- `hookSpecificOutput.additionalContext`: string

### PostToolBatch

- `decision`: `"block"` (optional; `continue: false` also stops the loop)
- `reason`: string
- `hookSpecificOutput.additionalContext`: string (optional, injected before next model call)

### TaskCreated / TaskCompleted / PreCompact / ConfigChange

- `decision`: `"block"` (optional; TaskCompleted uses exit 2 or `continue: false`)
- `reason`: string

### Stop / SubagentStop (output)

- `decision`: `"block"` (optional)
- `reason`: string
- `hookSpecificOutput.hookEventName`: `"Stop"` or `"SubagentStop"`
- `hookSpecificOutput.additionalContext`: string (non-error feedback injected into next turn)

### SubagentStart

- `hookSpecificOutput.additionalContext`: string (added to subagent context)

### PermissionRequest

- `hookSpecificOutput.decision.behavior`: `allow|deny`
- `hookSpecificOutput.decision.updatedInput`: object (allow only)
- `hookSpecificOutput.decision.updatedPermissions`: array of permission update entries (allow only)
- `hookSpecificOutput.decision.message`: string (deny only)
- `hookSpecificOutput.decision.interrupt`: boolean (deny only)

Permission update entry `type`: `addRules|replaceRules|removeRules|setMode|addDirectories|removeDirectories`; `destination`: `session|localSettings|projectSettings|userSettings`

### PermissionDenied

- `hookSpecificOutput.retry`: boolean

### WorktreeCreate

- `hookSpecificOutput.worktreePath`: string (absolute path; command hooks print path on stdout)

### MessageDisplay

- `hookSpecificOutput.displayContent`: string (modified display text)

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
- `$CLAUDE_PLUGIN_OPTION_*` — plugin user config options (e.g. `$CLAUDE_PLUGIN_OPTION_MY_KEY`)
- `$CLAUDE_CODE_REMOTE` — `"true"` in web environments
- `$CLAUDE_EFFORT` — effort level (`low`, `medium`, `high`, `xhigh`, `max`)
- `$CLAUDE_ENV_FILE` — env persist file (SessionStart, Setup, CwdChanged, FileChanged only)
- `$CLAUDE_CODE_BRIDGE_SESSION_ID` — Remote Control session ID (v2.1.199+)

## Settings Allowlists

- `allowedHttpHookUrls` — array of URL globs permitted for HTTP hooks (e.g. `["http://localhost:*", "https://trusted.com/*"]`)
- `httpHookAllowedEnvVars` — array of env var names that HTTP hooks may read (e.g. `["TOKEN", "API_KEY"]`)

## Version Requirements

- `prompt_id` field: v2.1.196+
- `bypass_permissions_disabled` SessionEnd reason removed: v2.1.234
- `quota_auto_resume_*` notification types: v2.1.234+
- PreModelSwitch / PostModelSwitch, SessionStart resume cost fields: v2.1.251+
- `mcp_server` input field (tool events): v2.1.274+
- `agent_id` on TaskCreated/TaskCompleted/TeammateIdle: v2.1.290+
- `classifierContext` (PostToolUse output): v2.1.236+
- `onFailure` handler field: v2.1.295+
- `scratchpad_dir` field: v2.1.257+
- `cloud_credential_error` in `StopFailure`: v2.1.267+

## Constraints

- Hook output capped at 10,000 characters (exceeding saves to file with shortened model preview)
- All matching hooks run in parallel
- Identical handlers deduplicated by command/URL
- JSON-only stdout on exit 0
- `OTEL_*` exporter variables are removed from all subprocess environments
