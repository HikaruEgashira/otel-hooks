"""Lightweight Datadog Agent trace transport (stdlib only).

Sends spans to the local Datadog Agent via ``PUT /v0.3/traces`` using only
the Python standard library — no ``ddtrace`` dependency required.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import random
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_current_span: ContextVar[Span | None] = ContextVar("_current_span", default=None)


def _rand64() -> int:
    return random.getrandbits(63)


def _now_ns() -> int:
    return int(time.time() * 1_000_000_000)


@dataclass
class Span:
    trace_id: int
    span_id: int
    parent_id: int
    name: str
    resource: str
    service: str
    type: str
    start: int
    duration: int = 0
    meta: dict[str, str] = field(default_factory=dict)

    def set_tags(self, tags: dict[str, str]) -> None:
        self.meta.update(tags)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "resource": self.resource,
            "service": self.service,
            "type": self.type,
            "start": self.start,
            "duration": self.duration,
            "meta": self.meta,
        }


class Tracer:
    def __init__(self, service: str = "otel-hooks", env: str | None = None) -> None:
        self.service = service
        self._global_tags: dict[str, str] = {}
        if env:
            self._global_tags["env"] = env
        self._buffer: list[Span] = []
        self._lock = threading.Lock()
        self._host = os.environ.get("DD_AGENT_HOST", "localhost")
        self._port = int(os.environ.get("DD_TRACE_AGENT_PORT", "8126"))

    def set_tags(self, tags: dict[str, str]) -> None:
        self._global_tags.update(tags)

    @contextmanager
    def trace(self, name: str, resource: str, service: str, span_type: str):
        parent = _current_span.get(None)
        trace_id = parent.trace_id if parent else _rand64()
        span = Span(
            trace_id=trace_id,
            span_id=_rand64(),
            parent_id=parent.span_id if parent else 0,
            name=name,
            resource=resource,
            service=service,
            type=span_type,
            start=_now_ns(),
            meta=dict(self._global_tags),
        )
        with self._lock:
            self._buffer.append(span)
        token = _current_span.set(span)
        try:
            yield span
        finally:
            span.duration = _now_ns() - span.start
            _current_span.reset(token)

    def flush(self) -> None:
        with self._lock:
            spans = self._buffer[:]
            self._buffer.clear()
        if not spans:
            return
        traces: dict[int, list[dict]] = {}
        for s in spans:
            traces.setdefault(s.trace_id, []).append(s.to_dict())
        body = json.dumps(list(traces.values()))
        try:
            conn = http.client.HTTPConnection(self._host, self._port, timeout=2)
            conn.request(
                "PUT", "/v0.3/traces", body, {"Content-Type": "application/json"}
            )
            resp = conn.getresponse()
            resp.read()
            conn.close()
        except (ConnectionRefusedError, OSError) as exc:
            logger.warning(
                "Failed to send traces to Datadog Agent at %s:%s: %s",
                self._host,
                self._port,
                exc,
            )

    def shutdown(self) -> None:
        self.flush()
