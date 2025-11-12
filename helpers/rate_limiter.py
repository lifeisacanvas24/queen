#!/usr/bin/env python3
# ============================================================
# quant/utils/rate_limiter.py — v2.0 (Async Token Bucket + Settings Diagnostics)
# ============================================================
"""Quant-Core — Async Token Bucket Rate Limiter.

✅ Async-safe continuous token refill
✅ Settings-integrated defaults (FETCH.MAX_REQ_PER_SEC)
✅ Structured diagnostics via Queen logger
✅ Desynchronized jitter to prevent bursts
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Optional

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS


def _get(d: dict, *keys, default=None):
    for k in keys:
        if k in d: return d[k]
        if isinstance(k, str):
            if k.lower() in d: return d[k.lower()]
            if k.upper() in d: return d[k.upper()]
    return default

DEFAULT_QPS = float(_get(SETTINGS.FETCH, "max_req_per_sec", "MAX_REQ_PER_SEC", default=50))
DIAG_ENABLED = bool(_get(SETTINGS.DIAGNOSTICS, "enabled", "ENABLED", default=True))


class AsyncTokenBucket:
    """Asynchronous continuous-time token bucket with optional diagnostics."""

    def __init__(
        self,
        rate_per_second: Optional[float] = None,
        name: str = "generic",
        diag: Optional[bool] = None,
    ):
        self.rate = float(rate_per_second or DEFAULT_QPS)
        self.tokens = self.rate
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()
        self.name = name
        self.diag = DIAG_ENABLED if diag is None else bool(diag)
        self._last_log = 0.0

    async def acquire(self) -> None:
        """Acquire one token, waiting if necessary."""
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            refill = elapsed * self.rate

            if refill > 0:
                self.tokens = min(self.rate, self.tokens + refill)
                self.last_refill = now

            while self.tokens < 1:
                sleep_for = max(0.001, (1 - self.tokens) / self.rate)
                await asyncio.sleep(sleep_for)
                now = time.monotonic()
                elapsed = now - self.last_refill
                refill = elapsed * self.rate
                if refill > 0:
                    self.tokens = min(self.rate, self.tokens + refill)
                    self.last_refill = now

            self.tokens -= 1.0

            if self.diag and now - self._last_log > 1.0:
                self._last_log = now
                log.info(
                    f"[RateLimiter:{self.name}] tokens={self.tokens:.2f}/{self.rate}"
                )

        # slight jitter to desync bursts
        await asyncio.sleep(random.uniform(0.002, 0.01))


# ------------------------------------------------------------
# 🧪 CLI Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":

    async def _test():
        rl = AsyncTokenBucket(rate_per_second=10, name="demo")
        for i in range(25):
            await rl.acquire()
            print(f"✅ Request {i+1}")

    asyncio.run(_test())
