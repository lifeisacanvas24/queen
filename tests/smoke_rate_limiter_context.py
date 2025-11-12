#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_rate_limiter_context.py — v1.0
# ============================================================
from __future__ import annotations

import asyncio
import time

from queen.helpers.rate_limiter import limiter


def run_all():
    async def _work(i: int):
        async with limiter("ctx-smoke"):
            await asyncio.sleep(0.005)
            return f"ok-{i}"

    async def _test():
        t0 = time.perf_counter()
        out = await asyncio.gather(*[_work(i) for i in range(25)])
        elapsed = time.perf_counter() - t0
        assert all(v.startswith("ok-") for v in out)
        assert elapsed >= 0   # just a sanity timing check
        print("✅ smoke_rate_limiter_context: passed")

    asyncio.run(_test())

if __name__ == "__main__":
    run_all()
