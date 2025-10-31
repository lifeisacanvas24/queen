#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/advanced.py — v1.2 (Polars-native, Unified)
# ------------------------------------------------------------
# ✅ No duplication with core.py
# ✅ Uses core.atr as the single source of truth
# ✅ Adds Bollinger Bands, Supertrend, ATR channels
# ✅ Optional attach_advanced() for convenience
# ============================================================
from __future__ import annotations

import polars as pl

from .core import atr as _atr  # reuse canonical ATR


# ---------------- Bollinger Bands ----------------
def bollinger_bands(
    df: pl.DataFrame,
    period: int = 20,
    stddev: float = 2.0,
    column: str = "close",
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Returns (mid, upper, lower) as Series."""
    mid = df[column].rolling_mean(window_size=period)
    std = df[column].rolling_std(window_size=period)
    upper = (mid + stddev * std).alias("bb_upper")
    lower = (mid - stddev * std).alias("bb_lower")
    return mid.alias("bb_mid"), upper, lower


# ---------------- Supertrend (ATR-based) ----------------
def supertrend(
    df: pl.DataFrame, period: int = 10, multiplier: float = 3.0
) -> pl.Series:
    """Returns a 'supertrend' Series (uptrend uses lower band, downtrend uses upper)."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pl.select(pl.max_horizontal(tr1, tr2, tr3).alias("tr")).to_series()

    atr_series = tr.ewm_mean(span=period, adjust=False).fill_null(strategy="forward")
    hl2 = ((high + low) / 2).cast(pl.Float64)
    upper = (hl2 + multiplier * atr_series).to_numpy()
    lower = (hl2 - multiplier * atr_series).to_numpy()
    close_v = close.to_numpy()

    out = []
    in_uptrend = True
    for i in range(len(close_v)):
        if i == 0:
            out.append(float(hl2[0]))
            continue
        cu, pu = upper[i], upper[i - 1]
        cl, pl_ = lower[i], lower[i - 1]
        # smooth bands
        if cu < pu or close_v[i - 1] > pu:
            cu = max(cu, pu)
        if cl > pl_ or close_v[i - 1] < pl_:
            cl = min(cl, pl_)
        # flip
        if in_uptrend and close_v[i] < cl:
            in_uptrend = False
        elif not in_uptrend and close_v[i] > cu:
            in_uptrend = True
        out.append(cl if in_uptrend else cu)

    return pl.Series("supertrend", out)


# ---------------- ATR Channels ----------------
def atr_channels(
    df: pl.DataFrame, period: int = 14, multiplier: float = 1.5
) -> tuple[pl.Series, pl.Series]:
    """Returns (upper, lower) ATR channels around close."""
    a = _atr(df, period)
    return (df["close"] + multiplier * a).alias("atr_upper"), (
        df["close"] - multiplier * a
    ).alias("atr_lower")


# ---------------- Convenience: attach ----------------
def attach_advanced(df: pl.DataFrame) -> pl.DataFrame:
    """Return a cloned DataFrame with advanced columns attached."""
    if df.is_empty():
        return df

    out = df.clone()

    # ATR from core
    out = out.with_columns(_atr(out).alias("atr_14"))

    # Bollinger
    bb_mid, bb_up, bb_lo = bollinger_bands(out)
    out = out.with_columns([bb_mid, bb_up, bb_lo])

    # Supertrend
    out = out.with_columns(supertrend(out))

    # ATR channels
    up_ch, lo_ch = atr_channels(out)
    out = out.with_columns([up_ch, lo_ch])

    return out


# Optional registry (if you introspect exports)
EXPORTS = {
    "bollinger_bands": bollinger_bands,
    "supertrend": supertrend,
    "atr_channels": atr_channels,
    "attach_advanced": attach_advanced,
}
