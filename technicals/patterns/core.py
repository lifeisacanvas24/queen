#!/usr/bin/env python3
# ============================================================
# queen/technicals/patterns/core.py — v1.3 (Polars-native, Bible-aligned)
# ------------------------------------------------------------
# Core Japanese candlestick detectors (Series-safe):
#   • doji
#   • hammer (umbrella bullish)
#   • shooting_star (umbrella bearish)
#   • bullish_engulfing
#   • bearish_engulfing
#
# NOTE:
#   • This module ONLY defines raw detection functions.
#   • Lookback / group (REVERSAL vs CONTINUATION) / credibility
#     live in queen/settings/patterns.py and Bible v10.5.
#   • Aggregation & naming for stacks live in patterns/runner.py
#     and downstream fusion layers.
# ============================================================
from __future__ import annotations

from typing import Any, Dict

import polars as pl

from queen.settings.patterns import required_lookback


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _false_series(n: int, name: str) -> pl.Series:
    """Utility: return a Boolean Series of length n filled with False."""
    return pl.Series(name=name, values=[False] * max(0, n), dtype=pl.Boolean)


def _max2(a: pl.Series, b: pl.Series) -> pl.Series:
    """Element-wise max(a, b) as a Series (Polars-version safe)."""
    return (
        pl.DataFrame({"_a": a, "_b": b})
        .select(pl.max_horizontal("_a", "_b").alias("_max"))
        .to_series()
        .rename(a.name or "_max")
    )


def _min2(a: pl.Series, b: pl.Series) -> pl.Series:
    """Element-wise min(a, b) as a Series (Polars-version safe)."""
    return (
        pl.DataFrame({"_a": a, "_b": b})
        .select(pl.min_horizontal("_a", "_b").alias("_min"))
        .to_series()
        .rename(a.name or "_min")
    )


def _body(o: pl.Series, c: pl.Series) -> pl.Series:
    """Absolute real body size."""
    return (c - o).abs()


def _upper_wick(o: pl.Series, c: pl.Series, h: pl.Series) -> pl.Series:
    """Upper shadow length."""
    return h - _max2(o, c)


def _lower_wick(o: pl.Series, c: pl.Series, l: pl.Series) -> pl.Series:
    """Lower shadow length."""
    return _min2(o, c) - l


# ------------------------------------------------------------
# Pattern: Doji
# ------------------------------------------------------------
def detect_doji(df: pl.DataFrame, tolerance: float = 0.1, **_: Any) -> pl.Series:
    """Doji:
        |close - open| <= tolerance * (high - low).

    Bible interpretation:
        • Indecision / balance bar.
        • Acts as context for reversals (e.g., doji near CPR edge, after trend).
    """
    name = "doji"
    if df.is_empty():
        return _false_series(0, name)

    rng = (df["high"] - df["low"]).abs().fill_null(0.0)
    body = (df["close"] - df["open"]).abs().fill_null(0.0)

    cond = body <= (rng * float(tolerance))
    return cond.fill_null(False).alias(name)


# ------------------------------------------------------------
# Pattern: Hammer (Umbrella Bullish)
# ------------------------------------------------------------
def hammer(
    df: pl.DataFrame,
    body_ratio: float = 2.0,
    upper_max_mult: float = 1.0,
    **_: Any,
) -> pl.Series:
    """Hammer:
        • Long lower shadow
        • Small body near the high
        • Small upper shadow

    Bible:
        • Bullish reversal *candidate*.
        • Context (trend down, near support / CPR, volume, RSI regime) handled
          in scoring layers, not here.
    """
    name = "hammer"
    if df.is_empty():
        return _false_series(0, name)

    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body = _body(o, c)
    upper = _upper_wick(o, c, h)
    lower = _lower_wick(o, c, l)

    cond = (lower >= body_ratio * body) & (upper <= upper_max_mult * body) & (body > 0)
    return cond.fill_null(False).alias(name)


# ------------------------------------------------------------
# Pattern: Shooting Star (Umbrella Bearish)
# ------------------------------------------------------------
def shooting_star(
    df: pl.DataFrame,
    body_ratio: float = 2.0,
    lower_max_mult: float = 1.0,
    **_: Any,
) -> pl.Series:
    """Shooting Star:
        • Long upper shadow
        • Small body near the low
        • Small lower shadow

    Bible:
        • Bearish reversal *candidate* (especially near resistance/CPR R1–R2).
    """
    name = "shooting_star"
    if df.is_empty():
        return _false_series(0, name)

    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body = _body(o, c)
    upper = _upper_wick(o, c, h)
    lower = _lower_wick(o, c, l)

    cond = (upper >= body_ratio * body) & (lower <= lower_max_mult * body) & (body > 0)
    return cond.fill_null(False).alias(name)


# ------------------------------------------------------------
# Pattern: Bullish Engulfing
# ------------------------------------------------------------
def bullish_engulfing(df: pl.DataFrame, require_wide: bool = True, **_: Any) -> pl.Series:
    """Bullish Engulfing:
    • Previous candle: red body
    • Current candle: green body that fully engulfs previous body.
    • Optionally require current body > previous body (stronger signal).
    """
    name = "bullish_engulfing"
    n = df.height
    if n < 2:
        return _false_series(n, name)

    o, c = df["open"], df["close"]
    o1, c1 = o.shift(1), c.shift(1)

    prev_red = c1 < o1
    curr_green = c > o
    engulf = (o <= c1) & (c >= o1)  # current body fully contains previous body

    cond = prev_red & curr_green & engulf
    if require_wide:
        prev_body = (c1 - o1).abs()
        curr_body = (c - o).abs()
        cond = cond & (curr_body > prev_body)

    return cond.fill_null(False).alias(name)


# ------------------------------------------------------------
# Pattern: Bearish Engulfing
# ------------------------------------------------------------
def bearish_engulfing(df: pl.DataFrame, require_wide: bool = True, **_: Any) -> pl.Series:
    """Bearish Engulfing:
    • Previous candle: green body
    • Current candle: red body that fully engulfs previous body.
    • Optionally require current body > previous body (stronger signal).
    """
    name = "bearish_engulfing"
    n = df.height
    if n < 2:
        return _false_series(n, name)

    o, c = df["open"], df["close"]
    o1, c1 = o.shift(1), c.shift(1)

    prev_green = c1 > o1
    curr_red = c < o
    engulf = (o >= c1) & (c <= o1)

    cond = prev_green & curr_red & engulf
    if require_wide:
        prev_body = (c1 - o1).abs()
        curr_body = (c - o).abs()
        cond = cond & (curr_body > prev_body)

    return cond.fill_null(False).alias(name)


# ------------------------------------------------------------
# Registry (used by runner + registry + settings/patterns)
# ------------------------------------------------------------
EXPORTS: Dict[str, Any] = {
    # raw detectors
    "doji": detect_doji,
    "hammer": hammer,
    "shooting_star": shooting_star,
    "bullish_engulfing": bullish_engulfing,
    "bearish_engulfing": bearish_engulfing,
    # metadata hook
    "required_lookback": required_lookback,
}

__all__ = ["EXPORTS"]
