#!/usr/bin/env python3
# ============================================================
# queen/technicals/trend_strength_daily.py — v1.1
# ------------------------------------------------------------
# Daily Trend Strength (derived from intraday OHLCV)
#
# Responsibilities:
#   • Take raw intraday OHLCV (any interval with "timestamp")
#   • Compress to 1D bars in MARKET_TZ
#   • Use EMA(20/50/200) + HH/HL / LH/LL structure
#   • Return a compact dict for scoring / cockpit / overrides:
#       - Trend_Strength_Score_D   (0–10)
#       - Trend_Strength_Label_D   ("Strong Up", "Up", "Range", "Down", "Strong Down")
#       - Trend_Bias_D             ("Bullish", "Bearish", "Range", "Unknown")
#       - Trend_Ema_Stack_D        ("Bull", "Bear", "Mixed", "Unknown")
#       - Trend_HHHL_Confirm_D     (bool)
#       - Trend_LHLL_Confirm_D     (bool)
#       - Trend_Bars_D             (# daily bars used)
#
# Notes:
#   • Pure Polars, no pandas.
#   • Does NOT depend on Bible; uses indicators.core only.
#   • Safe neutral output when data is insufficient.
# ============================================================

from __future__ import annotations

from typing import Any, Dict

import polars as pl

from queen.helpers.market import MARKET_TZ_KEY
from queen.technicals.indicators import core as ind


# -----------------------------
# Daily compression helper
# -----------------------------
def _intraday_to_daily(df: pl.DataFrame) -> pl.DataFrame:
    """Compress intraday OHLCV into one bar per session date (MARKET_TZ).

    Expects:
      • "timestamp" (Datetime)
      • "open", "high", "low", "close" (numeric)

    Returns:
      • DataFrame with: ["d", "open", "high", "low", "close"]

    """
    if (
        df.is_empty()
        or "timestamp" not in df.columns
        or "open" not in df.columns
        or "high" not in df.columns
        or "low" not in df.columns
        or "close" not in df.columns
    ):
        return pl.DataFrame(
            {
                "d": pl.Series([], dtype=pl.Date),
                "open": pl.Series([], dtype=pl.Float64),
                "high": pl.Series([], dtype=pl.Float64),
                "low": pl.Series([], dtype=pl.Float64),
                "close": pl.Series([], dtype=pl.Float64),
            }
        )

    dated = df.with_columns(
        pl.col("timestamp")
        .dt.convert_time_zone(MARKET_TZ_KEY)
        .dt.date()
        .alias("d")
    )

    daily = (
        dated.sort("timestamp")
        .group_by("d")
        .agg(
            pl.col("open").first().alias("open"),
            pl.col("high").max().alias("high"),
            pl.col("low").min().alias("low"),
            pl.col("close").last().alias("close"),
        )
        .sort("d")
    )

    return daily


# -----------------------------
# HH/HL helpers
# -----------------------------
def _hh_hl_confirm(daily: pl.DataFrame, lookback: int = 5) -> bool:
    """Return True if closes & lows show a clear HH/HL structure recently."""
    if daily.height < lookback + 2:
        return False
    tail = daily.tail(lookback + 1)
    closes = tail["close"].cast(pl.Float64).to_list()
    lows = tail["low"].cast(pl.Float64).to_list()

    try:
        last_c = closes[-1]
        last_l = lows[-1]
        prev_cs = closes[:-1]
        prev_ls = lows[:-1]
        return last_c > max(prev_cs[-3:]) and last_l > max(prev_ls[-3:])
    except Exception:
        return False


def _lh_ll_confirm(daily: pl.DataFrame, lookback: int = 5) -> bool:
    """Return True if closes & highs show a clear LH/LL structure recently."""
    if daily.height < lookback + 2:
        return False
    tail = daily.tail(lookback + 1)
    closes = tail["close"].cast(pl.Float64).to_list()
    highs = tail["high"].cast(pl.Float64).to_list()

    try:
        last_c = closes[-1]
        last_h = highs[-1]
        prev_cs = closes[:-1]
        prev_hs = highs[:-1]
        return last_c < min(prev_cs[-3:]) and last_h < min(prev_hs[-3:])
    except Exception:
        return False


# -----------------------------
# EMA stack + trend label
# -----------------------------
def _ema_stack_label(
    ema20: float | None, ema50: float | None, ema200: float | None
) -> str:
    if ema20 is None or ema50 is None or ema200 is None:
        return "Unknown"
    if ema20 > ema50 > ema200:
        return "Bull"
    if ema20 < ema50 < ema200:
        return "Bear"
    return "Mixed"


def _trend_from_stack_and_structure(
    stack: str,
    hhhl: bool,
    lhll: bool,
) -> tuple[str, str, float]:
    """Return (Trend_Strength_Label_D, Trend_Bias_D, score)."""
    # Defaults
    label = "Range"
    bias = "Range"
    score = 5.0

    if stack == "Bull":
        bias = "Bullish"
        if hhhl:
            label = "Strong Up"
            score = 9.0
        else:
            label = "Up"
            score = 7.0
    elif stack == "Bear":
        bias = "Bearish"
        if lhll:
            label = "Strong Down"
            score = 2.0
        else:
            label = "Down"
            score = 3.5
    else:
        label = "Range"
        bias = "Range"
        score = 5.0

    return label, bias, score


# -----------------------------
# Public API
# -----------------------------
def compute_daily_trend_strength(
    df: pl.DataFrame,
    *,
    min_days: int = 30,
) -> Dict[str, Any]:
    """Compute daily trend strength from intraday OHLCV."""
    neutral: Dict[str, Any] = {
        "Trend_Strength_Score_D": 0.0,
        "Trend_Strength_Label_D": "Unknown",
        "Trend_Bias_D": "Unknown",
        "Trend_Ema_Stack_D": "Unknown",
        "Trend_HHHL_Confirm_D": False,
        "Trend_LHLL_Confirm_D": False,
        "Trend_Bars_D": 0,
    }

    try:
        daily = _intraday_to_daily(df)
    except Exception:
        return neutral

    if daily.is_empty() or daily.height < min_days:
        out = dict(neutral)
        out["Trend_Bars_D"] = int(daily.height)
        return out

    try:
        ema20 = float(ind.ema(daily, 20, "close").drop_nulls().tail(1).item())
    except Exception:
        ema20 = None

    try:
        ema50 = float(ind.ema(daily, 50, "close").drop_nulls().tail(1).item())
    except Exception:
        ema50 = None

    try:
        ema200 = float(ind.ema(daily, 200, "close").drop_nulls().tail(1).item())
    except Exception:
        ema200 = None

    stack = _ema_stack_label(ema20, ema50, ema200)
    hhhl = _hh_hl_confirm(daily)
    lhll = _lh_ll_confirm(daily)

    label, bias, score = _trend_from_stack_and_structure(stack, hhhl, lhll)

    return {
        "Trend_Strength_Score_D": float(round(score, 2)),
        "Trend_Strength_Label_D": label,
        "Trend_Bias_D": bias,
        "Trend_Ema_Stack_D": stack,
        "Trend_HHHL_Confirm_D": bool(hhhl),
        "Trend_LHLL_Confirm_D": bool(lhll),
        "Trend_Bars_D": int(daily.height),
    }
