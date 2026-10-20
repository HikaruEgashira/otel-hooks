# Cline Hooks Specification

> Source: https://docs.cline.bot/sdk/plugins (also https://docs.cline.bot/sdk/hooks)
> (Original URL https://docs.cline.bot/customization/hooks is now a stub pointing to the SDK Plugins page)
> Snapshot: 2026-10-20

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

Available lifecycle hooks: `beforeRun`, `afterRun`, `beforeModel`, `afterModel`, `beforeTool`, `afterTool`, `onEvent`.

## Plugin Hook Keys (AgentPlugin)

As of 2026-10-13, hooks are attached via a `hooks` object on an `AgentPlugin`
(not directly on the plugin). The plugin declares `"hooks"` in
`manifest.capabilities` and registers tools etc. in `setup(api, ctx)`.

```typescript
const plugin: AgentPlugin = {
  name: "my-plugin",
  manifest: { capabilities: ["tools", "hooks"] },
  setup(api, ctx) { /* register tools */ },
  hooks: {
    beforeTool(context) { /* context.toolCall.name, context.input */ },
    afterRun(context) { /* context.result.usage.inputTokens / outputTokens */ },
  },
};
```

All hooks receive a context with the current runtime `snapshot` (agent id, conversation id, iteration, messages, usage).

| Hook key | When | Context fields | Can return |
|----------|------|----------------|------------|
| `beforeRun` | Before a run starts | `snapshot` | `stop` + `reason` to end the run; `appendContext` (text the model sees on its first request) |
| `afterRun` | After a run ends | `result` (`result.usage.inputTokens` / `outputTokens`, may be undefined) | Nothing (metrics, notifications, cleanup) |
| `beforeModel` | Before each model request | `request` | `messages`, `tools`, or `options` to change the request; `stop` + `reason` |
| `afterModel` | After each model response | `assistantMessage`, `finishReason` | `stop` + `reason` |
| `beforeTool` | Before a tool runs | `tool`, `toolCall` (`toolCall.name`), `input` | `skip` + `reason` to block the call (reason goes back to the model); `input` to replace the input; `policy` (e.g. `{ autoApprove: false }`) to require approval; `appendContext`; `stop` |
| `afterTool` | After a tool runs | `result`, timing | `result` to replace the result; `appendContext`; `stop` + `reason` |
| `onEvent` | For runtime events | runtime event | Nothing |

(Context/return fields documented as of 2026-10-20.)

## Hook Failure Handling

Each plugin hook call has a 3-second timeout. If a hook throws, rejects, or times out, the session's `hookErrorMode` decides what happens:

| `hookErrorMode` | Behavior |
|-----------------|----------|
| `"ignore"` (default) | Failure is recorded and reported; the run continues as if the hook returned nothing |
| `"throw"` | Error is rethrown and the run fails |

A hook that keeps failing marks its plugin `degraded`, then `failed` after five failures in a row.

## Plugin Runtime

- By default each plugin runs in its own worker thread, one per session, inside the host's runtime.
- Opt-in `sandbox` mode (previous per-session subprocess sandbox) via `CLINE_PLUGIN_MODE` (or `mode` on `resolveAndLoadAgentPlugins`).
- Plugin `console.log` and stdout output are discarded (cannot corrupt `--json` output or a JSON-RPC stream); use `ctx.logger`.
- Values passed to and returned from a plugin cross a thread boundary and must be plain data; functions are dropped.

## Setup Context and Plugin Status

`setup(api, ctx)` context: `ctx.cwd`, `ctx.session?.sessionId`, `ctx.emitEvent(name, payload)`, `ctx.workspaceInfo`, `ctx.onDispose(fn)`, `ctx.logger`.

| Stage | Timeout |
|-------|---------|
| Import | 4 s (`CLINE_PLUGIN_IMPORT_TIMEOUT_MS`) |
| `setup()` | 4 s |
| Hook | 3 s (plugin becomes `degraded`; run continues unless `hookErrorMode` is `"throw"`) |
| Tool | 60 s, or the tool's `timeoutMs` |

Plugin status values: `loading`, `ready`, `degraded`, `failed`, `disabled`.

## Plugin Locations / Config

| Scope | Path / Setting |
|-------|----------------|
| Global | `~/.cline/plugins/` (installed sources under `_installed/{npm,git,remote,local}/`) |
| Project | `.cline/plugins/` in the repo root |
| SDK session config | `pluginPaths` (absolute module paths exporting an `AgentPlugin`), `extensions` (plugin objects) |
| CLI | `cline plugin install <source>` (file URL, npm, git, local path); `--cwd <path>` installs to `<path>/.cline/plugins`; `--force` replaces an existing install; `--json` |
| Package plugins | `package.json` `cline.plugins` array with `paths` and `capabilities` |
| Session plugin policy | `plugins` in session config, shaped like `toolPolicies`: `"*"` sets the default, named entries override per plugin (e.g. `{ "*": { enabled: false }, "code-review": { enabled: true } }`); plugins are enabled unless a policy turns them off |

Programmatic registration: `cline.start({ config: { extensions: [plugin] } })`, or pass absolute module paths through `config.pluginPaths`.

Applies to Cline SDK, CLI and Kanban (not the VSCode/JetBrains extensions).

## Hook Configuration Fields (Hook Policies) — legacy

Not documented on any current upstream page as of 2026-10-20 (superseded by the fixed timeouts and `hookErrorMode` above); retained from the 2026-06-30 snapshot.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | — | `"blocking"` (waits for result) or `"async"` (fire-and-forget) |
| `timeoutMs` | number | — | Maximum duration before timeout |
| `retries` | number | 0 | Retry count on failure |
| `retryDelayMs` | number | 1000 | Pause between retries (ms) |
| `failureMode` | string | `"fail_open"` | `"fail_open"` proceeds on failure; `"fail_closed"` blocks |
| `maxConcurrency` | number | 1 | Parallel hook executions |
| `queueLimit` | number | 100 | Max queued hooks before dropping |

Defaults are not documented on the current upstream page; the values above are retained from the 2026-06-30 snapshot.
Use `fail_closed` for policy-enforcement hooks where bypassing the hook is unsafe.

## Hook Events (15 total) — legacy

Not listed on current upstream pages as of 2026-10-20. Current upstream documents only the 7 `hooks` keys above; runtime events reach plugins via `onEvent`, with no event name list documented. Retained from the 2026-06-30 snapshot for backward compatibility of the `hook_event.py` mappings.

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
