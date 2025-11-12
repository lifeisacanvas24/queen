#!/usr/bin/env python3
# ============================================================
# queen/helpers/rate_limiter.py — v2.5 (Async Token Bucket + Pool + Singleton + Decorator)
# ============================================================
from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS


# ------------------------------------------------------------
# ⚙️ Config helpers
# ------------------------------------------------------------
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


DEFAULT_QPS = float(_get(SETTINGS.FETCH, "max_req_per_sec", "MAX_REQ_PER_SEC", default=50))
DIAG_ENABLED = bool(_get(SETTINGS.DIAGNOSTICS, "enabled", "ENABLED", default=True))


# ------------------------------------------------------------
# 🪣 AsyncTokenBucket
# ------------------------------------------------------------
class AsyncTokenBucket:
    """Asynchronous continuous-time token bucket with diagnostics + jitter."""

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
        self.capacity = rate  # burst capacity per second
        self.tokens = float(rate)
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()
        self.name = name
        self.diag = DIAG_ENABLED if diag is None else bool(diag)
        self._last_log = 0.0
        self._jitter_min = float(jitter_min)
        self._jitter_max = float(jitter_max)

    def _refill_unlocked(self, now: float) -> None:
        elapsed = now - self.last_refill
        if elapsed <= 0:
            return
        refill = elapsed * self.rate
        if refill > 0:
            self.tokens = min(self.capacity, self.tokens + refill)
            self.last_refill = now

    async def acquire(self, n: int = 1) -> None:
        """Acquire n tokens (blocking until available)."""
        if n <= 0:
            return
        async with self.lock:
            now = time.monotonic()
            self._refill_unlocked(now)

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

        await asyncio.sleep(random.uniform(self._jitter_min, self._jitter_max))

    def try_acquire(self, n: int = 1) -> bool:
        """Attempt to acquire n tokens without blocking (returns False if not enough)."""
        if n <= 0:
            return True
        now = time.monotonic()
        self._refill_unlocked(now)
        if self.tokens >= n and not self.lock.locked():
            self.tokens -= n
            return True
        return False

    async def set_rate(self, rate_per_second: float) -> None:
        """Dynamically adjust rate and capacity safely."""
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be > 0")
        async with self.lock:
            now = time.monotonic()
            self._refill_unlocked(now)
            self.rate = float(rate_per_second)
            self.capacity = float(rate_per_second)
            self.tokens = min(self.tokens, self.capacity)
            self.last_refill = now


# ------------------------------------------------------------
# 🧩 RateLimiterPool
# ------------------------------------------------------------
class RateLimiterPool:
    """Pool of named AsyncTokenBuckets (per-endpoint/service)."""

    def __init__(
        self,
        default_qps: float | None = None,
        *,
        per_key: dict[str, float] | None = None,
        diag: bool | None = None,
    ):
        self._default_qps = float(default_qps or DEFAULT_QPS)
        if self._default_qps <= 0:
            raise ValueError("default_qps must be > 0")

        # seed from settings.FETCH.rate_limits if present
        rl_cfg = _get(SETTINGS.FETCH, "rate_limits", "RATE_LIMITS", default={}) or {}
        seeded: dict[str, float] = {}
        for k, v in rl_cfg.items():
            if isinstance(v, (int, float)) and v > 0:
                seeded[str(k)] = float(v)

        if per_key:
            for k, v in per_key.items():
                if isinstance(v, (int, float)) and v > 0:
                    seeded[str(k)] = float(v)

        self._diag = DIAG_ENABLED if diag is None else bool(diag)
        self._limiters: dict[str, AsyncTokenBucket] = {}
        self._dict_lock = asyncio.Lock()

        for key, qps in seeded.items():
            self._limiters[key] = AsyncTokenBucket(qps, name=key, diag=self._diag)

    async def _ensure(self, key: str) -> AsyncTokenBucket:
        if key in self._limiters:
            return self._limiters[key]
        async with self._dict_lock:
            if key not in self._limiters:
                self._limiters[key] = AsyncTokenBucket(
                    self._default_qps, name=key, diag=self._diag
                )
            return self._limiters[key]

    async def acquire(self, key: str, n: int = 1) -> None:
        limiter = await self._ensure(key)
        await limiter.acquire(n)

    async def set_rate(self, key: str, rate_per_second: float) -> None:
        limiter = await self._ensure(key)
        await limiter.set_rate(rate_per_second)

    def try_acquire(self, key: str, n: int = 1) -> bool:
        limiter = self._limiters.get(key)
        if not limiter:
            limiter = self._limiters.setdefault(
                key, AsyncTokenBucket(self._default_qps, name=key, diag=self._diag)
            )
        return limiter.try_acquire(n)

    def get(self, key: str) -> AsyncTokenBucket:
        return self._limiters.setdefault(
            key, AsyncTokenBucket(self._default_qps, name=key, diag=self._diag)
        )

    def stats(self) -> dict[str, dict[str, float]]:
        return {
            k: {"rate": v.rate, "tokens": float(v.tokens)} for k, v in self._limiters.items()
        }

    def keys(self) -> list[str]:
        return list(self._limiters.keys())


# ------------------------------------------------------------
# 🧠 Lazy Singleton Pool Accessor
# ------------------------------------------------------------
_global_pool: RateLimiterPool | None = None

def get_pool() -> RateLimiterPool:
    """Return the global shared RateLimiterPool instance (lazy singleton)."""
    global _global_pool
    if _global_pool is None:
        _global_pool = RateLimiterPool()
        log.info("[RateLimiter] Global pool initialized.")
    return _global_pool


# ------------------------------------------------------------
# ✨ rate_limited() decorator
# ------------------------------------------------------------
def rate_limited(key: str, n: int = 1):
    """Async decorator that rate-limits calls using the global pool.

    Example:
        @rate_limited("intraday")
        async def fetch_intraday(symbol):
            ...

    """
    def decorator(fn: Callable[..., Awaitable[Any]]):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            pool = get_pool()
            await pool.acquire(key, n)
            return await fn(*args, **kwargs)
        return wrapper
    return decorator

# ------------------------------------------------------------
# 🧵 Context-manager sugar
# ------------------------------------------------------------
@asynccontextmanager
async def with_pool(key: str, n: int = 1):
    """Throttle an arbitrary async block using the global pool.

    Example:
        async with with_pool("intraday"):
            await broker_call()

    """
    pool = get_pool()
    await pool.acquire(key, n)
    try:
        yield
    finally:
        # tokens are consumed on acquire; nothing to release
        pass

# alias for ultra-short syntax
def limiter(key: str, n: int = 1):
    """Alias of with_pool() so you can write: `async with limiter("intraday"):`"""
    return with_pool(key, n)

__all__ = [
    "AsyncTokenBucket",
    "RateLimiterPool",
    "get_pool",
    "rate_limited",
    "with_pool",
    "limiter",
]

# ------------------------------------------------------------
# 🧪 CLI Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    @rate_limited("demo")
    async def demo_task(i):
        print(f"executing {i}")

    async def _demo():
        tasks = [demo_task(i) for i in range(10)]
        await asyncio.gather(*tasks)
        print("stats:", get_pool().stats())

    asyncio.run(_demo())
