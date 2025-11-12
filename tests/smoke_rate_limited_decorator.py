#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_rate_limited_decorator.py — v1.0
# ============================================================
from __future__ import annotations

import asyncio
import time

from queen.helpers.rate_limiter import rate_limited


def run_all():
    @rate_limited("decorator", n=1)
    async def fake_call(i):
        await asyncio.sleep(0.01)
        return f"ok-{i}"

    async def _test():
        t0 = time.perf_counter()
        results = await asyncio.gather(*[fake_call(i) for i in range(20)])
        elapsed = time.perf_counter() - t0
        assert all(r.startswith("ok-") for r in results)
        assert elapsed > 0, "decorator didn’t throttle correctly"
        print("✅ smoke_rate_limited_decorator: passed")

    asyncio.run(_test())

if __name__ == "__main__":
    run_all()
