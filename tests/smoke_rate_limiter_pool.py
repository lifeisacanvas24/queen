#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_rate_limiter_pool.py — v1.0
# ============================================================
from __future__ import annotations

import asyncio
import time

from queen.helpers.rate_limiter import RateLimiterPool


def run_all():
    async def _test():
        pool = RateLimiterPool(per_key={"fast": 30, "slow": 5}, default_qps=10, diag=False)

        # Non-blocking path should succeed a few times, then start failing
        ok1 = pool.try_acquire("fast")
        ok2 = pool.try_acquire("fast")
        _ = pool.try_acquire("fast")  # may be True/False; non-deterministic by design

        # Blocking semantics for both keys
        t0 = time.perf_counter()
        # 20 ops on 'fast' @30 qps → should be sub-1s
        for _ in range(20):
            await pool.acquire("fast")
        fast_elapsed = time.perf_counter() - t0

        t1 = time.perf_counter()
        # 10 ops on 'slow' @5 qps → ~2s
        for _ in range(10):
            await pool.acquire("slow")
        slow_elapsed = time.perf_counter() - t1

        assert fast_elapsed < 1.5, f"fast limiter too slow: {fast_elapsed:.2f}s"
        assert slow_elapsed < 3.5, f"slow limiter too slow: {slow_elapsed:.2f}s"

        # Dynamic re-rate
        await pool.set_rate("slow", 12)
        t2 = time.perf_counter()
        for _ in range(12):
            await pool.acquire("slow")
        reconfig_elapsed = time.perf_counter() - t2
        assert reconfig_elapsed < 2.0, f"re-rated limiter too slow: {reconfig_elapsed:.2f}s"

        print("✅ smoke_rate_limiter_pool: passed")

    asyncio.run(_test())

if __name__ == "__main__":
    run_all()
