# ============================================================
# queen/technicals/indicators/core.py (v1.1 — Polars-Optimized)
# ============================================================
from __future__ import annotations

import polars as pl


# ---------------- SMA / EMA ----------------
def sma(df: pl.DataFrame, period: int = 20, column: str = "close") -> pl.Series:
    return df[column].rolling_mean(window_size=period)


def ema(df: pl.DataFrame, period: int = 20, column: str = "close") -> pl.Series:
    return df[column].ewm_mean(span=period, adjust=False)


def _slope(s: pl.Series, periods: int = 1) -> pl.Series:
    periods = max(int(periods or 1), 1)
    return (s - s.shift(periods)).alias(f"{s.name}_slope{periods}")


def ema_slope(
    df: pl.DataFrame,
    length: int = 21,
    periods: int = 1,
    column: str = "close",
) -> pl.Series:
    """Slope of EMA(length) over `periods` bars."""
    e = ema(df, period=length, column=column)
    # ensure a stable name for the slope label
    if not getattr(e, "name", None):
        e = e.alias(f"ema_{int(length)}")
    return _slope(e, periods=periods)


# ---------------- RSI ----------------
def rsi(df: pl.DataFrame, period: int = 14, column: str = "close") -> pl.Series:
    delta = df[column].diff()
    # Pure Series path (compatible across Polars versions)
    gain = delta.fill_null(0).apply(lambda x: x if x > 0 else 0.0)
    loss = delta.fill_null(0).apply(lambda x: -x if x < 0 else 0.0)
    avg_gain = gain.ewm_mean(span=period, adjust=False)
    avg_loss = loss.ewm_mean(span=period, adjust=False)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ---------------- MACD ----------------
def macd(
    df: pl.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pl.DataFrame:
    ema_fast = ema(df, fast, column)
    ema_slow = ema(df, slow, column)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm_mean(span=signal, adjust=False)
    hist = macd_line - signal_line
    return pl.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


# ---------------- VWAP ----------------
def vwap(df: pl.DataFrame) -> pl.Series:
    """Compute intraday VWAP (Polars-safe)."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_vol = df["volume"].cum_sum()
    cum_tp_vol = (typical_price * df["volume"]).cum_sum()
    out = cum_tp_vol / cum_vol
    # Ensure proper name
    try:
        return out.rename("vwap")
    except Exception:
        # older Polars might require alias on Expr; wrap via select
        return pl.select(out.alias("vwap")).to_series()


# ---------------- ATR (Series-safe) ----------------
def atr(df: pl.DataFrame, period: int = 14) -> pl.Series:
    """Average True Range (volatility measure)."""
    prev_close = df["close"].shift(1)
    tr1 = (df["high"] - df["low"]).abs()
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    # Use max_horizontal in a select so we always get a materialized Series
    tr = pl.select(pl.max_horizontal(tr1, tr2, tr3).alias("tr")).to_series()
    atr_s = tr.ewm_mean(span=period, adjust=False)
    try:
        return atr_s.rename(f"atr_{period}")
    except Exception:
        return pl.select(atr_s.alias(f"atr_{period}")).to_series()


# ---------------- Attach standard set ----------------
def attach_indicators(
    df: pl.DataFrame,
    ema_periods=(20, 50),
    rsi_period: int = 14,
    macd_cfg=(12, 26, 9),
) -> pl.DataFrame:
    out = df.with_columns(
        [
            ema(df, ema_periods[0]).alias(f"ema_{ema_periods[0]}"),
            ema(df, ema_periods[1]).alias(f"ema_{ema_periods[1]}"),
            rsi(df, rsi_period).alias(f"rsi_{rsi_period}"),
        ]
    )
    macd_df = macd(out, *macd_cfg)
    return out.hstack(macd_df)
