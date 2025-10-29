#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_keltner.py — Sanity for compute_keltner()
# ============================================================

import numpy as np
import polars as pl
from queen.technicals.indicators.keltner import (
    compute_keltner,
    compute_volatility_index,
    summarize_keltner,
)


def _make_df(n: int = 150) -> pl.DataFrame:
    np.random.seed(7)
    base = np.linspace(100, 110, n) + np.random.normal(0, 1.0, n)
    high = base + np.random.uniform(0.4, 1.2, n)
    low = base - np.random.uniform(0.4, 1.2, n)
    close = base + np.random.normal(0, 0.5, n)
    return pl.DataFrame({"high": high, "low": low, "close": close})


def test_keltner_columns():
    df = _make_df()
    out = compute_keltner(df, timeframe="intraday_15m")
    need = {"KC_mid", "KC_upper", "KC_lower", "KC_norm", "KC_Bias"}
    assert need.issubset(set(out.columns)), f"missing {need - set(out.columns)}"


def test_volatility_index_range():
    df = _make_df()
    out = compute_keltner(df)
    vix = compute_volatility_index(out)
    assert 0.0 <= vix <= 1.0, f"volx out of range: {vix}"


def test_summary_structure():
    df = _make_df()
    out = compute_keltner(df)
    summary = summarize_keltner(out)
    assert {"KC_width_pct", "KC_state", "Bias"}.issubset(summary.keys())


if __name__ == "__main__":
    test_keltner_columns()
    test_volatility_index_range()
    test_summary_structure()
    print("✅ smoke_keltner: all checks passed")
