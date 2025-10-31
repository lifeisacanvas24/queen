# queen/tests/smoke_bias_regime_latency.py
from __future__ import annotations

import time

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.bias_regime import compute_bias_regime


def test():
    n = 2000
    df = pl.DataFrame(
        {
            "high": np.random.uniform(100, 110, n),
            "low": np.random.uniform(95, 105, n),
            "close": np.random.uniform(97, 108, n),
            "ADX": np.random.uniform(10, 40, n),
            "CMV": np.random.uniform(-1, 1, n),
        }
    )
    t0 = time.perf_counter()
    out = compute_bias_regime(df)
    dt = (time.perf_counter() - t0) * 1000
    assert {"ATR", "ATR_Ratio", "CMV_Flips", "Regime_State", "Regime_Emoji"}.issubset(
        out.columns
    )
    print(
        f"⏱️ BiasRegime latency (N≈{n}): {dt:.2f} ms\n✅ smoke_bias_regime_latency: completed"
    )


if __name__ == "__main__":
    test()
