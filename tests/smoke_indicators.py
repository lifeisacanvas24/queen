#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_indicators.py — v1.2 (resilient)
# Validates core indicators without assuming exact return types
# Run:
#   python -m queen.tests.smoke_indicators
#   pytest -q queen/tests/smoke_indicators.py
# ============================================================

from __future__ import annotations

import math

import numpy as np
import polars as pl
from queen.technicals.indicators.advanced import (
    atr,
    atr_channels,
    bollinger_bands,
    supertrend,
)
from queen.technicals.indicators.adx_dmi import (
    adx_dmi,
    adx_summary,
    lbx,
)


def _is_float_dtype(dt) -> bool:
    return dt in (pl.Float32, pl.Float64)


def _is_str_dtype(dt) -> bool:
    # accept string-like outputs (sometimes indicators choose Categorical)
    return dt in (pl.Utf8, pl.String, pl.Categorical)


# ---------- helpers ----------
def _as_series(
    x, *, prefer: tuple[str, ...] = (), df: pl.DataFrame | None = None
) -> pl.Series:
    if isinstance(x, pl.Series):
        return x
    if isinstance(x, pl.Expr):
        if df is None:
            raise TypeError("Expr given but no df provided to evaluate it.")
        return df.select(x.alias("_tmp")).to_series()
    if isinstance(x, pl.DataFrame):
        cols = list(x.columns)
        for name in prefer:
            if name in cols:
                return x[name]
        for c in cols:
            if pl.datatypes.is_float(x[c].dtype):
                return x[c]
        return x[cols[0]]
    raise TypeError(f"Unsupported indicator output type: {type(x)!r}")


def _make_df(n: int = 400) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    base = 100 + np.linspace(0, 5, n) + rng.normal(0, 0.8, n)
    high = base + rng.uniform(0.5, 2.0, n)
    low = base - rng.uniform(0.5, 2.0, n)
    close = base + rng.normal(0, 0.3, n)
    open_ = close + rng.normal(0, 0.2, n)
    vol = rng.integers(50_000, 150_000, n)
    return pl.DataFrame(
        {
            "timestamp": np.arange(n, dtype=np.int64),
            "open": open_.astype(float),
            "high": high.astype(float),
            "low": low.astype(float),
            "close": close.astype(float),
            "volume": vol.astype(np.int64),
        }
    )


# ---------- tests ----------
def test_advanced_indicators_shapes():
    df = _make_df(300)

    s_atr = _as_series(atr(df, period=14), prefer=("atr", "atr_14"))
    assert isinstance(s_atr, pl.Series)
    assert s_atr.len() == df.height

    mid, up, lo = bollinger_bands(df, period=20, stddev=2.0)
    for s in (mid, up, lo):
        s = _as_series(s, prefer=("bb_mid", "middle"))
        assert isinstance(s, pl.Series)
        assert s.len() == df.height

    s_st = _as_series(supertrend(df, period=10, multiplier=3.0), prefer=("supertrend",))
    assert isinstance(s_st, pl.Series)
    assert s_st.len() == df.height

    ch_up, ch_lo = atr_channels(df, period=14, multiplier=1.5)
    for s in (ch_up, ch_lo):
        s = _as_series(s, prefer=("atr_upper", "atr_lower"))
        assert isinstance(s, pl.Series)
        assert s.len() == df.height


def test_adx_dmi_columns_and_types():
    df = _make_df(220)
    out = adx_dmi(df, timeframe="15m")
    expected_cols = {"adx", "di_plus", "di_minus", "adx_trend"}
    assert expected_cols.issubset(set(out.columns))
    assert _is_float_dtype(out["adx"].dtype)
    assert _is_float_dtype(out["di_plus"].dtype)
    assert _is_float_dtype(out["di_minus"].dtype)
    assert _is_str_dtype(out["adx_trend"].dtype)
    assert float(out["adx"].fill_null(0).max()) >= 0.0


def test_lbx_and_summary_contracts():
    df = _make_df(260)
    out = adx_dmi(df, timeframe="15m")
    val = lbx(out, timeframe="15m")
    assert isinstance(val, float)
    assert 0.0 <= val <= 1.0 or math.isclose(val, 0.0) or math.isclose(val, 1.0)
    summary = adx_summary(out)
    want = {"adx", "di_plus", "di_minus", "trend_bias", "strength"}
    assert want.issubset(summary.keys())
    assert isinstance(summary["adx"], float)
    assert isinstance(summary["trend_bias"], str)
    assert summary["strength"] in {"weak", "moderate", "strong"}


if __name__ == "__main__":
    test_advanced_indicators_shapes()
    test_adx_dmi_columns_and_types()
    test_lbx_and_summary_contracts()
    print("✅ smoke_indicators: all checks passed")
