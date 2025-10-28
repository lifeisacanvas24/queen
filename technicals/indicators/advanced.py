#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/advanced.py — v1.1 (Polars-native)
# ============================================================
from __future__ import annotations

import polars as pl


# ------------------------------------------------------------
# Core helpers
# ------------------------------------------------------------
def _true_range(df: pl.DataFrame) -> pl.Series:
    """Row-wise True Range = max(high-low, |high-prev_close|, |low-prev_close|)."""
    prev_close = df["close"].shift(1)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - prev_close).abs()
    low_close = (df["low"] - prev_close).abs()
    return pl.max_horizontal(high_low, high_close, low_close)


# ------------------------------------------------------------
# ATR (Average True Range)
# ------------------------------------------------------------
def atr(df: pl.DataFrame, period: int = 14, name: str = "atr_14") -> pl.Series:
    """Compute Average True Range (ATR) and return a concrete Series."""
    tr = _true_range(df)  # Series
    # Some Polars versions return an Expr for ewm_mean; force-evaluate to Series.
    expr = tr.ewm_mean(span=period, adjust=False).alias(name)
    return df.select(expr).to_series()


# ------------------------------------------------------------
# Bollinger Bands
# ------------------------------------------------------------
def bollinger_bands(
    df: pl.DataFrame,
    period: int = 20,
    stddev: float = 2.0,
    column: str = "close",
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Returns (mid, upper, lower) as Series.
    mid = rolling_mean, bands = mid ± stddev * rolling_std
    """
    mid = df[column].rolling_mean(window_size=period)
    std = df[column].rolling_std(window_size=period)
    upper = mid + stddev * std
    lower = mid - stddev * std
    return mid, upper, lower


# ------------------------------------------------------------
# Supertrend (ATR-based bias line)
# ------------------------------------------------------------
def supertrend(
    df: pl.DataFrame, period: int = 10, multiplier: float = 3.0
) -> pl.Series:
    """Returns a 'supertrend' Series (uptrend uses lower band, downtrend uses upper)."""
    high, low, close = df["high"], df["low"], df["close"]

    tr1 = (high - low).abs()
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr_df = pl.DataFrame({"tr1": tr1, "tr2": tr2, "tr3": tr3})

    try:
        tr = tr_df.select(
            pl.max_horizontal(pl.col("tr1"), pl.col("tr2"), pl.col("tr3"))
        ).to_series()
    except Exception:
        tr = tr_df.max(axis=1)
    tr = tr.fill_null(strategy="forward")

    atr_series = tr.ewm_mean(span=period, adjust=False).fill_null(strategy="forward")
    hl2 = ((high + low) / 2).to_numpy()
    atr_vals = atr_series.to_numpy()
    close_vals = close.to_numpy()

    upperband = hl2 + multiplier * atr_vals
    lowerband = hl2 - multiplier * atr_vals

    trend_vals: list[float] = []
    in_uptrend = True
    for i in range(len(close_vals)):
        if i == 0:
            trend_vals.append(hl2[0])
            continue

        curr_close = close_vals[i]
        prev_close = close_vals[i - 1]
        curr_upper, prev_upper = upperband[i], upperband[i - 1]
        curr_lower, prev_lower = lowerband[i], lowerband[i - 1]

        # Smooth bands
        if curr_upper < prev_upper or prev_close > prev_upper:
            curr_upper = max(curr_upper, prev_upper)
        if curr_lower > prev_lower or prev_close < prev_lower:
            curr_lower = min(curr_lower, prev_lower)

        # Trend flip
        if in_uptrend and curr_close < curr_lower:
            in_uptrend = False
        elif not in_uptrend and curr_close > curr_upper:
            in_uptrend = True

        trend_vals.append(curr_lower if in_uptrend else curr_upper)

    return pl.Series("supertrend", trend_vals)


# ------------------------------------------------------------
# ATR Channels (volatility envelopes)
# ------------------------------------------------------------
def atr_channels(
    df: pl.DataFrame, period: int = 14, multiplier: float = 1.5
) -> tuple[pl.Series, pl.Series]:
    """Returns (upper, lower) channels around close using ATR."""
    a = atr(df, period)
    return df["close"] + multiplier * a, df["close"] - multiplier * a


# ------------------------------------------------------------
# Convenience: attach multiple columns
# ------------------------------------------------------------
def attach_advanced(df: pl.DataFrame) -> pl.DataFrame:
    """Return a cloned DataFrame with useful advanced columns attached."""
    out = df.clone()

    # ATR
    out = out.with_columns(atr(out).alias("atr_14"))

    # Bollinger
    mid, up, lo = bollinger_bands(out)
    out = out.with_columns(
        [mid.alias("bb_mid"), up.alias("bb_upper"), lo.alias("bb_lower")]
    )

    # Supertrend
    out = out.with_columns(supertrend(out))

    # ATR channels
    up_ch, lo_ch = atr_channels(out)
    out = out.with_columns([up_ch.alias("atr_upper"), lo_ch.alias("atr_lower")])

    return out


# ------------------------------------------------------------
# Registry exports
# ------------------------------------------------------------
EXPORTS = {
    "atr": atr,
    "bollinger_bands": bollinger_bands,  # tuple return is OK; used by rules via custom ops
    "supertrend": supertrend,
    "atr_channels": atr_channels,  # tuple return is OK
    "attach_advanced": attach_advanced,  # convenience (not typically used in rules)
}
