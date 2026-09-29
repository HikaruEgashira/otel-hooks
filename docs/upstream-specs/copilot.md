# GitHub Copilot Hooks Specification

> Source: https://docs.github.com/en/copilot/reference/hooks-configuration
> Snapshot: 2026-09-29

## Config Location

Hooks can be defined in dedicated hook files or inline within settings files:

| Scope | Path |
|-------|------|
| Policy (Linux/macOS) | `/etc/github-copilot/policy.d/*.json` |
| Policy (Windows) | `C:\ProgramData\GitHub\Copilot\policy.d\*.json` |
| Policy (Windows Registry) | `HKLM\Software\Policies\GitHub\Copilot` (each subkey holds a `Policy` REG_SZ value containing a JSON policy document) |
| Project (repository) — dedicated file | `.github/hooks/<name>.json` |
| Project (repository) — inline | `.github/copilot/settings.json` or `.github/copilot/settings.local.json` (under `hooks` key) |
| Project (repository) — inline, cross-tool | `.claude/settings.json` or `.claude/settings.local.json` (under `hooks` key; "Cross-tool ... files in the repository are also read") |
| User (CLI) — dedicated file | `~/.copilot/hooks/*.json` (macOS/Linux); `%USERPROFILE%\.copilot\hooks\` (Windows); `$COPILOT_HOME/hooks/` if `COPILOT_HOME` is set |
| User (CLI) — inline | `~/.copilot/settings.json` (under `hooks` key) |
| Plugin-contributed | `hooks.json` or `hooks/hooks.json` in the plugin's installation directory |

Load order: Policy → User → Project → Plugins. Hooks from all sources combine.

Cloud Agent: only `.github/hooks/*.json` files loaded; policy, user-level, and plugin hooks unavailable.
Cloud agents run in a Linux sandbox; only `bash` field honored (not `powershell`), with the cross-platform `command` field honored as a fallback; network is restricted.

Malformed hook items in directory-loaded files (e.g. `.github/hooks/`) are dropped individually; structural errors (invalid JSON, bad `version`, non-array event list) reject the whole file. Inline `hooks` in `settings.json` are strict: any item-level validation error rejects the whole `hooks` field.

Policy hooks cannot be disabled by `disableAllHooks`. Policy files (POSIX) must be root-owned and not group/world-writable.

## Config Schema

```json
{
  "version": 1,
  "hooks": {
    "<hookEventName>": [
      {
        "type": "command (optional; defaults to \"command\")",
        "matcher": "regex string (optional; see Matcher Filtering)",
        "bash": "string (script path)",
        "powershell": "string (script path)",
        "command": "string (cross-platform path)",
        "exec": "string (executable name; used with args for exec form)",
        "args": ["string", "..."],
        "cwd": "string (optional)",
        "env": { "<key>": "<value>" },
        "timeoutSec": 30,
        "timeout": "number (optional; alias for timeoutSec)",
        "comment": "string (optional; not documented upstream as of 2026-09-29)"
      }
    ]
  },
  "disableAllHooks": true
}
```

- `timeout`: "Alias for `timeoutSec`, in seconds. Used only when `timeoutSec` is absent; `timeoutSec` takes precedence when both are present." (applies to command and HTTP hooks)
- `command`: cross-platform fallback, "Copied to both `bash` and `powershell` when those fields are absent"
- `exec` / `args`: CLI only; do not combine `exec` with `bash`, `powershell`, or `command`
- `comment`: not documented upstream as of 2026-09-29

### Hook Types

- `command` — shell script; `bash` (Linux/macOS), `powershell` (Windows), or cross-platform `command`
- `http` — POST JSON payload; fields: `type` (required, `"http"`), `url` (required), `headers`, `allowedEnvVars`, `timeoutSec`, `timeout` (alias), `matcher`
  - Only `https://` allowed by default; `http://localhost`, `http://127.*`, `http://[::1]` allowed when `COPILOT_HOOK_ALLOW_LOCALHOST=1`
  - For `preToolUse` and `permissionRequest`, `url` must use `https://`; when `allowedEnvVars` is set, `url` must use `https://`
- `prompt` — auto-submit text; fields: `type` (required, `"prompt"`), `prompt` (required). Only supported on `sessionStart`; fires only for new interactive sessions (not on resume, not in `-p` mode)

**Progress Messages** (command hooks): Hooks may emit transient status updates to stdout before the final JSON output:

```json
{"type": "progress", "message": "Checking policy..."}
{"type": "progress", "message": "Routing...", "temporary": true}
```

Lines with `"type": "progress"` are consumed and displayed as status; they are excluded from hook output parsing.

### Matcher Filtering

Optional `matcher` regex on each hook entry, compiled as `^(?:PATTERN)$` (must match the full value). Invalid regexes cause the hook entry to be skipped.

| Event | `matcher` is matched against |
|-------|------------------------------|
| `notification` | `notification_type` |
| `permissionRequest` | `toolName` |
| `postToolUse` | `toolName` |
| `preCompact` | `trigger` (`"manual"` or `"auto"`) |
| `preToolUse` | `toolName` |
| `subagentStart` | `agentName` |

PascalCase `PreToolUse` / `PermissionRequest` use Claude-format matchers: `*`, `**`, or empty fires for every tool; a literal name or `|`-separated alternation matches the runtime or Claude tool name; any other value is a case-sensitive regex anchored `^(?:PATTERN)$` against the Claude tool name.

## Hook Events (14 total)

| Event | Has Output | Description |
|-------|-----------|-------------|
| sessionStart | Yes | New or resumed session begins; can inject `additionalContext` |
| sessionEnd | No | Session completes or terminates |
| userPromptSubmitted | Yes | User submits a prompt; can return `modifiedPrompt` (SDK hooks only) |
| userPromptTransformed | Yes | After prompt transformation, before model receives it |
| preToolUse | Yes | Before tool execution (can deny) |
| postToolUse | Yes | After tool execution (can modify result) |
| postToolUseFailure | Yes | After a tool completes with a failure; can return `additionalContext` |
| errorOccurred | No | Error during execution |
| agentStop | Yes | Main agent finishes a turn (can block; 8-consecutive-block runaway guard) |
| notification | Yes | Async system notification (CLI only); can return `additionalContext` |
| permissionRequest | Yes | Before permission service runs (CLI only) |
| preCompact | No | Context compaction is about to begin |
| subagentStart | Yes | A subagent is spawned; can inject context (cannot block) |
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

Output:
```json
{
  "additionalContext": "string (optional, injected into session)"
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

Output (SDK programmatic hooks only; command/HTTP hooks output is dropped):
```json
{
  "modifiedPrompt": "string"
}
```

### userPromptTransformed

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "prompt": "string",
  "transformedPrompt": "string"
}
```

Output:
```json
{
  "modifiedTransformedPrompt": "string"
}
```

### preToolUse

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "unknown"
}
```

### postToolUse

```json
{
  "sessionId": "string",
  "timestamp": "number (Unix ms)",
  "cwd": "string",
  "toolName": "string",
  "toolArgs": "unknown",
  "toolResult": {
    "resultType": "success",
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
  "toolArgs": "unknown",
  "error": "string"
}
```

Output:
```json
{
  "additionalContext": "string (optional, recovery guidance for the model)"
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
  "stopReason": "end_turn",
  "stop_hook_active": "boolean (true when a previous Stop hook blocked)"
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
  "agentId": "string",
  "agentType": "string",
  "agentName": "string",
  "agentDisplayName": "string (optional)",
  "response": "string (subagent's final response text)",
  "stopReason": "end_turn"
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

Output:
```json
{
  "additionalContext": "string (optional, injected as user message)"
}
```

### permissionRequest

No dedicated input schema is documented upstream. Upstream notes a sandbox-bypass exception: for requests with `requestSandboxBypass: true` in `toolInput`, a hook `allow` does not pre-approve the escape; only `deny` propagates. `read` and `hook` permission kinds short-circuit before hooks run.

Notes:
- `stopReason` is currently always `"end_turn"` (agentStop, subagentStop).
- `toolArgs` is typed `unknown` upstream (camelCase format).

## VS Code Compatible Payload Format (PascalCase / snake_case)

Two payload formats are supported, selected by the event name used in the hook configuration:

- **camelCase format** — event name in camelCase (e.g. `sessionStart`); fields use camelCase (schemas above).
- **VS Code compatible format** — event name in PascalCase (e.g. `SessionStart`); fields use snake_case to match the VS Code Copilot extension format.

| camelCase event | PascalCase event |
|-----------------|------------------|
| sessionStart | SessionStart |
| sessionEnd | SessionEnd |
| userPromptSubmitted | UserPromptSubmit |
| preToolUse | PreToolUse |
| postToolUse | PostToolUse |
| postToolUseFailure | PostToolUseFailure |
| agentStop | Stop |
| subagentStop | SubagentStop |
| errorOccurred | ErrorOccurred |
| preCompact | PreCompact |
| permissionRequest | PermissionRequest (Claude-format matcher semantics) |

`userPromptTransformed`, `subagentStart`, and `notification` have no VS Code compatible variant documented.

Common fields (all VS Code compatible payloads):

```json
{
  "hook_event_name": "<PascalCase event name>",
  "session_id": "string",
  "timestamp": "string (ISO 8601)",
  "cwd": "string"
}
```

Per-event additional fields:

| Event | Additional fields |
|-------|-------------------|
| SessionStart | `source`: `startup\|resume\|new`, `initial_prompt` (optional) |
| SessionEnd | `reason`: `complete\|error\|abort\|timeout\|user_exit` |
| UserPromptSubmit | `prompt` |
| PreToolUse | `tool_name`, `tool_input` (unknown; "parsed from JSON string when possible") |
| PostToolUse | `tool_name`, `tool_input`, `tool_result`: `{ "result_type": "success", "text_result_for_llm": "string" }` |
| PostToolUseFailure | `tool_name`, `tool_input`, `error` (string) |
| Stop | `transcript_path`, `stop_reason`: `end_turn`, `stop_hook_active` (boolean) |
| SubagentStop | `transcript_path`, `agent_id`, `agent_type`, `agent_name`, `agent_display_name` (optional), `last_assistant_message` (the `response` text), `stop_reason`: `end_turn` |
| ErrorOccurred | `error`: `{ message, name, stack? }`, `error_context`: `model_call\|tool_execution\|system\|user_input`, `recoverable` (boolean) |
| PreCompact | `transcript_path`, `trigger`: `manual\|auto`, `custom_instructions` |

Payloads for PascalCase `PreToolUse` report `tool_name` as the Claude tool name (e.g. `Bash`, not `bash`). Output field names (`decision`, `reason`, `modifiedResponse`) are the same in both formats for `agentStop`/`subagentStop`.

## Output (events with output)

### preToolUse

```json
{
  "permissionDecision": "allow|deny|ask",
  "permissionDecisionReason": "string",
  "modifiedArgs": "object (optional)"
}
```

Note: `permissionDecisionReason` is required when decision is `"deny"`. Under cloud agent, `"ask"` is treated as `"deny"`. (The previous note "only `deny` is processed" is not documented upstream as of 2026-09-29.)

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

### subagentStart

```json
{
  "additionalContext": "string (optional, prepended to subagent prompt; cannot block)"
}
```

### agentStop

```json
{
  "decision": "block|allow",
  "reason": "string"
}
```

### subagentStop

```json
{
  "decision": "block|allow",
  "reason": "string",
  "modifiedResponse": "string (optional, replaces subagent response returned to parent)"
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

### notification

```json
{
  "additionalContext": "string (optional, injected as user message)"
}
```

## Exit Codes (command hooks)

| Code | Meaning |
|------|---------|
| 0 | Success — stdout parsed as JSON |
| 2 | Warning — stderr surfaced but execution continues. For `permissionRequest` and `preToolUse`, exit 2 is a **deny** (stdout JSON merged with the deny even if it reports `allow`). For `postToolUseFailure`, exit 2 is treated as `additionalContext` (stdout appended to the failure shown to the agent) |
| Other | Logged failure — execution continues (fail-open). Exception: `preToolUse` is fail-closed — denies with `"Denied by preToolUse hook (hook errored)"` |
| Timeout | Killed after `timeoutSec`; fail-open for every event, including `preToolUse` and policy hooks |

## Supported Tool Names (for `preToolUse` matcher)

`ask_user`, `bash`, `create`, `edit`, `glob`, `grep`, `powershell`, `task`, `view`, `web_fetch`, `rg`, `str_replace_editor`, `apply_patch`, `web_search`, `update_todo`

Note: as of 2026-09-29 the upstream "Tool names for hook matching" table lists only `ask_user`, `bash`, `create`, `edit`, `glob`, `grep`, `powershell`, `task`, `view`, `web_fetch`; `rg`, `str_replace_editor`, `apply_patch`, `web_search`, `update_todo` appear upstream only in the Claude tool name mapping table below.

### Claude Tool Name Mappings (PascalCase matchers)

| Runtime name | Claude name |
|---|---|
| `bash`, `powershell` | `Bash` |
| `view` | `Read` |
| `create` | `Write` |
| `edit`, `str_replace_editor`, `apply_patch` | `Edit` |
| `grep`, `rg` | `Grep` |
| `glob` | `Glob` |
| `web_fetch` | `WebFetch` |
| `web_search` | `WebSearch` |
| `ask_user` | `AskUserQuestion` |
| `update_todo` | `TodoWrite` |
| `task` | `Agent` (`Task` also accepted) |

## Cloud Agent Execution Environment

| Property | Value |
|----------|-------|
| OS | Linux; only `bash` field honored (`powershell` ignored); cross-platform `command` honored as a fallback |
| Working directory | `/workspace` (repo) or `/root` |
| Filesystem | Ephemeral; discarded when job ends |
| Network | Restricted; only GitHub/Copilot reachable |
| Environment | `GITHUB_COPILOT_API_TOKEN`, `GITHUB_COPILOT_GIT_TOKEN`, `COPILOT_AGENT_PROMPT`, `HOME=/root` set; `GITHUB_TOKEN` not set |
| Interactivity | Non-interactive; all tool permissions pre-granted |
| Config | Only `.github/hooks/*.json` loaded |

## Constraints

- Default timeout: 30 seconds (`timeoutSec`; `timeout` is an alias used only when `timeoutSec` is absent)
- Multiple hooks of same type execute sequentially
- Scripts read JSON from stdin
- `disableAllHooks: true` disables all hooks in a file
- `transcriptPath` now included in `agentStop`, `subagentStart`, `subagentStop`, `preCompact`
- `preToolUse` command hooks are **fail-closed** on errors: exit 2, crashes, and any other non-zero exit deny the tool call. **Timeouts are always fail-open**, even for `preToolUse` and admin-deployed policy hooks (tool call proceeds through the normal permission flow)
- HTTP `preToolUse` hooks are **fail-open**: network error, timeout, or non-2xx response falls through to the default permission flow
- **Runaway guard**: After 8 consecutive `block` decisions from `agentStop`, the CLI overrides and ends the turn
- Hook output bounded at **10 MiB** per invocation; `additionalContext` capped at **10 KB** when multiple hooks return it
- HTTP hooks require HTTPS by default for permission events; HTTP allowed for localhost only with `COPILOT_HOOK_ALLOW_LOCALHOST=1`
