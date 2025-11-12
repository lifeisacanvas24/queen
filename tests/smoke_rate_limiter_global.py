#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_rate_limiter_global.py — v1.0
# ============================================================
from __future__ import annotations

import asyncio

from queen.helpers.rate_limiter import get_pool


def run_all():
    async def _test():
        pool = get_pool()
        await pool.acquire("demo", 2)
        pool.try_acquire("demo")
        await pool.set_rate("demo", 8)
        stats = pool.stats()
        assert "demo" in stats
        print("✅ smoke_rate_limiter_global: passed")

    asyncio.run(_test())

if __name__ == "__main__":
    run_all()
