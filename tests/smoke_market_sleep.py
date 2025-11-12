#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_market_sleep.py — v1.0 (compute_sleep_delay sanity)
# ============================================================
from __future__ import annotations

import datetime as dt

from queen.helpers.market import MARKET_TZ, compute_sleep_delay


def _assert(cond: bool, msg: str = "assertion failed"):
    if not cond:
        raise AssertionError(msg)

def test_compute_sleep_delay():
    # Fix a time: 10:07:13 IST
    now = dt.datetime(2025, 1, 1, 10, 7, 13, tzinfo=MARKET_TZ)
    # 5m candle
    delay0, nxt0 = compute_sleep_delay(now, 5, jitter_ratio=0.0)
    period = 5 * 60
    _assert(1.0 <= delay0 <= period - 1, f"delay out of bounds: {delay0}")
    _assert(nxt0 > now, "next wake should be in the future")

    # Deterministic jitter extremes
    d_neg, _ = compute_sleep_delay(now, 5, jitter_ratio=0.3, jitter_value=-1.0)
    d_pos, _ = compute_sleep_delay(now, 5, jitter_ratio=0.3, jitter_value=+1.0)
    _assert(1.0 <= d_neg <= period - 1, f"neg jitter bounds: {d_neg}")
    _assert(1.0 <= d_pos <= period - 1, f"pos jitter bounds: {d_pos}")

    # 1h candle
    delay1h, nxt1h = compute_sleep_delay(now, 60, jitter_ratio=0.0)
    _assert(1.0 <= delay1h <= 3600 - 1, "1h delay bounds")

    print("✅ smoke_market_sleep: passed")

if __name__ == "__main__":
    test_compute_sleep_delay()
