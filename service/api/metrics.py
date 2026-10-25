"""A few in-process runtime counters for the API (reset when the server restarts)."""

from __future__ import annotations

import threading
import time
from typing import Any


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._requests = 0
        self._responses = {"2xx": 0, "4xx": 0, "5xx": 0}
        self._latency_total_ms = 0.0
        self._latency_max_ms = 0.0
        self._counters = {"matches_run": 0, "live_sessions_started": 0, "internal_errors": 0}

    def observe_request(self, status: int, ms: float) -> None:
        bucket = "2xx" if status < 400 else "4xx" if status < 500 else "5xx"
        with self._lock:
            self._requests += 1
            self._responses[bucket] += 1
            self._latency_total_ms += ms
            self._latency_max_ms = max(self._latency_max_ms, ms)
            if status == 500:
                self._counters["internal_errors"] += 1

    def count(self, name: str) -> None:
        with self._lock:
            self._counters[name] += 1

    def snapshot(self, active_sessions: int) -> dict[str, Any]:
        with self._lock:
            n = self._requests
            return {
                "uptime_s": round(time.monotonic() - self._started, 1),
                "requests_total": n,
                "responses": dict(self._responses),
                "latency_ms": {"avg": round(self._latency_total_ms / n, 2) if n else 0.0,
                               "max": round(self._latency_max_ms, 2)},
                "matches_run": self._counters["matches_run"],
                "live_sessions": {"started": self._counters["live_sessions_started"],
                                  "active": active_sessions},
                "internal_errors": self._counters["internal_errors"],
            }
