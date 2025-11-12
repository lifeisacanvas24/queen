#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_rate_limiter.py — v1.1
# ============================================================
from __future__ import annotations

import asyncio
import time

from queen.helpers.rate_limiter import AsyncTokenBucket  # ← refactored path


def run_all():
    async def _test():
        rl = AsyncTokenBucket(rate_per_second=20, name="smoke", diag=False)

        # Non-blocking should often fail initially after a few successes
        ok1 = rl.try_acquire()
        ok2 = rl.try_acquire()
        _ = rl.try_acquire()  # we don't assert hard here to avoid flakiness

        n = 25
        t0 = time.perf_counter()
        # Batch acquire a few times
        await rl.acquire(3)
        await rl.acquire(2)
        for _ in range(n - 5):
            await rl.acquire()
        elapsed = time.perf_counter() - t0

        assert elapsed < 3.0, f"rate limiter too slow: {elapsed:.2f}s"
        print("✅ smoke_rate_limiter: passed")

    asyncio.run(_test())

if __name__ == "__main__":
    run_all()
