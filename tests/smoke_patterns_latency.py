#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_patterns_latency.py — tiny perf guard
# ============================================================
from __future__ import annotations

import math
import time

import polars as pl
from queen.technicals.patterns import core as pc
from queen.technicals.patterns.composite import detect_composite_patterns


def _mk(n: int = 2000) -> pl.DataFrame:
    close = [100 + 2.0 * math.cos(i * 0.04) for i in range(n)]
    open_ = [close[i] - 0.2 * math.sin(i * 0.07) for i in range(n)]
    high = [max(open_[i], close[i]) + 0.4 for i in range(n)]
    low = [min(open_[i], close[i]) - 0.4 for i in range(n)]
    vol = [1500 + (i % 30) * 5 for i in range(n)]
    return pl.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol}
    )


def test_latency():
    df = _mk()
    t0 = time.time()
    # core
    for name, fn in pc.EXPORTS.items():
        if name != "required_lookback":
            _ = fn(df)
    # composite
    _ = detect_composite_patterns(df)
    dt = (time.time() - t0) * 1000.0
    print(f"⏱️ patterns latency (N≈2000): {dt:.2f} ms")


if __name__ == "__main__":
    test_latency()
