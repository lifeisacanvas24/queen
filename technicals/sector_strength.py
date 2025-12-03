#!/usr/bin/env python3
# ============================================================
# queen/technicals/sector_strength.py — v1.1
# ------------------------------------------------------------
# Sector-level Trend Strength (Daily by compression)
# ============================================================

from __future__ import annotations

from typing import Optional, Dict, Any

import polars as pl

from queen.helpers.market import MARKET_TZ_KEY
from queen.technicals.indicators import core as ind


def _compress_to_daily(df: pl.DataFrame) -> pl.DataFrame:
    """Convert intraday OHLCV to daily OHLC."""
    if df.is_empty() or "timestamp" not in df.columns:
        return pl.DataFrame()

    return (
        df.with_columns(
            pl.col("timestamp")
            .dt.convert_time_zone(MARKET_TZ_KEY)
            .dt.date()
            .alias("d")
        )
        .sort("timestamp")
        .group_by("d")
        .agg(
            pl.col("open").first().alias("open"),
            pl.col("high").max().alias("high"),
            pl.col("low").min().alias("low"),
            pl.col("close").last().alias("close"),
        )
        .sort("d")
    )


def _trend_structure(daily: pl.DataFrame) -> str:
    """Simple HH/HL vs LH/LL structure over last 3 bars."""
    if daily.height < 4:
        return "Range"

    try:
        h = daily["high"].to_list()
        l = daily["low"].to_list()
        c = daily["close"].to_list()

        hh = h[-1] > h[-2] and h[-2] > h[-3]
        hl = l[-1] > l[-2] and l[-2] > l[-3]

        lh = h[-1] < h[-2] and h[-2] < h[-3]
        ll = l[-1] < l[-2] and l[-2] < l[-3]

        if hh and hl:
            return "Up"
        if lh and ll:
            return "Down"
        return "Range"
    except Exception:
        return "Range"


def _ema_alignment(daily: pl.DataFrame) -> str:
    """EMA(20/50/200) alignment trend."""
    if daily.height < 250:
        return "Range"

    try:
        e20 = ind.ema(daily, 20, "close").drop_nulls().tail(1).item()
        e50 = ind.ema(daily, 50, "close").drop_nulls().tail(1).item()
        e200 = ind.ema(daily, 200, "close").drop_nulls().tail(1).item()
    except Exception:
        return "Range"

    if e20 > e50 > e200:
        return "Up"
    if e20 < e50 < e200:
        return "Down"
    return "Range"


def _rsi_momentum(daily: pl.DataFrame) -> str:
    """RSI(14)-based momentum classification."""
    if daily.height < 20:
        return "Neutral"

    try:
        r = daily["close"].cast(pl.Float64)
        rsi_now = ind.rsi_last(r, 14)
        if rsi_now is None:
            return "Neutral"

        if rsi_now >= 60:
            return "Bullish"
        if rsi_now <= 40:
            return "Bearish"
        return "Neutral"
    except Exception:
        return "Neutral"


def compute_sector_strength(df: pl.DataFrame) -> Dict[str, Any]:
    """Return sector trend/bias/score from intraday DF."""
    if df.is_empty() or df.height < 20:
        return {
            "sector_score": None,
            "sector_bias": None,
            "sector_trend": None,
        }

    daily = _compress_to_daily(df)
    if daily.is_empty():
        return {
            "sector_score": None,
            "sector_bias": None,
            "sector_trend": None,
        }

    struct = _trend_structure(daily)
    ema_trend = _ema_alignment(daily)
    rsi_m = _rsi_momentum(daily)

    score = 0.0

    if ema_trend == "Up":
        score += 5
    elif ema_trend == "Down":
        score -= 5

    if struct == "Up":
        score += 3
    elif struct == "Down":
        score -= 3

    if rsi_m == "Bullish":
        score += 2
    elif rsi_m == "Bearish":
        score -= 2

    score = max(-10, min(10, score))

    if score >= 7:
        bias = "Bullish"
        label = "Strong Bullish"
    elif score >= 3:
        bias = "Bullish"
        label = "Bullish"
    elif score <= -7:
        bias = "Bearish"
        label = "Strong Bearish"
    elif score <= -3:
        bias = "Bearish"
        label = "Bearish"
    else:
        bias = "Neutral"
        label = "Range"

    return {
        "sector_score": score,
        "sector_bias": bias,
        "sector_trend": label,
    }
