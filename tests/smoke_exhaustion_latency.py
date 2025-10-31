from __future__ import annotations

import time

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.exhaustion import detect_exhaustion_bars


def _gen_df(n: int = 2000) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    base = np.linspace(100, 120, n) + rng.normal(0, 0.8, n)
    high = base + rng.uniform(0.3, 1.5, n)
    low = base - rng.uniform(0.3, 1.5, n)
    close = base + rng.normal(0, 0.4, n)
    volume = rng.integers(1_000, 8_000, n)
    cmv = np.tanh(np.sin(np.linspace(0, 10, n)) + rng.normal(0, 0.05, n))
    return pl.DataFrame(
        {"high": high, "low": low, "close": close, "volume": volume, "CMV": cmv}
    )


def test_latency(n: int = 2000, rounds: int = 3, cap_ms: float = 5.0):
    df = _gen_df(n)

    # warm-up JIT/vectorized paths
    _ = detect_exhaustion_bars(df)

    best_ms = float("inf")
    for _ in range(rounds):
        t0 = time.perf_counter()
        _ = detect_exhaustion_bars(df)
        dt = (time.perf_counter() - t0) * 1000.0
        if dt < best_ms:
            best_ms = dt

    print(f"⏱️ Exhaustion latency (N≈{n}): {best_ms:.2f} ms")
    assert best_ms < cap_ms, f"Exhaustion too slow: {best_ms:.2f} ms"


if __name__ == "__main__":
    test_latency()
    print("✅ smoke_exhaustion_latency: completed")
