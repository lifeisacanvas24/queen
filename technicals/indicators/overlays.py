# queen/technicals/indicators/overlays.py — v1.1
from __future__ import annotations

import polars as pl

_BASE_MIN_BARS = {"ema": 60, "ema_cross": 120, "vwap": 40, "price_minus_vwap": 40}
INDICATOR_MIN_BARS = {**_BASE_MIN_BARS}


def ema(df: pl.DataFrame, length: int = 20, price_col: str = "close") -> pl.Series:
    s = df[price_col].cast(pl.Float64)
    out = s.ewm_mean(span=int(length), adjust=False).alias(f"ema{int(length)}")
    return out


def ema_cross(
    df: pl.DataFrame, fast: int = 20, slow: int = 50, price_col: str = "close"
) -> pl.Series:
    f = ema(df, length=fast, price_col=price_col)
    s = ema(df, length=slow, price_col=price_col)
    return (f - s).alias("ema_spread")  # use crosses_* 0 for signals


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
    return (numer / denom).fill_null(strategy="forward").alias("vwap")


def price_minus_vwap(df: pl.DataFrame, price_col: str = "close") -> pl.Series:
    pvwap = vwap(df)
    return (df[price_col].cast(pl.Float64) - pvwap).alias("price_minus_vwap")


def _compute_slope(s: pl.Series, periods: int = 1) -> pl.Series:
    periods = max(1, int(periods))
    return (s - s.shift(periods)).alias(f"{s.name}_slope{periods}")


def ema_slope(
    df: pl.DataFrame, length: int = 21, periods: int = 1, **kwargs
) -> pl.Series:
    e = ema(df, length=length, **kwargs)
    if not getattr(e, "name", None):
        e = e.alias(f"ema{int(length)}")
    return _compute_slope(e, periods=periods)


EXPORTS = {
    "ema": ema,
    "ema_slope": ema_slope,
    "ema_cross": ema_cross,
    "vwap": vwap,
    "price_minus_vwap": price_minus_vwap,
}
