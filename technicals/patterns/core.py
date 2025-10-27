#!/usr/bin/env python3
# ============================================================
# queen/technicals/patterns/core.py — v1.2 (Polars-native, Series-safe)
# Patterns: hammer, shooting_star, doji, bullish_engulfing, bearish_engulfing
# NOTE: This module ONLY defines detection functions + EXPORTS.
#       Lookback/metadata live in queen/settings/patterns.py.
# ============================================================
from __future__ import annotations

from typing import Any, Dict

import polars as pl
from queen.settings.patterns import required_lookback


# --------------------------
# Helpers
# --------------------------
def _false_series(n: int, name: str) -> pl.Series:
    return pl.Series(name=name, values=[False] * max(0, n), dtype=pl.Boolean)


def _max2(a: pl.Series, b: pl.Series) -> pl.Series:
    """Element-wise max(a, b) that returns a Series (not an Expr)."""
    # Build a tiny DF so we can use max_horizontal reliably, then return Series.
    return (
        pl.DataFrame({"_a": a, "_b": b})
        .select(pl.max_horizontal("_a", "_b").alias("_max"))
        .to_series()
        .rename(a.name or "_max")
    )


def _min2(a: pl.Series, b: pl.Series) -> pl.Series:
    """Element-wise min(a, b) that returns a Series (not an Expr)."""
    return (
        pl.DataFrame({"_a": a, "_b": b})
        .select(pl.min_horizontal("_a", "_b").alias("_min"))
        .to_series()
        .rename(a.name or "_min")
    )


def _body(o: pl.Series, c: pl.Series) -> pl.Series:
    return (c - o).abs()


def _upper_wick(o: pl.Series, c: pl.Series, h: pl.Series) -> pl.Series:
    return h - _max2(o, c)


def _lower_wick(o: pl.Series, c: pl.Series, l: pl.Series) -> pl.Series:
    return _min2(o, c) - l


# --------------------------
# Patterns
# --------------------------
def detect_doji(df: pl.DataFrame, tolerance: float = 0.1, **_) -> pl.Series:
    """Doji: |close - open| <= tolerance * (high - low)."""
    name = "doji"
    if df.is_empty():
        return _false_series(0, name)

    rng = (df["high"] - df["low"]).abs().fill_null(0.0)
    body = (df["close"] - df["open"]).abs().fill_null(0.0)
    return (body <= (rng * float(tolerance))).fill_null(False).alias(name)


def hammer(
    df: pl.DataFrame,
    body_ratio: float = 2.0,
    upper_max_mult: float = 1.0,
    **_,
) -> pl.Series:
    """Hammer: long lower shadow, small body near high, small upper shadow."""
    name = "hammer"
    if df.is_empty():
        return _false_series(0, name)

    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body = _body(o, c)
    upper = _upper_wick(o, c, h)
    lower = _lower_wick(o, c, l)

    cond = (lower >= body_ratio * body) & (upper <= upper_max_mult * body) & (body > 0)
    return cond.fill_null(False).alias(name)


def shooting_star(
    df: pl.DataFrame,
    body_ratio: float = 2.0,
    lower_max_mult: float = 1.0,
    **_,
) -> pl.Series:
    """Shooting Star: long upper shadow, small body near low, small lower shadow."""
    name = "shooting_star"
    if df.is_empty():
        return _false_series(0, name)

    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body = _body(o, c)
    upper = _upper_wick(o, c, h)
    lower = _lower_wick(o, c, l)

    cond = (upper >= body_ratio * body) & (lower <= lower_max_mult * body) & (body > 0)
    return cond.fill_null(False).alias(name)


def bullish_engulfing(df: pl.DataFrame, require_wide: bool = True, **_) -> pl.Series:
    """Bullish Engulfing: previous red body fully engulfed by current green body."""
    name = "bullish_engulfing"
    n = df.height
    if n < 2:
        return _false_series(n, name)

    o, c = df["open"], df["close"]
    o1, c1 = o.shift(1), c.shift(1)

    prev_red = c1 < o1
    curr_green = c > o
    # current body fully contains previous body
    engulf = (o <= c1) & (c >= o1)

    cond = prev_red & curr_green & engulf
    if require_wide:
        prev_body = (c1 - o1).abs()
        curr_body = (c - o).abs()
        cond = cond & (curr_body > prev_body)

    # First row cannot be a 2-candle pattern, but shift() already handles it (nulls -> False)
    return cond.fill_null(False).alias(name)


def bearish_engulfing(df: pl.DataFrame, require_wide: bool = True, **_) -> pl.Series:
    """Bearish Engulfing: previous green body fully engulfed by current red body."""
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


# --------------------------
# Registry
# --------------------------
EXPORTS: Dict[str, Any] = {
    "doji": detect_doji,
    "hammer": hammer,
    "shooting_star": shooting_star,
    "bullish_engulfing": bullish_engulfing,
    "bearish_engulfing": bearish_engulfing,
    "required_lookback": required_lookback,
}
