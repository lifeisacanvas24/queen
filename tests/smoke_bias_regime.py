from __future__ import annotations

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.bias_regime import compute_bias_regime


def test():
    n = 128
    df = pl.DataFrame(
        {
            "high": np.random.uniform(100, 110, n),
            "low": np.random.uniform(95, 105, n),
            "close": np.random.uniform(97, 108, n),
            "ADX": np.random.uniform(10, 40, n),
            "CMV": np.random.uniform(-1, 1, n),
        }
    )
    out = compute_bias_regime(df)
    assert {"ATR", "ATR_Ratio", "CMV_Flips", "Regime_State", "Regime_Emoji"}.issubset(
        out.columns
    )
    print("✅ smoke_bias_regime: passed")


if __name__ == "__main__":
    test()
