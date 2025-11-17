# ============================================================
# queen/technicals/indicators/core.py — v1.4 (No-Duplicate + VWAP_LAST)
# ------------------------------------------------------------
# Core Polars-based indicator helpers used across the engine:
#   • SMA / EMA (+ EMA slope)
#   • RSI (+ rsi_last)
#   • Simple MACD helper (DataFrame form)
#   • VWAP (+ vwap_last)
#   • ATR (+ atr_last)
#   • CPR from previous day
#   • OBV trend classification
#
# All functions are forward-only, Polars-native, and kept DRY.
# ============================================================

from __future__ import annotations

import datetime as dt
from typing import Optional

import polars as pl

from queen.helpers.market import MARKET_TZ


# ---------------- SMA / EMA ----------------
def sma(df: pl.DataFrame, period: int = 20, column: str = "close") -> pl.Series:
    """Simple Moving Average over `period` bars."""
    return (
        df[column]
        .cast(pl.Float64, strict=False)
        .rolling_mean(window_size=int(period))
        .alias(f"sma_{period}")
    )


def ema(df: pl.DataFrame, period: int = 20, column: str = "close") -> pl.Series:
    """Exponential Moving Average over `period` bars."""
    return (
        df[column]
        .cast(pl.Float64, strict=False)
        .ewm_mean(span=int(period), adjust=False)
        .alias(f"ema_{period}")
    )


def _slope(s: pl.Series, periods: int = 1) -> pl.Series:
    periods = max(int(periods or 1), 1)
    nm = s.name or "series"
    return (s - s.shift(periods)).alias(f"{nm}_slope{periods}")


def ema_slope(
    df: pl.DataFrame,
    length: int = 21,
    periods: int = 1,
    column: str = "close",
) -> pl.Series:
    """Slope of EMA(length) over `periods` bars."""
    e = ema(df, period=length, column=column)  # already aliased
    return _slope(e, periods=periods)


# ---------------- RSI ----------------
def rsi(df: pl.DataFrame, period: int = 14, column: str = "close") -> pl.Series:
    """Classic RSI (Wilder-style via EMA approximation)."""
    close = df[column].cast(pl.Float64, strict=False)
    delta = close.diff().fill_null(0.0)

    gain = delta.map_elements(lambda x: x if x > 0 else 0.0)
    loss = delta.map_elements(lambda x: -x if x < 0 else 0.0)

    avg_gain = gain.ewm_mean(span=int(period), adjust=False)
    avg_loss = loss.ewm_mean(span=int(period), adjust=False)

    rs = avg_gain / (avg_loss + 1e-12)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.alias(f"rsi_{period}")


# ---------------- MACD (simple helper; advanced MACD lives in momentum_macd.py) ----------------
def macd(
    df: pl.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pl.DataFrame:
    """Simple MACD helper (for any legacy/simple callers)."""
    close = df[column].cast(pl.Float64, strict=False)
    ema_fast = close.ewm_mean(span=int(fast), adjust=False)
    ema_slow = close.ewm_mean(span=int(slow), adjust=False)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm_mean(span=int(signal), adjust=False)
    hist = macd_line - signal_line

    return pl.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "hist": hist,
        }
    )


# ---------------- VWAP ----------------
def vwap(df: pl.DataFrame) -> pl.Series:
    """Running VWAP over the entire DataFrame window."""
    if df.is_empty():
        return pl.Series("vwap", [])

    required = {"high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        return pl.Series("vwap", [0.0] * df.height, dtype=pl.Float64)

    high = df["high"].cast(pl.Float64, strict=False)
    low = df["low"].cast(pl.Float64, strict=False)
    close = df["close"].cast(pl.Float64, strict=False)
    vol = df["volume"].cast(pl.Float64, strict=False)

    typical_price = (high + low + close) / 3.0
    cum_vol = vol.cum_sum()
    cum_tp_vol = (typical_price * vol).cum_sum()

    out = cum_tp_vol / (cum_vol + 1e-12)
    return out.alias("vwap")


def vwap_last(df: pl.DataFrame) -> Optional[float]:
    """Return the latest VWAP value as a float, or None if not computable.

    This is the canonical forward API used by daemons / scanners that only
    need a single scalar VWAP snapshot instead of the full Series.
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return None

    required = {"high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        return None

    s = vwap(df).drop_nulls()
    if s.is_empty():
        return None
    return float(s.tail(1).item())


# ---------------- ATR ----------------
def atr(df: pl.DataFrame, period: int = 14) -> pl.Series:
    """ATR using a simple rolling-mean of True Range."""
    if df.is_empty():
        return pl.Series(f"atr_{period}", [])

    h = df["high"].cast(pl.Float64, strict=False)
    l = df["low"].cast(pl.Float64, strict=False)
    c = df["close"].cast(pl.Float64, strict=False)
    prev_close = c.shift(1)

    tr1 = (h - l).abs()
    tr2 = (h - prev_close).abs()
    tr3 = (l - prev_close).abs()

    tr = pl.select(pl.max_horizontal(tr1, tr2, tr3).alias("tr")).to_series()
    return (
        tr.ewm_mean(span=int(period), adjust=False)
        .alias(f"atr_{period}")
    )


def rsi_last(close: pl.Series, period: int = 14) -> Optional[float]:
    """Return last RSI value from a close Series, or None if insufficient data."""
    if close.len() <= period + 1:
        return None

    close = close.cast(pl.Float64, strict=False).fill_null(strategy="forward")
    diff = close.diff().fill_null(0.0)
    gain = diff.map_elements(lambda x: x if x > 0 else 0.0)
    loss = (-diff).map_elements(lambda x: x if x > 0 else 0.0)

    roll_up = gain.rolling_mean(window_size=int(period))
    roll_dn = loss.rolling_mean(window_size=int(period))

    rs = roll_up / (roll_dn + 1e-12)
    r = 100.0 - (100.0 / (1.0 + rs))
    r = r.drop_nulls().tail(1)
    return float(r.item()) if r.len() else None


def atr_last(df: pl.DataFrame, period: int = 14) -> Optional[float]:
    """Return last ATR value as a float, or None if insufficient data."""
    if df.height < period + 2:
        return None

    h = df["high"].cast(pl.Float64, strict=False)
    l = df["low"].cast(pl.Float64, strict=False)
    c = df["close"].cast(pl.Float64, strict=False)
    prev_c = c.shift(1)

    tr_series = pl.select(
        pl.max_horizontal(
            (h - l).abs(),
            (h - prev_c).abs(),
            (l - prev_c).abs(),
        ).alias("tr")
    ).to_series()

    atr_series = tr_series.rolling_mean(window_size=int(period)).drop_nulls()
    return float(atr_series.tail(1).item()) if atr_series.len() else None


# ---------------- CPR / OBV ----------------
def cpr_from_prev_day(df: pl.DataFrame) -> Optional[float]:
    """Compute classic CPR pivot from the previous day's OHLC."""
    if df.is_empty():
        return None

    ts_col = "timestamp"
    if ts_col not in df.columns:
        return None

    # Convert to market date in IST (or configured MARKET_TZ)
    d_ist = df.select(
        pl.col(ts_col)
        .dt.convert_time_zone(str(MARKET_TZ))
        .dt.date()
    ).to_series()

    if d_ist.is_empty():
        return None

    prev_day = d_ist.max() - dt.timedelta(days=1)
    day_df = df.filter(
        pl.col(ts_col)
        .dt.convert_time_zone(str(MARKET_TZ))
        .dt.date()
        == prev_day
    )
    if day_df.is_empty():
        return None

    H = float(day_df["high"].max())
    L = float(day_df["low"].min())
    C = float(day_df["close"].tail(1).item())
    return (H + L + C) / 3.0


def obv_trend(df: pl.DataFrame) -> str:
    """Return 'Rising' / 'Falling' / 'Flat' OBV regime over recent bars."""
    if df.is_empty():
        return "Flat"

    if "close" not in df.columns or "volume" not in df.columns:
        return "Flat"

    close = df["close"].cast(pl.Float64, strict=False).fill_null(strategy="forward")
    vol = df["volume"].cast(pl.Float64, strict=False).fill_null(0)

    sign = (close.diff() > 0).cast(pl.Int8) - (close.diff() < 0).cast(pl.Int8)
    obv = (sign * vol).cum_sum().fill_null(strategy="forward")

    last = obv.tail(20)
    if last.is_empty() or last.len() < 2:
        return "Flat"

    a = last.head(1).item()
    b = last.tail(1).item()
    if a is None or b is None:
        return "Flat"

    dif = float(b) - float(a)
    if dif > 0:
        return "Rising"
    if dif < 0:
        return "Falling"
    return "Flat"


__all__ = [
    "sma",
    "ema",
    "ema_slope",
    "rsi",
    "rsi_last",
    "macd",
    "vwap",
    "vwap_last",
    "atr",
    "atr_last",
    "cpr_from_prev_day",
    "obv_trend",
]
