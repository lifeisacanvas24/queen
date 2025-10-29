#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/advanced.py — v1.2 (Polars-native, Unified)
# Classic advanced overlays + unified aggregator for specialized engines
# ============================================================
from __future__ import annotations

import polars as pl


# ---------- Classic helpers (unchanged) ----------
def _true_range(df: pl.DataFrame) -> pl.Series:
    prev_close = df["close"].shift(1)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - prev_close).abs()
    low_close = (df["low"] - prev_close).abs()
    return pl.max_horizontal(high_low, high_close, low_close)


def atr(df: pl.DataFrame, period: int = 14, name: str = "atr_14") -> pl.Series:
    tr = _true_range(df)
    expr = tr.ewm_mean(span=period, adjust=False).alias(name)
    return df.select(expr).to_series()


def bollinger_bands(
    df: pl.DataFrame, period: int = 20, stddev: float = 2.0, column: str = "close"
) -> tuple[pl.Series, pl.Series, pl.Series]:
    mid = df[column].rolling_mean(window_size=period)
    std = df[column].rolling_std(window_size=period)
    upper = mid + stddev * std
    lower = mid - stddev * std
    return mid, upper, lower


def supertrend(
    df: pl.DataFrame, period: int = 10, multiplier: float = 3.0
) -> pl.Series:
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
    hl2 = (high + low) / 2
    # Convert to numpy for the simple loop logic
    hl2n, atrn, closen = hl2.to_numpy(), atr_series.to_numpy(), close.to_numpy()
    upperband = hl2n + multiplier * atrn
    lowerband = hl2n - multiplier * atrn
    trend_vals: list[float] = []
    in_uptrend = True
    for i in range(len(closen)):
        if i == 0:
            trend_vals.append(float(hl2n[0]))
            continue
        curr_close, prev_close = closen[i], closen[i - 1]
        curr_upper, prev_upper = upperband[i], upperband[i - 1]
        curr_lower, prev_lower = lowerband[i], lowerband[i - 1]
        if curr_upper < prev_upper or prev_close > prev_upper:
            curr_upper = max(curr_upper, prev_upper)
        if curr_lower > prev_lower or prev_close < prev_lower:
            curr_lower = min(curr_lower, prev_lower)
        if in_uptrend and curr_close < curr_lower:
            in_uptrend = False
        elif not in_uptrend and curr_close > curr_upper:
            in_uptrend = True
        trend_vals.append(curr_lower if in_uptrend else curr_upper)
    return pl.Series("supertrend", trend_vals)


def atr_channels(
    df: pl.DataFrame, period: int = 14, multiplier: float = 1.5
) -> tuple[pl.Series, pl.Series]:
    a = atr(df, period)
    return df["close"] + multiplier * a, df["close"] - multiplier * a


# ---------- Unified aggregator bits ----------
def _hstack_safe(base: pl.DataFrame, add: pl.DataFrame) -> pl.DataFrame:
    if add.is_empty():
        return base
    overlap = [c for c in add.columns if c in base.columns]
    if overlap:
        add = add.drop(overlap)
    return base.hstack(add)


# Import specialized engines (already present in your tree)
from .keltner import compute_keltner
from .momentum_macd import compute_macd as compute_macd_adv
from .volume_chaikin import chaikin as compute_chaikin
from .volume_mfi import compute_mfi

# (Optionally include breadth & adx if desired)
# from .breadth_cumulative import compute_breadth
# from .breadth_momentum import compute_breadth_momentum
# from .adx_dmi import adx_dmi


def attach_advanced(df: pl.DataFrame, context: str = "intraday_15m") -> pl.DataFrame:
    """Return a DataFrame with:
    Classic advanced overlays (ATR/Bollinger/Supertrend/ATR channels),
    plus specialized engines (Keltner, adv-MACD, Chaikin, MFI), stitched safely.
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    out = df.clone()

    # ----- Classic overlays -----
    out = out.with_columns(atr(out).alias("atr_14"))
    mid, up, lo = bollinger_bands(out)
    out = out.with_columns(
        [mid.alias("bb_mid"), up.alias("bb_upper"), lo.alias("bb_lower")]
    )
    out = out.with_columns(supertrend(out))
    up_ch, lo_ch = atr_channels(out)
    out = out.with_columns([up_ch.alias("atr_upper"), lo_ch.alias("atr_lower")])

    # ----- Specialized engines -----
    out = _hstack_safe(out, compute_keltner(df, context=context))
    out = _hstack_safe(
        out, compute_macd_adv(df, context=context)
    )  # normalized/slope/crossover
    # For Chaikin we map context like 'intraday_15m' -> '15m' timeframe when needed
    tf = context.split("_")[-1] if "_" in context else context
    out = _hstack_safe(out, compute_chaikin(df, timeframe=tf))
    out = _hstack_safe(out, compute_mfi(df, context=context))

    # Optionally:
    # out = _hstack_safe(out, compute_breadth(df, context=context))
    # out = _hstack_safe(out, compute_breadth_momentum(df, context=context))
    # out = _hstack_safe(out, adx_dmi(df, timeframe=tf))

    return out


# ---------- Registry exports ----------
EXPORTS = {
    "atr": atr,
    "bollinger_bands": bollinger_bands,
    "supertrend": supertrend,
    "atr_channels": atr_channels,
    "attach_advanced": attach_advanced,
}
