from __future__ import annotations

import time

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.divergence import detect_divergence


def _build_df(n: int = 2000) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    x = np.linspace(0, 50, n)  # long-ish wave so slopes vary
    price = 100 + 2.0 * np.sin(x) + 0.2 * rng.normal(size=n)
    cmv = 0.8 * np.sin(x + 0.35) + 0.15 * rng.normal(size=n)
    return pl.DataFrame({"close": price, "CMV": cmv})


def test_latency():
    df = _build_df()

    # warm-up
    _ = detect_divergence(df, lookback=5, threshold=0.02)

    # best-of-3 measure
    runs = 3
    best = float("inf")
    for _ in range(runs):
        t0 = time.perf_counter()
        _ = detect_divergence(df, lookback=5, threshold=0.02)
        dt = (time.perf_counter() - t0) * 1000.0
        if dt < best:
            best = dt

    print(f"⏱️ Divergence latency (N≈2000): {best:.2f} ms")
    # Soft upper bound — adjust if your box is slower/faster
    cap_ms = 8.0
    assert best < cap_ms, f"Divergence too slow: {best:.2f} ms"


if __name__ == "__main__":
    test_latency()
    print("✅ smoke_divergence_latency: completed")
