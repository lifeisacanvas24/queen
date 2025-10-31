from __future__ import annotations

import numpy as np
import polars as pl
from queen.technicals.signals.tactical.divergence import (
    detect_divergence,
    summarize_divergence,
)


def test():
    n = 200
    rng = np.random.default_rng(0)
    x = np.linspace(0, 6, n)
    price = np.sin(x) + 0.05 * rng.normal(size=n)
    cmv = np.sin(x + 0.4) * 0.9 + 0.05 * rng.normal(size=n)
    df = pl.DataFrame({"close": price, "CMV": cmv})
    out = detect_divergence(df, lookback=5, threshold=0.02)
    assert {"Divergence_Signal", "Divergence_Score", "Divergence_Flag"}.issubset(
        out.columns
    )
    print("Summary:", summarize_divergence(out))


if __name__ == "__main__":
    test()
    print("✅ smoke_divergence: passed")
