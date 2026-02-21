from __future__ import annotations

import sys
import tests._path_setup  # noqa: F401
import types
import unittest
from contextlib import contextmanager

from otel_hooks.providers.factory import create_provider


@contextmanager
def _fake_provider_modules() -> None:
    backups = {
        name: sys.modules.get(name)
        for name in (
            "otel_hooks.providers.langfuse",
            "otel_hooks.providers.otlp",
            "otel_hooks.providers.datadog",
        )
    }

    langfuse_mod = types.ModuleType("otel_hooks.providers.langfuse")
    otlp_mod = types.ModuleType("otel_hooks.providers.otlp")
    datadog_mod = types.ModuleType("otel_hooks.providers.datadog")

    class LangfuseProvider:
        def __init__(self, public_key: str, secret_key: str, host: str) -> None:
            self.public_key = public_key
            self.secret_key = secret_key
            self.host = host

    class OTLPProvider:
        def __init__(self, endpoint: str, headers: dict[str, str] | None = None) -> None:
            self.endpoint = endpoint
            self.headers = headers or {}

    class DatadogProvider:
        def __init__(self, service: str = "otel-hooks", env: str | None = None) -> None:
            self.service = service
            self.env = env

    langfuse_mod.LangfuseProvider = LangfuseProvider
    otlp_mod.OTLPProvider = OTLPProvider
    datadog_mod.DatadogProvider = DatadogProvider

    sys.modules["otel_hooks.providers.langfuse"] = langfuse_mod
    sys.modules["otel_hooks.providers.otlp"] = otlp_mod
    sys.modules["otel_hooks.providers.datadog"] = datadog_mod

    try:
        yield
    finally:
        for name, value in backups.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


class ProviderFactoryTest(unittest.TestCase):
    def test_create_provider_table_driven(self) -> None:
        cases = [
            {
                "name": "unknown",
                "config": {},
                "expect_none": True,
            },
            {
                "name": "langfuse",
                "config": {"langfuse": {"public_key": "pk", "secret_key": "sk", "base_url": "https://lf"}},
                "expect_none": False,
                "assertions": lambda p: (
                    self.assertEqual(p.public_key, "pk"),
                    self.assertEqual(p.secret_key, "sk"),
                    self.assertEqual(p.host, "https://lf"),
                ),
            },
            {
                "name": "langfuse",
                "config": {"langfuse": {"public_key": "pk"}},
                "expect_none": True,
            },
            {
                "name": "otlp",
                "config": {"otlp": {"endpoint": "http://e", "headers": "a=1,b=2"}},
                "expect_none": False,
                "assertions": lambda p: (
                    self.assertEqual(p.endpoint, "http://e"),
                    self.assertEqual(p.headers, {"a": "1", "b": "2"}),
                ),
            },
            {
                "name": "otlp",
                "config": {"otlp": {}},
                "expect_none": True,
            },
            {
                "name": "datadog",
                "config": {"datadog": {"service": "svc", "env": "prod"}},
                "expect_none": False,
                "assertions": lambda p: (
                    self.assertEqual(p.service, "svc"),
                    self.assertEqual(p.env, "prod"),
                ),
            },
        ]

        with _fake_provider_modules():
            for i, case in enumerate(cases):
                with self.subTest(i=i, case=case["name"]):
                    provider = create_provider(case["name"], case["config"])
                    if case["expect_none"]:
                        self.assertIsNone(provider)
                        continue
                    self.assertIsNotNone(provider)
                    if "assertions" in case:
                        case["assertions"](provider)


if __name__ == "__main__":
    unittest.main()
