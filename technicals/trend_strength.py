# queen/technicals/trend_strength.py
from __future__ import annotations

import polars as pl


def compute_trend_strength(df: pl.DataFrame) -> str:
    """Returns one of:
        "strong_up", "up", "sideways", "down", "strong_down"

    Uses EMA alignment + HH/HL structure (last 5 vs last 10 bars).
    Expects at least: columns ['close', 'high', 'low'].
    """
    if df.height < 20:
        return "sideways"

    close = pl.col("close")

    # quick EMA approximations using EWM on the whole frame
    ema20  = df.select(close.ewm_mean(span=20)).item()
    ema50  = df.select(close.ewm_mean(span=50)).item()
    ema100 = df.select(close.ewm_mean(span=100)).item()

    # Basic EMA alignment
    if ema20 > ema50 > ema100:
        trend = "up"
    elif ema100 > ema50 > ema20:
        trend = "down"
    else:
        trend = "sideways"

    # Structure check (HH/HL vs previous window)
    last5 = df.tail(5)
    last10 = df.tail(10)

    if last5.height >= 5 and last10.height >= 10:
        hh = last5.get_column("high").max() > last10.get_column("high").max()
        hl = last5.get_column("low").min()  > last10.get_column("low").min()

        if trend == "up" and hh and hl:
            return "strong_up"
        if trend == "down" and (not hh) and (not hl):
            return "strong_down"

    return trend
