# ============================================================
# quant/indicators/core.py (v1.0 — Polars-Optimized)
# ============================================================
"""Quant-Core Indicator Library (Polars-native)

Fast, dependency-free indicator calculations for Quant-Core:
    EMA, SMA, RSI, MACD, ATR, VWAP
All based on your unified candle schema:
    timestamp | open | high | low | close | volume | oi | symbol
"""

from __future__ import annotations

import polars as pl

# ============================================================
# 🧮 Simple / Exponential Moving Averages
# ============================================================

def sma(df: pl.DataFrame, period: int = 20, column: str = "close") -> pl.Series:
    """Simple moving average."""
    return df[column].rolling_mean(window_size=period)


def ema(df: pl.DataFrame, period: int = 20, column: str = "close") -> pl.Series:
    """Exponential moving average (EMA)."""
    return df[column].ewm_mean(span=period, adjust=False)

# ============================================================
# 💪 Relative Strength Index (RSI)
# ============================================================

def rsi(df: pl.DataFrame, period: int = 14, column: str = "close") -> pl.Series:
    """Compute RSI using exponential smoothing (Polars ≥ 1.x safe)."""
    delta = df[column].diff()

    # ✅ Replace clip_min(0) with Polars expression-based logic
    gain = delta.map_elements(lambda x: x if x > 0 else 0.0)
    loss = delta.map_elements(lambda x: -x if x < 0 else 0.0)

    avg_gain = gain.ewm_mean(span=period, adjust=False)
    avg_loss = loss.ewm_mean(span=period, adjust=False)
    rs = avg_gain / avg_loss
    rsi_series = 100 - (100 / (1 + rs))
    return rsi_series

# ============================================================
# 📈 MACD (Moving Average Convergence Divergence)
# ============================================================

def macd(df: pl.DataFrame,
         fast: int = 12,
         slow: int = 26,
         signal: int = 9,
         column: str = "close") -> pl.DataFrame:
    """MACD (Moving Average Convergence Divergence)."""
    ema_fast = ema(df, fast, column)
    ema_slow = ema(df, slow, column)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm_mean(span=signal, adjust=False)
    hist = macd_line - signal_line
    return pl.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})

# ============================================================
# 🎯 Average True Range (ATR)
# ============================================================

def atr(df: pl.DataFrame, period: int = 14) -> pl.Series:
    """Average True Range (volatility measure)."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pl.concat_list([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ]).list.max()
    return tr.ewm_mean(span=period, adjust=False)

# ============================================================
# 💰 Volume Weighted Average Price (VWAP)
# ============================================================

def vwap(df: pl.DataFrame) -> pl.Series:
    """Compute intraday VWAP."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_vol = df["volume"].cumsum()
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    return cumulative_tp_vol / cumulative_vol

# ============================================================
# 🧱 Helper: attach indicators to DataFrame
# ============================================================

def attach_indicators(df: pl.DataFrame,
                      ema_periods=(20, 50),
                      rsi_period: int = 14,
                      macd_cfg=(12, 26, 9)) -> pl.DataFrame:
    """Return DataFrame with standard indicators attached."""
    df = df.with_columns([
        ema(df, ema_periods[0]).alias(f"ema_{ema_periods[0]}"),
        ema(df, ema_periods[1]).alias(f"ema_{ema_periods[1]}"),
        rsi(df, rsi_period).alias(f"rsi_{rsi_period}")
    ])
    macd_df = macd(df, *macd_cfg)
    return df.hstack(macd_df)
