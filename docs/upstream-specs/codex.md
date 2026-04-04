# Codex CLI Hooks Specification

> Source: https://developers.openai.com/codex/config-reference
> Snapshot: 2026-04-04

## Config Location

| Scope | Path |
|-------|------|
| Global | `~/.codex/config.toml` |

## Hooks Feature Status

**Under development; disabled by default.**

```toml
[features]
codex_hooks = true  # Enable lifecycle hooks loaded from hooks.json
```

## Known Details

- Hooks loaded from `hooks.json` (location unspecified beyond filename)
- No documented event names, payload schemas, or constraints
- Feature flag required: `features.codex_hooks = true`

## otel-hooks Integration

otel-hooks uses Codex's native OTEL exporter configuration instead of hooks:

```toml
[otel]
# OTLP exporter settings configured directly in config.toml
```

Supports `otlp-http` and `otlp-grpc` exporters.

## TODO

- [ ] Monitor for hooks.json schema documentation
- [ ] Track feature graduation from experimental
