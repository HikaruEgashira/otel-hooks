# OpenCode Plugins Specification

> Source: https://opencode.ai/docs/plugins/
> Snapshot: 2026-04-04

## Config Location

| Scope | Path |
|-------|------|
| Global config | `~/.config/opencode/opencode.json` |
| Global plugins | `~/.config/opencode/plugins/` |
| Project config | `opencode.json` |
| Project plugins | `.opencode/plugins/` |

## Config Schema

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["package-name", "@scoped/package", "local-plugin-name"]
}
```

## Plugin Module Structure

```javascript
export const PluginName = async (context) => {
  return { /* hooks object */ }
}
```

### Context Object

- `project` — current project information
- `directory` — current working directory
- `worktree` — git worktree path
- `client` — OpenCode SDK client
- `$` — Bun shell API

## Available Events

### Command
- `command.executed`

### File
- `file.edited`
- `file.watcher.updated`

### Installation
- `installation.updated`

### LSP
- `lsp.client.diagnostics`
- `lsp.updated`

### Message
- `message.part.removed`
- `message.part.updated`
- `message.removed`
- `message.updated`

### Permission
- `permission.asked`
- `permission.replied`

### Server
- `server.connected`

### Session
- `session.created`
- `session.compacted`
- `session.deleted`
- `session.diff`
- `session.error`
- `session.idle`
- `session.status`
- `session.updated`

### Todo
- `todo.updated`

### Shell
- `shell.env` — signature: `async (input, output)`

### Tool
- `tool.execute.before` — signature: `async (input, output)`
- `tool.execute.after`

### TUI
- `tui.prompt.append`
- `tui.command.execute`
- `tui.toast.show`

### Experimental
- `experimental.session.compacting` — signature: `async (input, output)`

## Hook Signatures

Standard: `async ({ event }) => {}`

Input/output: `async (input, output) => {}`

Compaction: `output.context.push(string)` or `output.prompt = string`

## Custom Tool Definition

```javascript
import { tool } from "@opencode-ai/plugin"

tool({
  description: "string",
  args: { /* Zod schema */ },
  async execute(args, context) { /* ... */ }
})
```

## Installation Behavior

- npm plugins cached at `~/.cache/opencode/node_modules/`
- Local plugins loaded directly
- External deps require `.opencode/package.json`

## Load Order

1. Global config → 2. Project config → 3. Global plugins → 4. Project plugins

Duplicate npm packages (same name/version) load once.
