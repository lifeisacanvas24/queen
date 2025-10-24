#!/usr/bin/env python3
# ============================================================
# queen/technicals/patterns/core.py — v0.4 (clean API)
# ============================================================
from __future__ import annotations

from typing import Any, Dict

import polars as pl
from queen.settings import patterns as PAT


def required_lookback(pattern_name: str, timeframe_key: str) -> int:
    """Return the min lookback candles for a pattern & timeframe."""
    name = pattern_name.lower()
    catalog: Dict[str, dict] = {**PAT.JAPANESE, **PAT.CUMULATIVE}
    spec = catalog.get(name, {})
    ctx = spec.get("contexts", {})
    if timeframe_key in ctx:
        return int(ctx[timeframe_key].get("lookback", 0))
    return max((int(v.get("lookback", 0)) for v in ctx.values()), default=0)


# --------------------------
# Pattern implementations
# --------------------------
def detect_doji(df: pl.DataFrame, tol: float = 0.1, **kwargs) -> pl.Series:
    """Detect Doji — close ≈ open within tolerance % of range."""
    if "tolerance" in kwargs and isinstance(kwargs["tolerance"], (int, float)):
        tol = float(kwargs["tolerance"])
    if df.is_empty():
        return pl.Series([], dtype=pl.Boolean)

    rng = (df["high"] - df["low"]).abs().fill_null(0.0)
    body = (df["close"] - df["open"]).abs().fill_null(0.0)
    return (body <= (rng * tol)).fill_null(False)


def detect_hammer(df: pl.DataFrame, body_mult: float = 2.0, **kwargs) -> pl.Series:
    """Very simple hammer heuristic (placeholder)."""
    if df.is_empty():
        return pl.Series([], dtype=pl.Boolean)
    body = (df["close"] - df["open"]).abs()
    upper = df["high"] - df[["open", "close"]].max(axis=1)
    lower = df[["open", "close"]].min(axis=1) - df["low"]
    return (lower > body * body_mult) & (upper < body)


# Exported registry (canonical name → callable)
EXPORTS: Dict[str, Any] = {
    "doji": detect_doji,
    "hammer": detect_hammer,
}
