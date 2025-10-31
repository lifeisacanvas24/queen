#!/usr/bin/env python3
# queen/tests/smoke_fusion_all_latency.py
from __future__ import annotations

import time

import numpy as np
import polars as pl

# CMV (new path)
from queen.technicals.signals.fusion.cmv import compute_cmv

# LBX (forward-only canonical path; if not present, we skip gracefully)
try:
    from queen.technicals.signals.fusion.liquidity_breadth import (
        compute_liquidity_breadth_fusion as compute_lbx,
    )

    HAVE_LBX = True
except Exception:
    compute_lbx = None
    HAVE_LBX = False

# RScore (market regime)
from queen.technicals.signals.fusion.market_regime import compute_market_regime


def _mk_df(n: int = 2000) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    base = np.linspace(100, 120, n) + rng.normal(0, 1.0, n)
    high = base + rng.uniform(0.4, 1.5, n)
    low = base - rng.uniform(0.4, 1.5, n)
    close = base + rng.normal(0, 0.6, n)
    volume = rng.integers(1000, 6000, n)
    # minimal CMV prereqs so compute_cmv does not fill zeros
    rsi_14 = rng.uniform(20, 80, n)
    obv = np.cumsum(rng.integers(-500, 500, n))
    sps = rng.normal(0, 0.5, n)

    return pl.DataFrame(
        {
            "open": close - rng.normal(0, 0.3, n),
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "rsi_14": rsi_14,
            "obv": obv,
            "SPS": sps,
        }
    )


def _timeit(fn, *args, repeats=3, **kwargs) -> float:
    # warmup
    fn(*args, **kwargs)
    best = 1e9
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn(*args, **kwargs)
        dt = (time.perf_counter() - t0) * 1000.0
        best = min(best, dt)
    return best


def test_all_latency():
    df = _mk_df(2000)

    # --- CMV ---
    dt_cmv = _timeit(compute_cmv, df, repeats=3)
    print(f"⏱️ CMV latency (N≈2000): {dt_cmv:.2f} ms")
    assert dt_cmv < 30.0, f"CMV too slow: {dt_cmv:.2f} ms"

    # --- LBX (optional) ---
    if HAVE_LBX:

        def _lbx(df_: pl.DataFrame):
            # requires CMV+SPS + OHLCV (already present)
            return compute_lbx(df_, context="intraday_15m")

        dt_lbx = _timeit(_lbx, df, repeats=3)
        print(f"⏱️ LBX latency (N≈2000): {dt_lbx:.2f} ms")
        assert dt_lbx < 22.0, f"LBX too slow: {dt_lbx:.2f} ms"
    else:
        print("⚠️ LBX fusion not available — skipped.")

    # --- RScore ---
    dt_rs = _timeit(compute_market_regime, df, repeats=3)
    print(f"⏱️ RScore latency (N≈2000): {dt_rs:.2f} ms")
    assert dt_rs < 22.0, f"RScore too slow: {dt_rs:.2f} ms"


if __name__ == "__main__":
    test_all_latency()
