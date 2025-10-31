from __future__ import annotations

import os
import time
import numpy as np
import polars as pl

from queen.technicals.signals.fusion.cmv import compute_cmv
from queen.helpers.logger import log  # ensures logger init message is printed


def _build_df(n: int = 2000) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    base = np.linspace(100, 110, n) + rng.normal(0, 0.6, n)
    high = base + rng.uniform(0.3, 1.2, n)
    low = base - rng.uniform(0.3, 1.2, n)
    close = base + rng.normal(0, 0.4, n)
    volume = rng.integers(1000, 7000, n)

    # inputs CMV expects (safe defaults if absent)
    rsi_14 = rng.uniform(30, 70, n)
    obv = np.cumsum(rng.integers(-500, 500, n))
    sps = np.clip(rng.normal(0, 0.5, n), -1, 1)

    return pl.DataFrame(
        {
            "open": base,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "rsi_14": rsi_14,
            "obv": obv,
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

    # warm-up
    _ = compute_cmv(df)

    dt_ms = _best_of_3(lambda: compute_cmv(df))

    cap_ms = float(os.getenv("CMV_CAP_MS", "25.0"))
    print(f"⏱️ CMV latency (N≈2000): {dt_ms:.2f} ms")
    assert dt_ms < cap_ms, f"CMV too slow: {dt_ms:.2f} ms"


if __name__ == "__main__":
    test_latency()
    print("✅ smoke_cmv_latency: completed")
