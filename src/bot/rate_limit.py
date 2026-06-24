"""In-memory per-chat daily rate limiter.

Guards the LLM budget: each chat_id gets N LLM calls per day. FAQ-router answers
are free and must NOT go through this. Counts reset at UTC midnight. State is
in-memory (fine for a single-process bot); swap for Redis if you scale out.
"""
from __future__ import annotations

from datetime import datetime, timezone


class DailyRateLimiter:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._counts: dict[tuple[int, str], int] = {}

    @staticmethod
    def _day() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def remaining(self, chat_id: int) -> int:
        used = self._counts.get((chat_id, self._day()), 0)
        return max(0, self.limit - used)

    def allow(self, chat_id: int) -> bool:
        """Consume one unit if available. Returns True if the call may proceed."""
        key = (chat_id, self._day())
        used = self._counts.get(key, 0)
        if used >= self.limit:
            return False
        self._counts[key] = used + 1
        return True
