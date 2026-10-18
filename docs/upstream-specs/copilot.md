# GitHub Copilot Hooks Specification

> Source: https://docs.github.com/en/copilot/reference/hooks-configuration
> Snapshot: 2026-10-13

## Config Location

Hooks can be defined in dedicated hook files or inline within settings files:

| Scope | Path |
|-------|------|
| Policy (Linux/macOS) | `/etc/github-copilot/policy.d/*.json` |
| Policy (Windows) | `C:\ProgramData\GitHub\Copilot\policy.d\*.json` |
| Policy (Windows Registry) | `HKLM\Software\Policies\GitHub\Copilot` (REG_SZ values) |
| Project (repository) — dedicated file | `.github/hooks/<name>.json` |
| Project (repository) — inline | `.github/copilot/settings.json` or `.github/copilot/settings.local.json` (under `hooks` key) |
| Project (repository) — inline, cross-tool | `.claude/settings.json` or `.claude/settings.local.json` (under `hooks` key) |
| User (CLI) — dedicated file | `~/.copilot/hooks/*.json` (macOS/Linux), `%USERPROFILE%\.copilot\hooks\*.json` (Windows), or `$COPILOT_HOME/hooks/` if set |
| User (CLI) — inline | `~/.copilot/settings.json` (under `hooks` key; `config.json` is no longer read for hooks) |
| Plugin-contributed | `hooks.json` or `hooks/hooks.json` in each plugin's install directory |

Load order (CLI): Policy files → Repository `.github/hooks/*.json` → User `~/.copilot/hooks/*.json` → Inline repo settings (`.github/copilot/settings*.json`, `.claude/settings*.json`) → Inline `~/.copilot/settings.json` → Plugins. Hooks from all sources combine.

Malformed items: in directory-loaded files only the bad item is dropped; invalid JSON, bad `version`, or a non-array event list rejects the whole file. Inline `settings.json` hooks are strict.

Cloud Agent: only `.github/hooks/*.json` files loaded; policy, user-level, and plugin hooks unavailable.
Cloud agents run in a Linux sandbox; only `bash` field honored (not `powershell`); network is restricted.

Policy hooks cannot be disabled by `disableAllHooks`. Policy files (POSIX) must be root-owned and not group/world-writable.

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
        "exec": "string (executable name; used with args for exec form)",
        "args": ["string", "..."],
        "cwd": "string (optional)",
        "env": { "<key>": "<value>" },
        "timeoutSec": 30,
        "matcher": "string (optional regex; see Matcher Filtering)",
        "comment": "string (optional)"
      }
    ]
  },
  "disableAllHooks": true
}
```

### Hook Types

- `command` — shell script; `bash` (Linux/macOS), `powershell` (Windows), or cross-platform `command`. `type` defaults to `command` when omitted. `exec`/`args` are CLI only and cannot be combined with `bash`/`powershell`/`command`
- `http` — POST JSON payload; fields: `url`, `headers`, `allowedEnvVars`, `timeoutSec`. `url` must be `https://` for `preToolUse` and `permissionRequest`
- `prompt` — auto-submit text; fields: `prompt`. Only valid on `sessionStart` (CLI: new interactive sessions only)

**Progress Messages** (command hooks): Hooks may emit transient status updates to stdout before the final JSON output:

```json
{"type": "progress", "message": "Checking policy..."}
{"type": "progress", "message": "Routing...", "temporary": true}
```

Lines with `"type": "progress"` are consumed and displayed as status; they are excluded from hook output parsing.

### Matcher Filtering

Optional regex patterns (compiled as `^(?:PATTERN)$`) supported for:

| Event | Matched against |
|-------|-----------------|
| `notification` | `notification_type` |
| `permissionRequest` | `toolName` |
| `postToolUse` | `toolName` |
| `preCompact` | `trigger` |
| `preToolUse` | `toolName` |
| `subagentStart` | `agentName` |

## Event Name Casing / Payload Formats

Event names may be configured in camelCase or PascalCase. The casing selects the payload format: camelCase → camelCase payload (below); PascalCase → VS Code-compatible snake_case payload with `hook_event_name`.

| camelCase | PascalCase |
|-----------|-----------|
| sessionStart | SessionStart |
| sessionEnd | SessionEnd |
| userPromptSubmitted | UserPromptSubmit |
| userPromptTransformed | (none) |
| preToolUse | PreToolUse |
| postToolUse | PostToolUse |
| postToolUseFailure | PostToolUseFailure |
| agentStop | Stop |
| subagentStart | (none) |
| subagentStop | SubagentStop |
| errorOccurred | ErrorOccurred |
| preCompact | PreCompact |
| permissionRequest | PermissionRequest |
| notification | (none) |

VS Code (snake_case) payload fields: `hook_event_name`, `session_id`, `timestamp` (ISO 8601), `cwd`, plus per-event: `source`, `initial_prompt` (SessionStart); `reason` (SessionEnd); `prompt` (UserPromptSubmit); `tool_name`, `tool_input` (PreToolUse); `tool_name`, `tool_input`, `tool_result: { result_type, text_result_for_llm }` (PostToolUse); `tool_name`, `tool_input`, `error` (PostToolUseFailure); `transcript_path`, `stop_reason`, `stop_hook_active` (Stop); `transcript_path`, `agent_id`, `agent_type`, `agent_name`, `agent_display_name`, `last_assistant_message`, `stop_reason` (SubagentStop); `error`, `error_context`, `recoverable` (ErrorOccurred); `transcript_path`, `trigger`, `custom_instructions` (PreCompact).

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
  "toolArgs": "string (JSON-stringified)",
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
  "stopReason": "string",
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
  "stopReason": "string"
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

### permissionRequest

Full input schema not documented. References `toolName` (matcher target) and `toolInput` (may include `requestSandboxBypass: true`; `allow` does not pre-approve such requests).

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

## Output (events with output)

### preToolUse

```json
{
  "permissionDecision": "allow|deny|ask",
  "permissionDecisionReason": "string",
  "modifiedArgs": "object (optional)"
}
```

Note: `permissionDecisionReason` is required for `deny`; `ask` becomes `deny` in cloud agent.

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
| 2 | Warning — stderr surfaced but execution continues. For `preToolUse`/`permissionRequest`: deny (even if stdout says allow). For `postToolUseFailure`: stdout appended as `additionalContext` |
| Other | Logged failure — execution continues (`preToolUse`: denied, fail-closed) |
| Timeout | Killed after `timeoutSec`; always fail-open (all events, including `preToolUse` and policy hooks) |

## Supported Tool Names (for `preToolUse` matcher)

`ask_user`, `bash`, `create`, `edit`, `glob`, `grep`, `powershell`, `task`, `view`, `web_fetch`, `rg`, `str_replace_editor`, `apply_patch`, `web_search`, `update_todo`

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
| OS | Linux; only `bash` field honored |
| Working directory | `/workspace` (repo) or `/root` |
| Filesystem | Ephemeral; discarded when job ends |
| Network | Restricted; only GitHub/Copilot reachable |
| Environment | `GITHUB_COPILOT_API_TOKEN`, `GITHUB_COPILOT_GIT_TOKEN`, `COPILOT_AGENT_PROMPT`, `HOME=/root` set; `GITHUB_TOKEN` not set |
| Interactivity | Non-interactive; all tool permissions pre-granted |
| Config | Only `.github/hooks/*.json` loaded |

## Constraints

- Default timeout: 30 seconds (`timeoutSec`; the `timeout` field is a deprecated alias)
- Multiple hooks of same type execute sequentially
- Scripts read JSON from stdin
- `disableAllHooks: true` disables all hooks in a file
- `transcriptPath` now included in `agentStop`, `subagentStart`, `subagentStop`, `preCompact`
- `preToolUse` command hooks are **fail-closed** on crashes, exit 2, and non-timeout errors; timeouts are fail-open. HTTP hooks are fail-open on network errors, timeouts, and non-2xx responses
- **Runaway guard**: After 8 consecutive `block` decisions from `agentStop` / `subagentStop`, the CLI overrides and ends the turn
- Built-in `general-purpose` agent does not emit `subagentStart` / `subagentStop`
- `/clear` (CLI) fires `sessionEnd` with `reason: "user_exit"` as a detached background hook
- Sandboxed CLI sessions: repo, user, and plugin command hooks run inside the sandbox; policy hooks run on the host
- Hook output bounded at **10 MiB** per invocation; `additionalContext` capped at **10 KB** when multiple hooks return it
- HTTP hooks require HTTPS by default for permission events; HTTP allowed for localhost only with `COPILOT_HOOK_ALLOW_LOCALHOST=1`
