#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_pre_breakout.py
# ------------------------------------------------------------
# Verifies pre_breakout outputs (100% Polars).
# Asserts presence of: cpr_width, SPS, trend_up
# ============================================================

from __future__ import annotations

import polars as pl
from queen.technicals.signals.pre_breakout import compute_pre_breakout


def test():
    n = 120
    df = pl.DataFrame(
        {
            "close": pl.Series([100 + i * 0.05 for i in range(n)], dtype=pl.Float64),
            "high": pl.Series([100 + i * 0.06 for i in range(n)], dtype=pl.Float64),
            "low": pl.Series([100 + i * 0.04 for i in range(n)], dtype=pl.Float64),
            "volume": pl.Series(
                [1000 + (i % 10) * 25 for i in range(n)], dtype=pl.Int64
            ),
        }
    )

    out = compute_pre_breakout(df, timeframe="15m")

    required = {"cpr_width", "SPS", "trend_up"}
    missing = required - set(out.columns)
    assert not missing, f"Missing columns: {sorted(missing)}"

    # basic sanity checks
    assert out.height == n, f"row count changed: {out.height} != {n}"
    assert out.select(pl.col("SPS").is_not_null().sum()).item() > 0, "SPS all null?"
    assert (
        out.select(pl.col("trend_up").is_not_null().sum()).item() > 0
    ), "trend_up all null?"

    print("✅ smoke_pre_breakout: passed")


if __name__ == "__main__":
    test()
