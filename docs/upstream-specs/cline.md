# Cline Hooks Specification

> Source: https://docs.cline.bot/sdk/plugins
> (https://docs.cline.bot/customization/hooks is now a stub pointing to SDK Plugins;
> https://docs.cline.bot/sdk/hooks serves the same "Plugins Overview" content as /sdk/plugins.
> Config paths: https://docs.cline.bot/customization/plugins)
> Snapshot: 2026-09-29

## Migration Note

As of 2026-06-30, Cline has migrated from the shell-executable hook system
(`~/Documents/Cline/Hooks/`, `.clinerules/hooks/`) to an SDK-based hook system.
The old file-based format (8 events: TaskStart/Resume/Cancel/Complete, PreToolUse,
PostToolUse, UserPromptSubmit, PreCompact) is superseded by the SDK hooks below.

## SDK Plugin Structure

Hooks are defined inside the `hooks` object of an `AgentPlugin` (not directly on the extension):

```typescript
import { type AgentPlugin } from "@cline/sdk"

const myPlugin: AgentPlugin = {
  name: "my-plugin",
  manifest: {
    capabilities: ["tools", "hooks"],
  },
  setup(api, ctx) {
    // Register tools, commands, providers via api.registerTool(), etc.
  },
  hooks: {
    beforeTool(context) { /* observe or audit tool calls */ },
    afterRun(context) { /* metrics, cleanup, notify */ },
  },
}
```

Available lifecycle hook methods: `beforeRun`, `afterRun`, `beforeModel`, `afterModel`,
`beforeTool`, `afterTool`, `onEvent`.

## Plugin Registration / Config Location

| Method | Location |
|--------|----------|
| In code | `cline.start({ config: { extensions: [myPlugin] } })` |
| File-based | `cline.start({ config: { pluginPaths: ["/absolute/path/to/plugin.ts"] } })` (file exports an `AgentPlugin`) |
| Global plugins | `~/.cline/plugins/` (`_installed/{npm,git,remote,local}/` managed by `cline plugin install`) |
| Project plugins | `.cline/plugins/` (`cline plugin install --cwd <path>` installs to `<path>/.cline/plugins`) |

package.json manifest:

```json
{
  "cline": {
    "plugins": [
      { "paths": ["./index.ts"], "capabilities": ["tools", "hooks"] }
    ]
  }
}
```

(Plain string entries such as `"./index.ts"` are also accepted.)

Scope: plugins currently apply only to Cline SDK, CLI, and Kanban — not to the VSCode / JetBrains extensions.

## Hook Policies

Hook policies control execution behavior (upstream no longer documents types/defaults):

| Field | Meaning |
|-------|---------|
| `mode` | `"blocking"` or `"async"` |
| `timeoutMs` | Hook timeout |
| `retries` | Retry count |
| `retryDelayMs` | Delay between retries |
| `failureMode` | `"fail_open"` or `"fail_closed"` (use `fail_closed` for policy-enforcement hooks where bypassing is unsafe) |
| `maxConcurrency` | Concurrent hook executions |
| `queueLimit` | Queue size before dropping |

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
