#!/usr/bin/env python3
from __future__ import annotations
import time, gc, math
import polars as pl
import numpy as np
from queen.technicals.signals.fusion.cmv import compute_cmv


def _mk(n=2000):
    idx = np.arange(n)
    base = 100 + 0.02 * idx + np.sin(idx * 0.03)
    open_ = base + 0.1 * np.sin(idx * 0.07)
    close = base + 0.2 * np.sin(idx * 0.05)
    high = np.maximum(open_, close) + 0.6
    low = np.minimum(open_, close) - 0.6
    vol = 1000 + (idx % 40) * 11
    rsi = 50 + 10 * np.sin(idx * 0.02)
    obv = np.cumsum(np.random.randint(-5, 5, n))
    sps = np.sin(idx * 0.015)
    return pl.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "rsi_14": rsi,
            "obv": obv,
            "SPS": sps,
        }
    )


def test_latency():
    df = _mk(2000)
    # Warm-up
    compute_cmv(df)
    runs, best = 5, 1e9
    for _ in range(runs):
        gc.disable()
        t0 = time.perf_counter()
        compute_cmv(df)
        dt = (time.perf_counter() - t0) * 1000
        gc.enable()
        best = min(best, dt)
    print(f"⏱️ CMV latency (N≈2000): {best:.2f} ms")
    assert best < 40.0, f"CMV too slow: {best:.2f} ms"


if __name__ == "__main__":
    test_latency()
    print("✅ smoke_fusion_latency: completed")
