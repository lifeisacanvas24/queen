# ============================================================
# queen/technicals/indicators/advanced.py (v1.0 — Quant-Core)
# ============================================================
"""Advanced technical indicators — pure Polars, production-ready.

Includes:
    ✅ ATR (Average True Range)
    ✅ Bollinger Bands (20-period mean ± 2σ)
    ✅ Supertrend (ATR-based trend bias)
    ✅ ATR Channels (volatility envelopes)
"""

from __future__ import annotations

import polars as pl

# ============================================================
# ⚙️ Core Helpers
# ============================================================


def _true_range(df: pl.DataFrame) -> pl.Series:
    """Compute True Range (TR) for ATR-based indicators."""
    prev_close = df["close"].shift(1)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - prev_close).abs()
    low_close = (df["low"] - prev_close).abs()
    return pl.max_horizontal(high_low, high_close, low_close)


# ============================================================
# 📊 ATR (Average True Range)
# ============================================================


def atr(df: pl.DataFrame, period: int = 14) -> pl.Series:
    """Compute Average True Range (ATR) using Wilder's smoothing."""
    tr = _true_range(df)
    atr_series = tr.ewm_mean(span=period, adjust=False)
    return atr_series


# ============================================================
# 💎 Bollinger Bands
# ============================================================


def bollinger_bands(
    df: pl.DataFrame, period: int = 20, stddev: float = 2.0, column: str = "close"
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Compute Bollinger Bands (Middle, Upper, Lower)."""
    ma = df[column].rolling_mean(period)
    std = df[column].rolling_std(period)
    upper = ma + stddev * std
    lower = ma - stddev * std
    return ma, upper, lower


def supertrend(
    df: pl.DataFrame, period: int = 10, multiplier: float = 3.0
) -> pl.Series:
    """Compute Supertrend values (Polars-safe eager implementation)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # --- True-range sub-components
    tr1 = (high - low).abs()
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    # --- Row-wise max (universal)
    tr_df = pl.DataFrame({"tr1": tr1, "tr2": tr2, "tr3": tr3})
    try:
        # Polars ≥ 1.0 syntax
        tr = tr_df.select(
            pl.max_horizontal(pl.col("tr1"), pl.col("tr2"), pl.col("tr3"))
        ).to_series()
    except Exception:
        # fallback for very old Polars
        tr = tr_df.max(axis=1)

    tr = tr.fill_null(strategy="forward")

    # --- ATR (EMA)
    atr_series = tr.ewm_mean(span=period, adjust=False).fill_null(strategy="forward")

    # --- Midprice & arrays
    hl2 = ((high + low) / 2).to_numpy()
    atr_vals = atr_series.to_numpy()
    close_vals = close.to_numpy()

    upperband = hl2 + multiplier * atr_vals
    lowerband = hl2 - multiplier * atr_vals

    trend = []
    in_uptrend = True

    for i in range(len(close_vals)):
        if i == 0:
            trend.append(hl2[0])
            continue

        curr_close = close_vals[i]
        prev_close = close_vals[i - 1]
        curr_upper = upperband[i]
        curr_lower = lowerband[i]
        prev_upper = upperband[i - 1]
        prev_lower = lowerband[i - 1]

        # Band smoothing
        if curr_upper < prev_upper or prev_close > prev_upper:
            curr_upper = max(curr_upper, prev_upper)
        if curr_lower > prev_lower or prev_close < prev_lower:
            curr_lower = min(curr_lower, prev_lower)

        # Trend switch
        if in_uptrend and curr_close < curr_lower:
            in_uptrend = False
        elif not in_uptrend and curr_close > curr_upper:
            in_uptrend = True

        trend.append(curr_lower if in_uptrend else curr_upper)

    return pl.Series("supertrend", trend)


# ============================================================
# 📈 ATR Channels (Volatility Envelopes)
# ============================================================


def atr_channels(
    df: pl.DataFrame, period: int = 14, multiplier: float = 1.5
) -> tuple[pl.Series, pl.Series]:
    """Compute ATR channels around closing price."""
    atr_series = atr(df, period)
    upper = df["close"] + multiplier * atr_series
    lower = df["close"] - multiplier * atr_series
    return upper, lower


# ============================================================
# 🧩 Composite Attachment
# ============================================================


def attach_advanced(df: pl.DataFrame) -> pl.DataFrame:
    """Attach advanced indicators to DataFrame."""
    df = df.clone()

    # ATR
    df = df.with_columns(atr(df).alias("atr_14"))

    # Bollinger Bands
    mid, upper, lower = bollinger_bands(df)
    df = df.with_columns(
        [
            mid.alias("bb_mid"),
            upper.alias("bb_upper"),
            lower.alias("bb_lower"),
        ]
    )

    # Supertrend
    st = supertrend(df)
    df = df.with_columns(st)

    # ATR Channels
    upper_ch, lower_ch = atr_channels(df)
    df = df.with_columns(
        [
            upper_ch.alias("atr_upper"),
            lower_ch.alias("atr_lower"),
        ]
    )

    return df
