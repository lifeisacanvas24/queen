# ============================================================
# queen/technicals/indicators/core.py — v1.2 (Polars-Optimized + DRY helpers)
# ============================================================
from __future__ import annotations

import datetime as dt
from typing import Optional, Tuple

import polars as pl
from queen.helpers.market import MARKET_TZ  # for CPR prev-day calc


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
    e = ema(df, period=length, column=column)
    if not getattr(e, "name", None):
        e = e.alias(f"ema_{int(length)}")
    return _slope(e, periods=periods)


# ---------------- RSI (series-safe) ----------------
def rsi(df: pl.DataFrame, period: int = 14, column: str = "close") -> pl.Series:
    delta = df[column].cast(pl.Float64).diff()
    dz = delta.fill_null(0.0)
    gain = dz.map_elements(lambda x: x if x > 0 else 0.0)
    loss = dz.map_elements(lambda x: -x if x < 0 else 0.0)
    avg_gain = gain.ewm_mean(span=period, adjust=False)
    avg_loss = loss.ewm_mean(span=period, adjust=False)
    rs = avg_gain / (avg_loss + 1e-12)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.alias(f"rsi_{period}")


def rsi_last(close: pl.Series, period: int = 14) -> Optional[float]:
    """Return the latest RSI value; Series-only ops (Polars version friendly)."""
    if close.len() <= period + 1:
        return None
    close = close.cast(pl.Float64, strict=False)
    if close.null_count() > 0:
        # forward-fill then zero as a last resort
        try:
            close = close.fill_null(strategy="forward")
        except Exception:
            close = close.fill_null(0.0)

    diff = close.diff().fill_null(0.0)

    # map_elements avoids clip_min dependence across polars versions
    gain = diff.map_elements(lambda x: x if x > 0 else 0.0)
    loss = (-diff).map_elements(lambda x: x if x > 0 else 0.0)

    roll_up = gain.rolling_mean(window_size=period)
    roll_dn = loss.rolling_mean(window_size=period)

    # Avoid divide-by-zero without pl.when on Series
    rs = roll_up / (roll_dn + 1e-12)
    r = 100.0 - (100.0 / (1.0 + rs))
    r = r.drop_nulls().tail(1)
    return float(r.item()) if r.len() else None

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
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_vol = df["volume"].cum_sum()
    cum_tp_vol = (typical_price * df["volume"]).cum_sum()
    out = cum_tp_vol / cum_vol
    try:
        return out.rename("vwap")
    except Exception:
        return pl.select(out.alias("vwap")).to_series()


def vwap_last(df: pl.DataFrame) -> Optional[float]:
    if df.is_empty():
        return None
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].cast(pl.Float64, strict=False).fill_null(0)
    num = (tp * vol).sum()
    den = vol.sum()
    return float(num / den) if float(den) > 0 else None


# ---------------- ATR ----------------
def atr(df: pl.DataFrame, period: int = 14) -> pl.Series:
    prev_close = df["close"].shift(1)
    tr1 = (df["high"] - df["low"]).abs()
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    tr = pl.select(pl.max_horizontal(tr1, tr2, tr3).alias("tr")).to_series()
    atr_s = tr.ewm_mean(span=period, adjust=False)
    try:
        return atr_s.rename(f"atr_{period}")
    except Exception:
        return pl.select(atr_s.alias(f"atr_{period}")).to_series()


def atr_last(df: pl.DataFrame, period: int = 14) -> Optional[float]:
    """Latest ATR value (Series-safe; no Expr truthiness)."""
    if df.height < period + 2:
        return None

    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)

    # Make TR as a real Series (avoid Expr ops leaking through)
    tr_series = pl.select(
        pl.max_horizontal(
            (h - l).abs(),
            (h - prev_c).abs(),
            (l - prev_c).abs(),
        ).alias("tr")
    ).to_series()

    # Use rolling mean like your earlier logic (EMA version is fine too)
    atr_series = tr_series.rolling_mean(window_size=period).drop_nulls()
    if atr_series.len() == 0:
        return None
    return float(atr_series.tail(1).item())

# ---------------- CPR (prev-day pivot proxy) ----------------
def _prev_day_hlc(df: pl.DataFrame) -> Optional[Tuple[float, float, float]]:
    if df.is_empty():
        return None
    ts_col = "timestamp"
    d_ist = df.select(pl.col(ts_col).dt.convert_time_zone(str(MARKET_TZ)).dt.date()).to_series()
    prev_day = d_ist.max() - dt.timedelta(days=1)
    day_df = df.filter(pl.col(ts_col).dt.convert_time_zone(str(MARKET_TZ)).dt.date() == prev_day)
    if day_df.is_empty():
        return None
    H = float(day_df["high"].max())
    L = float(day_df["low"].min())
    C = float(day_df["close"].tail(1).item())
    return H, L, C


def cpr_from_prev_day(df: pl.DataFrame) -> Optional[float]:
    hlc = _prev_day_hlc(df)
    if not hlc:
        return None
    H, L, C = hlc
    return (H + L + C) / 3.0


# ---------------- OBV trend (Rising/Falling/Flat) ----------------
def obv_trend(df: pl.DataFrame) -> str:
    if df.is_empty():
        return "Flat"
    close = df["close"].cast(pl.Float64, strict=False).fill_null(strategy="forward")
    vol = df["volume"].cast(pl.Float64, strict=False).fill_null(0)
    sign = (close.diff() > 0).cast(pl.Int8) - (close.diff() < 0).cast(pl.Int8)
    obv = (sign * vol).cum_sum().fill_null(strategy="forward")
    last = obv.tail(20)
    if last.is_empty() or last.len() < 2:
        return "Flat"
    a, b = last.head(1).item(), last.tail(1).item()
    if a is None or b is None:
        return "Flat"
    dif = float(b) - float(a)
    return "Rising" if dif > 0 else ("Falling" if dif < 0 else "Flat")


# ---------------- Attach a standard set ----------------
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


# tidy public API
__all__ = [
    "sma", "ema", "ema_slope",
    "rsi", "rsi_last",
    "macd",
    "vwap", "vwap_last",
    "atr", "atr_last",
    "cpr_from_prev_day",
    "obv_trend",
    "attach_indicators",
]
