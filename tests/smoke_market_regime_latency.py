from __future__ import annotations

import os
import time
import numpy as np
import polars as pl

from queen.technicals.signals.fusion.market_regime import compute_market_regime
from queen.helpers.logger import log


def _build_df(n: int = 2000) -> pl.DataFrame:
    rng = np.random.default_rng(7)
    base = np.linspace(100, 120, n) + rng.normal(0, 0.9, n)
    high = base + rng.uniform(0.5, 2.1, n)
    low = base - rng.uniform(0.5, 2.1, n)
    close = base + rng.normal(0, 0.6, n)
    volume = rng.integers(1500, 9000, n)

    # Optional helpers if regime internals call LBX/CMV paths
    sps = np.clip(rng.normal(0, 0.5, n), -1, 1)

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

    # warm-up
    _ = compute_market_regime(df)

    dt_ms = _best_of_3(lambda: compute_market_regime(df))
    cap_ms = float(os.getenv("RSCORE_CAP_MS", "25.0"))
    print(f"⏱️ RScore latency (N≈2000): {dt_ms:.2f} ms")
    assert dt_ms < cap_ms, f"RScore too slow: {dt_ms:.2f} ms"


if __name__ == "__main__":
    test_latency()
    print("✅ smoke_market_regime_latency: completed")
