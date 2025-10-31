from __future__ import annotations

import time

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.bias_regime import compute_bias_regime


def _build_mock(n: int = 2000) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    base = np.linspace(100, 110, n) + rng.normal(0, 0.8, n)
    high = base + rng.uniform(0.2, 1.2, n)
    low = base - rng.uniform(0.2, 1.2, n)
    close = base + rng.normal(0, 0.4, n)
    adx = rng.uniform(10, 40, n)
    cmv = rng.uniform(-1, 1, n)
    return pl.DataFrame(
        {"high": high, "low": low, "close": close, "ADX": adx, "CMV": cmv}
    )


def test_latency():
    df = _build_mock()

    # warm-up
    compute_bias_regime(df)

    t0 = time.perf_counter()
    out = compute_bias_regime(df)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    # sanity checks
    assert {"ATR", "ATR_Ratio", "CMV_Flips", "Regime_State", "Regime_Emoji"}.issubset(
        set(out.columns)
    ), "Missing expected output columns"

    print(f"⏱️ BiasRegime latency (N≈{df.height}): {dt_ms:.2f} ms")
    # Soft perf guard (tune if needed)
    assert dt_ms < 8.0, f"BiasRegime too slow: {dt_ms:.2f} ms"


if __name__ == "__main__":
    test_latency()
    print("✅ smoke_bias_regime_latency: completed")
