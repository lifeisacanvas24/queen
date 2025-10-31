# queen/tests/smoke_pre_breakout.py
from __future__ import annotations

import numpy as np
import polars as pl
from queen.technicals.signals.pre_breakout import compute_pre_breakout


def _mk(n=240):
    base = np.linspace(100, 110, n)
    return pl.DataFrame(
        {
            "timestamp": pl.datetime_range(
                start=pl.datetime(2025, 1, 1, 9, 15),
                end=pl.datetime(2025, 1, 1, 9, 15) + pl.duration(minutes=n - 1),
                interval="1m",
                eager=True,
            ),
            "open": base + np.random.normal(0, 0.2, n),
            "high": base + np.random.normal(0.6, 0.2, n),
            "low": base - np.random.normal(0.6, 0.2, n),
            "close": base + np.random.normal(0, 0.3, n),
            "volume": np.random.randint(1000, 4000, n),
        }
    )


def test_pre_breakout():
    df = _mk(300)
    out = compute_pre_breakout(df)
    for c in ("cpr_width", "SPS", "momentum", "momentum_smooth", "trend_up"):
        assert c in out.columns


if __name__ == "__main__":
    test_pre_breakout()
    print("✅ smoke_pre_breakout: all checks passed")
