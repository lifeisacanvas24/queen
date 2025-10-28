#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/overlays.py — v1.0
# Simple EMA/VWAP helpers exposed via EXPORTS
# ============================================================
from __future__ import annotations

import polars as pl

# top-level, below imports
_BASE_MIN_BARS = {
    # add per-indicator overrides here only if you want to *force* min bars
    # (policy will still compute a number if no override exists)
    "ema": 60,
    "ema_cross": 120,
    "vwap": 40,
    "price_minus_vwap": 40,
}
INDICATOR_MIN_BARS = {**_BASE_MIN_BARS}


def ema(df: pl.DataFrame, length: int = 20, price_col: str = "close") -> pl.Series:
    s = df[price_col].cast(pl.Float64)
    alpha = 2.0 / (float(length) + 1.0)
    out = s.ewm_mean(alpha=alpha, adjust=False)
    out = out.alias(f"ema{length}")
    return out


def ema_cross(
    df: pl.DataFrame, fast: int = 20, slow: int = 50, price_col: str = "close"
) -> pl.Series:
    f = ema(df, length=fast, price_col=price_col)
    s = ema(df, length=slow, price_col=price_col)
    spread = (f - s).alias("ema_spread")
    return spread  # use crosses_* 0 for signals


def vwap(
    df: pl.DataFrame,
    price_cols: tuple[str, str, str] = ("high", "low", "close"),
    vol_col: str = "volume",
) -> pl.Series:
    h, l, c = (df[price_cols[0]], df[price_cols[1]], df[price_cols[2]])
    v = df[vol_col].cast(pl.Float64)
    typical = ((h + l + c) / 3.0).cast(pl.Float64)
    numer = (typical * v).cum_sum()
    denom = v.cum_sum().replace({0.0: None})
    vw = (numer / denom).fill_null(strategy="forward").alias("vwap")
    return vw


def price_minus_vwap(
    df: pl.DataFrame,
    price_col: str = "close",
) -> pl.Series:
    pvwap = vwap(df)
    diff = (df[price_col].cast(pl.Float64) - pvwap).alias("price_minus_vwap")
    return diff


def _compute_slope(s: pl.Series, periods: int = 1) -> pl.Series:
    """Simple discrete slope: s - s.shift(periods).
    Keeps the same dtype; first `periods` rows become nulls.
    """
    periods = int(periods) if periods and int(periods) > 0 else 1
    return (s - s.shift(periods)).alias(f"{s.name}_slope{periods}")


def ema_slope(
    df: pl.DataFrame, length: int = 21, periods: int = 1, **kwargs
) -> pl.Series:
    """Convenience wrapper: slope of EMA(length) over `periods` bars.
    Returns a Series named like 'ema{length}_slope{periods}'.
    """
    # Reuse your existing ema() implementation to get the EMA level first.
    ema_series = ema(df, length=length, **kwargs)
    # Ensure the name is stable (your ema() already used 'ema{length}')
    if not getattr(ema_series, "name", None):
        ema_series = ema_series.alias(f"ema{int(length)}")
    return _compute_slope(ema_series, periods=periods)


EXPORTS = {
    "ema": ema,  # Series 'ema{length}'
    "ema_slope": ema_slope,  # Series 'ema{length}_slope{periods}'
    "ema_cross": ema_cross,  # Series 'ema_spread' (fast - slow)
    "vwap": vwap,  # Series 'vwap'
    "price_minus_vwap": price_minus_vwap,  # Series 'price_minus_vwap'
}
