# Cline Hooks Specification

> Source: https://docs.cline.bot/sdk/hooks
> (Original URL https://docs.cline.bot/customization/hooks now redirects to the SDK Hooks page)
> Snapshot: 2026-06-30

## Migration Note

As of 2026-06-30, Cline has migrated from the shell-executable hook system
(`~/Documents/Cline/Hooks/`, `.clinerules/hooks/`) to an SDK-based hook system.
The old file-based format (8 events: TaskStart/Resume/Cancel/Complete, PreToolUse,
PostToolUse, UserPromptSubmit, PreCompact) is superseded by the SDK hooks below.

## SDK Plugin Structure

Hooks are defined via the Cline SDK (TypeScript):

```typescript
import { ClineHook } from "@cline/sdk";

const hook: ClineHook = {
  mode: "blocking",          // "blocking" | "async"
  timeoutMs: 30000,
  retries: 0,
  retryDelayMs: 1000,
  failureMode: "fail_open",  // "fail_open" | "fail_closed"
  maxConcurrency: 1,
  queueLimit: 100,
};
```

## Hook Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | — | `"blocking"` (waits for result) or `"async"` (fire-and-forget) |
| `timeoutMs` | number | — | Maximum duration before timeout |
| `retries` | number | 0 | Retry count on failure |
| `retryDelayMs` | number | 1000 | Pause between retries (ms) |
| `failureMode` | string | `"fail_open"` | `"fail_open"` proceeds on failure; `"fail_closed"` blocks |
| `maxConcurrency` | number | 1 | Parallel hook executions |
| `queueLimit` | number | 100 | Max queued hooks before dropping |

## Hook Events (15 total)

### Lifecycle Events

| Event | Description |
|-------|-------------|
| `session_start` | Session initialization |
| `session_shutdown` | Session teardown |
| `run_start` | Run begins (logging, timers, rate limit init) |
| `run_end` | Run ends (metrics, alerts, cleanup) |

### Execution Events

| Event | Description |
|-------|-------------|
| `iteration_start` | Iteration begins within a run |
| `iteration_end` | Iteration completes |
| `turn_start` | LLM turn begins |
| `turn_end` | LLM turn completes |

### Agent Events

| Event | Description |
|-------|-------------|
| `before_agent_start` | Before agent activates (inject context / modify prompt) |

### Tool Events

| Event | Description |
|-------|-------------|
| `tool_call_before` | Before tool invocation (audit or prevent) |
| `tool_call_after` | After tool invocation (record outcomes, side effects) |

### Error / Generic Events

| Event | Description |
|-------|-------------|
| `stop_error` | Execution stopped due to error |
| `error` | Exception notification |
| `input` | Input processing event |
| `runtime_event` | Generic runtime notification |

## Common Hook Scenarios

- **`before_agent_start`**: Inject context or modify prompt/messages
- **`run_start`**: Logging, timers, rate limit initialization
- **`tool_call_before`**: Audit or prevent tool invocations
- **`tool_call_after`**: Record outcomes, activate side operations
- **`run_end`**: Metrics collection, alert dispatch, resource cleanup
- **`error`**: Exception reporting mechanisms

## Integration Notes

otel-hooks integration:

- New Cline SDK events are mapped in `hook_event.py`
- Source detection via `source_tool: "cline"` hint or legacy `taskId` field
- For new SDK-based payloads without `taskId`, pass `--tool cline` flag or
  set `source_tool: "cline"` in the payload

## Legacy Format (pre-2026-06-30, for reference)

Old config locations: `~/Documents/Cline/Hooks/` (global), `.clinerules/hooks/` (project)

Old events: `TaskStart`, `TaskResume`, `TaskCancel`, `TaskComplete`, `PreToolUse`,
`PostToolUse`, `UserPromptSubmit`, `PreCompact`

Old detection field: `taskId` in payload
