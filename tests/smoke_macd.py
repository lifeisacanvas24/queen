#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_macd.py — Sanity for compute_macd()
# ============================================================

import numpy as np
import polars as pl
from queen.technicals.indicators.momentum_macd import (
    compute_macd,
    summarize_macd,
)


def _make_df(n: int = 200) -> pl.DataFrame:
    np.random.seed(42)
    x = np.linspace(0, 8 * np.pi, n)
    close = 100 + np.sin(x) * 5 + np.random.normal(0, 0.3, n)
    return pl.DataFrame({"close": close})


def test_macd_columns():
    df = _make_df()
    out = compute_macd(df, timeframe="intraday_15m")
    need = {
        "MACD_line",
        "MACD_signal",
        "MACD_hist",
        "MACD_norm",
        "MACD_slope",
        "MACD_crossover",
    }
    assert need.issubset(set(out.columns)), f"missing {need - set(out.columns)}"


def test_summary_keys():
    df = _make_df()
    out = compute_macd(df)
    summary = summarize_macd(out)
    for k in ["MACD_line", "MACD_signal", "MACD_hist", "bias"]:
        assert k in summary, f"missing {k} in summary"


if __name__ == "__main__":
    test_macd_columns()
    test_summary_keys()
    print("✅ smoke_macd: all checks passed")
