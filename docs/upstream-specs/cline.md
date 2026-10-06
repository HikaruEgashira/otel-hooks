# Cline Hooks Specification

> Source: https://docs.cline.bot/sdk/plugins
> (https://docs.cline.bot/sdk/hooks 308-redirects here; https://docs.cline.bot/customization/hooks is a stub page linking to SDK Plugins)
> Snapshot: 2026-10-06

## Migration Note

As of 2026-06-30, Cline has migrated from the shell-executable hook system
(`~/Documents/Cline/Hooks/`, `.clinerules/hooks/`) to an SDK-based hook system.
The old file-based format (8 events: TaskStart/Resume/Cancel/Complete, PreToolUse,
PostToolUse, UserPromptSubmit, PreCompact) is superseded by the SDK hooks below.

## SDK Plugin Structure

Hooks are defined via the Cline SDK (TypeScript) inside the `hooks` object of an `AgentPlugin`:

```typescript
import { type AgentPlugin } from "@cline/sdk"

const myPlugin: AgentPlugin = {
  name: "my-plugin",
  manifest: { capabilities: ["tools", "hooks"] },
  setup(api, ctx) { /* api.registerTool(), etc. */ },
  hooks: {
    beforeTool(context) { /* ... */ },
    afterRun(context) { /* ... */ },
  },
}
```

Hooks are defined inside the `hooks` object (not on the extension). Available lifecycle hooks:
`beforeRun`, `afterRun`, `beforeModel`, `afterModel`, `beforeTool`, `afterTool`, `onEvent`.
Hook stages (below) are listed separately under "Hook Stages".

## Plugin Registration & Locations

Source: https://docs.cline.bot/customization/plugins

- Programmatic: `cline.start({ config: { extensions: [plugin] } })` or `config.pluginPaths: ["/absolute/path/to/plugin.ts"]`
- CLI: `cline plugin install <npm|git|file URL|local path>` (`--cwd <path>` installs to `<path>/.cline/plugins`)
- Global plugins: `~/.cline/plugins/` (managed installs under `~/.cline/plugins/_installed/{npm,git,remote,local}/`)
- Project plugins: `.cline/plugins/`
- package.json manifest: `"cline": { "plugins": [{ "paths": ["./index.ts"], "capabilities": ["tools", "hooks"] }] }` (or plain string entries); each path exports an `AgentPlugin`

## Hook Configuration Fields (Hook Policies)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | — | `"blocking"` (waits for result) or `"async"` (fire-and-forget) |
| `timeoutMs` | number | — | Maximum duration before timeout |
| `retries` | number | — | Retry count on failure |
| `retryDelayMs` | number | — | Pause between retries (ms) |
| `failureMode` | string | — | `"fail_open"` proceeds on failure; `"fail_closed"` blocks |
| `maxConcurrency` | number | — | Parallel hook executions |
| `queueLimit` | number | — | Max queued hooks before dropping |

Defaults are not documented upstream.
Use `fail_closed` for policy-enforcement hooks where bypassing the hook is unsafe.

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
