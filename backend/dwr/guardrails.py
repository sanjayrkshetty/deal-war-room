"""Public-demo guardrails (`dwr/guardrails.py`).

No-auth deployment means strangers hit your Groq quota. These are the seatbelts:
in-memory, single-process, reset on restart — sized for a free-tier showcase,
not for production multi-tenancy.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class BudgetExceeded(RuntimeError):
    pass


class TokenBudget:
    """UTC-daily cumulative token counter backed by real API usage figures."""

    def __init__(self, daily_budget: int) -> None:
        self._budget = max(0, daily_budget)
        self._lock = threading.Lock()
        self._day: str | None = None
        self._used = 0

    def _roll_if_needed(self) -> None:
        day = _utc_day()
        if self._day != day:
            self._day = day
            self._used = 0

    def add(self, tokens: int) -> None:
        with self._lock:
            self._roll_if_needed()
            self._used += max(0, tokens)

    def used(self) -> int:
        with self._lock:
            self._roll_if_needed()
            return self._used

    def remaining(self) -> int:
        return max(0, self._budget - self.used())

    def allow_minimum(self, minimum: int) -> bool:
        return self.remaining() >= minimum

    def snapshot(self) -> dict:
        return {
            "daily_budget": self._budget,
            "tokens_used_today": self.used(),
            "tokens_remaining_today": self.remaining(),
            "resets_at": "00:00 UTC",
        }


class RateLimiter:
    """Sliding-window per-key limiter."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._events[key]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.max_events:
                return False
            bucket.append(now)
            return True


MIN_ANALYSIS_TOKENS = 20_000

_token_budget = TokenBudget(int(os.environ.get("DWR_DAILY_TOKEN_BUDGET", "400000")))
analysis_limiter = RateLimiter(
    max_events=int(os.environ.get("DWR_MAX_ANALYSES_PER_HOUR", "15")), window_seconds=3600
)
general_limiter = RateLimiter(
    max_events=int(os.environ.get("DWR_MAX_REQUESTS_PER_MINUTE", "120")), window_seconds=60
)


def token_budget() -> TokenBudget:
    return _token_budget
