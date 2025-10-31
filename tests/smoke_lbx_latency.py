from __future__ import annotations

import os
import time
import numpy as np
import polars as pl

from queen.technicals.signals.fusion.cmv import compute_cmv
from queen.technicals.signals.fusion.liquidity_breadth import (
    compute_liquidity_breadth_fusion,
)
from queen.helpers.logger import log


def _build_df(n: int = 2000) -> pl.DataFrame:
    rng = np.random.default_rng(123)
    base = np.linspace(100, 115, n) + rng.normal(0, 0.7, n)
    high = base + rng.uniform(0.4, 1.6, n)
    low = base - rng.uniform(0.4, 1.6, n)
    close = base + rng.normal(0, 0.5, n)
    volume = rng.integers(1000, 7000, n)

    sps = np.clip(rng.normal(0, 0.5, n), -1, 1)  # setup pressure proxy

    return pl.DataFrame(
        {
            "open": base,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "SPS": sps,
        }
    )


def _best_of_3(fn):
    best = float("inf")
    for _ in range(3):
        t0 = time.perf_counter()
        fn()
        dt = (time.perf_counter() - t0) * 1000.0
        best = min(best, dt)
    return best


def test_latency():
    df = _build_df()

    # LBX requires CMV column → compute once & attach
    df = compute_cmv(df)

    # warm-up
    _ = compute_liquidity_breadth_fusion(df)

    dt_ms = _best_of_3(lambda: compute_liquidity_breadth_fusion(df))

    cap_ms = float(os.getenv("LBX_CAP_MS", "30.0"))
    print(f"⏱️ LBX latency (N≈2000): {dt_ms:.2f} ms")
    assert dt_ms < cap_ms, f"LBX too slow: {dt_ms:.2f} ms"


if __name__ == "__main__":
    test_latency()
    print("✅ smoke_lbx_latency: completed")
