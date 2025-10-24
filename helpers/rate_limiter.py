#!/usr/bin/env python3
# ============================================================
# quant/utils/rate_limiter.py — v1.5 (Async Token Bucket + Hybrid Diagnostics)
# ============================================================
"""Quant-Core — Async Token Bucket Rate Limiter (Hybrid + Structured Diagnostics).

Highlights:
    ✅ Async-safe continuous token refill
    ✅ Config-proxy integrated (fetches default QPS if needed)
    ✅ Structured diagnostic logging (optional)
    ✅ Desynchronized jitter to prevent bursts
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Optional

from quant.utils.config_proxy import cfg_bool, cfg_get
from quant.utils.logs import safe_log_init

# Initialize a shared logger
logger = safe_log_init("RateLimiter")

# ============================================================
# ⚙️ Config Defaults (Hybrid-Safe)
# ============================================================
DEFAULT_QPS = cfg_get("fetch.max_req_per_sec", 50)
DIAG_ENABLED = cfg_bool("diagnostics.enabled", True)


# ============================================================
# 🧩 Core Class
# ============================================================
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
        self.diag = DIAG_ENABLED if diag is None else diag
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

            # Wait until enough tokens
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

            # Optional structured diagnostics
            if self.diag and now - self._last_log > 1.0:
                self._last_log = now
                logger.info(
                    f"[RateLimiter:{self.name}] tokens={self.tokens:.2f}/{self.rate}"
                )

        # Add slight random jitter to desync bursts
        await asyncio.sleep(random.uniform(0.002, 0.01))


# ============================================================
# 🧪 CLI Self-Test
# ============================================================
if __name__ == "__main__":

    async def _test():
        rl = AsyncTokenBucket(rate_per_second=10, name="demo")
        for i in range(25):
            await rl.acquire()
            print(f"✅ Request {i+1}")

    import asyncio

    asyncio.run(_test())
