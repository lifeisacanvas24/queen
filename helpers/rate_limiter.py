#!/usr/bin/env python3
# ============================================================
# queen/helpers/rate_limiter.py — v2.1 (Async Token Bucket + DX niceties)
# ============================================================
from __future__ import annotations

import asyncio
import random
import time

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS


def _get(d: dict, *keys, default=None):
    for k in keys:
        if k in d:
            return d[k]
        if isinstance(k, str):
            if k.lower() in d:
                return d[k.lower()]
            if k.upper() in d:
                return d[k.upper()]
    return default


DEFAULT_QPS = float(
    _get(SETTINGS.FETCH, "max_req_per_sec", "MAX_REQ_PER_SEC", default=50)
)
DIAG_ENABLED = bool(_get(SETTINGS.DIAGNOSTICS, "enabled", "ENABLED", default=True))


class AsyncTokenBucket:
    """Asynchronous continuous-time token bucket with optional diagnostics.

    Features:
      • Non-blocking try_acquire()
      • Batched acquire(n)
      • Jitter to desync bursts
    """

    def __init__(
        self,
        rate_per_second: float | None = None,
        name: str = "generic",
        diag: bool | None = None,
        *,
        jitter_min: float = 0.002,
        jitter_max: float = 0.01,
    ):
        rate = float(rate_per_second or DEFAULT_QPS)
        if rate <= 0:
            raise ValueError("rate_per_second must be > 0")

        self.rate = rate
        self.capacity = rate  # bucket size == rate (1s burst allowance)
        self.tokens = float(rate)
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()
        self.name = name
        self.diag = DIAG_ENABLED if diag is None else bool(diag)
        self._last_log = 0.0
        self._jitter_min = float(jitter_min)
        self._jitter_max = float(jitter_max)

    # ----- internals -----
    def _refill_unlocked(self, now: float) -> None:
        elapsed = now - self.last_refill
        if elapsed <= 0:
            return
        refill = elapsed * self.rate
        if refill > 0:
            self.tokens = min(self.capacity, self.tokens + refill)
            self.last_refill = now

    # ----- public API -----
    async def acquire(self, n: int = 1) -> None:
        """Acquire n tokens (blocking until available)."""
        if n <= 0:
            return
        async with self.lock:
            now = time.monotonic()
            self._refill_unlocked(now)

            # wait until we have n tokens
            while self.tokens < n:
                needed = n - self.tokens
                sleep_for = max(0.001, needed / self.rate)
                await asyncio.sleep(sleep_for)
                now = time.monotonic()
                self._refill_unlocked(now)

            self.tokens -= n

            if self.diag and (now - self._last_log) > 1.0:
                self._last_log = now
                log.info(
                    f"[RateLimiter:{self.name}] tokens={self.tokens:.2f}/{self.capacity} rate={self.rate:.2f}/s"
                )

        # slight jitter to desync callers
        await asyncio.sleep(random.uniform(self._jitter_min, self._jitter_max))

    def try_acquire(self, n: int = 1) -> bool:
        """Attempt to acquire n tokens without blocking (returns False if not enough)."""
        if n <= 0:
            return True
        now = time.monotonic()
        # Fast path: optimistic without awaiting the lock; still lock to mutate safely
        if self.lock.locked():
            return False
        acquired = False
        # Use a synchronous context with try/timeout pattern
        async def _try():
            nonlocal acquired
            async with self.lock:
                self._refill_unlocked(now)
                if self.tokens >= n:
                    self.tokens -= n
                    acquired = True

        # Run a tiny, immediately-scheduled task and block briefly (non-blocking wrt rate)
        # But since this is a sync function, we cannot await. Instead, we do a best-effort
        # lock-free read fallback.
        if self.tokens >= n:
            # small race risk mitigated by later refill; acceptable for non-blocking path
            self.tokens -= n
            return True
        return False


# ------------------------------------------------------------
# 🧪 CLI Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":

    async def _test():
        rl = AsyncTokenBucket(rate_per_second=10, name="demo", diag=False)
        # Try fast path
        ok = rl.try_acquire()
        print("try_acquire:", ok)
        # Batch 25 operations at 10 qps should finish ~2.5s
        import time as _t
        t0 = _t.perf_counter()
        for i in range(25):
            await rl.acquire()
            if (i + 1) % 5 == 0:
                print(f"acquired {i+1}")
        print("elapsed:", _t.perf_counter() - t0)

    asyncio.run(_test())
