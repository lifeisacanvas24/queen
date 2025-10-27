#!/usr/bin/env python3
# ============================================================
# queen/alerts/evaluator.py — v0.8
# Price | Indicator | Pattern evaluators (Polars)
# - filters non-indicator kwargs (no 'min_bars' leak)
# - friendlier "unknown pattern" error (lists available)
# - returns useful meta for UI/debug
# ============================================================
from __future__ import annotations

from typing import Any, Dict, Tuple

import polars as pl
from queen.alerts.rules import Rule
from queen.helpers.common import indicator_call_kwargs
from queen.technicals.patterns.core import EXPORTS as PATTERNS
from queen.technicals.registry import get_indicator

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


# Only pass indicator-native kwargs to registry functions
def _indicator_kwargs(rule: Rule) -> dict:
    blocked = {
        "min_bars",
        "need",
        "lookback",
        "context",
        "context_key",
        "timeframe",
        "tf",
    }
    return {k: v for k, v in (rule.params or {}).items() if k not in blocked}


def _last_two(series: pl.Series) -> Tuple[Any, Any]:
    s = series.drop_nulls()
    if s.len() < 2:
        return (s[-1] if s.len() else None, None)
    return s[-1], s[-2]


def _cmp(op: str, a: float, b: float) -> bool:
    if op == "lt":
        return a < b
    if op == "gt":
        return a > b
    if op == "eq":
        return a == b
    raise ValueError(f"Unsupported op: {op}")


def _cross(op: str, s: pl.Series, level: float) -> Tuple[bool, Dict[str, Any]]:
    """Cross detection against a horizontal level (returns ok, meta)."""
    cur, prev = _last_two(s)
    if cur is None or prev is None:
        return False, {
            "reason": "insufficient_data",
            "last2": [prev, cur],
            "level": level,
        }

    was_below = prev < level
    is_above = cur > level
    was_above = prev > level
    is_below = cur < level

    if op == "crosses_above":
        return (was_below and is_above), {
            "last2": [float(prev), float(cur)],
            "level": float(level),
        }
    if op == "crosses_below":
        return (was_above and is_below), {
            "last2": [float(prev), float(cur)],
            "level": float(level),
        }
    raise ValueError(f"Unsupported cross op: {op}")


# ------------------------------------------------------------------
# Evaluators
# ------------------------------------------------------------------


def eval_price(df: pl.DataFrame, rule: Rule) -> Tuple[bool, Dict[str, Any]]:
    if df.is_empty() or "close" not in df.columns:
        return False, {"reason": "no_data"}

    close = df["close"]
    cur = close[-1] if close.len() else None
    if cur is None:
        return False, {"reason": "no_data"}

    if rule.op in ("lt", "gt", "eq"):
        ok = _cmp(str(rule.op), float(cur), float(rule.value))
        return ok, {
            "kind": "price",
            "close": float(cur),
            "op": rule.op,
            "value": rule.value,
        }

    if rule.op in ("crosses_above", "crosses_below"):
        ok, meta = _cross(str(rule.op), close, float(rule.value))
        meta.update({"kind": "price", "op": rule.op})
        return ok, meta

    raise ValueError(f"Unsupported op: {rule.op}")


def eval_pattern(df: pl.DataFrame, rule: Rule) -> Tuple[bool, Dict[str, Any]]:
    name = (rule.pattern or "").lower()
    fn = PATTERNS.get(name)
    if not fn:
        available = ", ".join(sorted(PATTERNS.keys()))
        raise ValueError(f"Unknown pattern: {name}. Available: {available}")

    mask = fn(df, **(rule.params or {}))
    if not isinstance(mask, pl.Series) or mask.len() == 0:
        return False, {"reason": "pattern_empty"}

    ok = bool(mask[-1])
    return ok, {"kind": "pattern", "pattern": name, "value": ok}


def eval_indicator(df: pl.DataFrame, rule: Rule) -> Tuple[bool, Dict[str, Any]]:
    name = (rule.indicator or "").lower()
    try:
        fn = get_indicator(name)  # -> Series or DataFrame
    except KeyError:
        raise ValueError(f"Unknown indicator: {name}")

    # Filter out policy knobs like min_bars before calling indicator fn
    series_or_df = fn(df, **indicator_call_kwargs(rule.params))

    if isinstance(series_or_df, pl.Series):
        series = series_or_df
        colname = series.name or name
    elif isinstance(series_or_df, pl.DataFrame):
        # Take the first numeric column as the indicator series
        num_cols = [
            c
            for c in series_or_df.columns
            if pl.datatypes.is_numeric(series_or_df[c].dtype)
        ]
        if not num_cols:
            return False, {"reason": "indicator_no_numeric_output", "indicator": name}
        colname = num_cols[0]
        series = series_or_df[colname]
    else:
        return False, {"reason": "indicator_bad_output", "indicator": name}

    if series.len() == 0:
        return False, {"reason": "indicator_empty", "indicator": name}

    if rule.op in ("lt", "gt", "eq"):
        cur = series.drop_nulls()
        if cur.len() == 0:
            return False, {"reason": "indicator_all_nulls", "indicator": name}
        ok = _cmp(str(rule.op), float(cur[-1]), float(rule.value))
        return ok, {
            "kind": "indicator",
            "indicator": name,
            "op": rule.op,
            "value": rule.value,
            "last": float(cur[-1]),
            "series": colname,
        }

    if rule.op in ("crosses_above", "crosses_below"):
        ok, meta = _cross(str(rule.op), series, float(rule.value))
        meta.update(
            {"kind": "indicator", "indicator": name, "op": rule.op, "series": colname}
        )
        return ok, meta

    raise ValueError(f"Unsupported op: {rule.op}")


def eval_rule(rule: Rule, df: pl.DataFrame) -> Tuple[bool, Dict[str, Any]]:
    """Top-level dispatcher. Returns (ok, meta)."""
    kind = (rule.kind or "").lower()
    if kind == "price":
        return eval_price(df, rule)
    if kind == "pattern":
        return eval_pattern(df, rule)
    if kind == "indicator":
        return eval_indicator(df, rule)
    raise ValueError(f"Unsupported rule kind: {rule.kind}")
