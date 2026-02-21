"""Provider factory."""

from __future__ import annotations


from typing import Any


def create_provider(name: str, config: dict[str, Any]):
    """Create a provider instance from merged config. Returns None on failure."""
    pcfg = config.get(name, {})

    if name == "langfuse":
        try:
            from otel_hooks.providers.langfuse import LangfuseProvider
        except ImportError:
            return None
        public_key = pcfg.get("public_key")
        secret_key = pcfg.get("secret_key")
        host = pcfg.get("base_url", "https://cloud.langfuse.com")
        if not public_key or not secret_key:
            return None
        try:
            return LangfuseProvider(public_key=public_key, secret_key=secret_key, host=host)
        except Exception:
            return None

    if name == "otlp":
        try:
            from otel_hooks.providers.otlp import OTLPProvider
        except ImportError:
            return None
        endpoint = pcfg.get("endpoint", "")
        if not endpoint:
            return None
        headers_raw = pcfg.get("headers", "")
        headers: dict[str, str] = {}
        if headers_raw:
            for pair in headers_raw.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    headers[k.strip()] = v.strip()
        try:
            return OTLPProvider(endpoint=endpoint, headers=headers)
        except Exception:
            return None

    if name == "datadog":
        try:
            from otel_hooks.providers.datadog import DatadogProvider
        except ImportError:
            return None
        service = pcfg.get("service", "otel-hooks")
        env = pcfg.get("env")
        try:
            return DatadogProvider(service=service, env=env)
        except Exception:
            return None

    return None
