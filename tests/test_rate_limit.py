"""Tests for the daily rate limiter.

    uv run pytest
    python -m tests.test_rate_limit
"""
from __future__ import annotations

from src.bot.rate_limit import DailyRateLimiter


def test_allows_up_to_limit_then_blocks():
    rl = DailyRateLimiter(limit=3)
    assert [rl.allow(42) for _ in range(3)] == [True, True, True]
    assert rl.allow(42) is False  # 4th blocked
    assert rl.remaining(42) == 0


def test_per_chat_isolation():
    rl = DailyRateLimiter(limit=1)
    assert rl.allow(1) is True
    assert rl.allow(2) is True       # different chat, own budget
    assert rl.allow(1) is False


def test_remaining_counts_down():
    rl = DailyRateLimiter(limit=5)
    assert rl.remaining(7) == 5
    rl.allow(7)
    rl.allow(7)
    assert rl.remaining(7) == 3


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
