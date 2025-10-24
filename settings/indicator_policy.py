#!/usr/bin/env python3
# ============================================================
# queen/settings/indicator_policy.py — v0.1
# Central policy for indicator params + min-bars (settings-driven)
# ============================================================
from __future__ import annotations

from typing import Any, Dict

from queen.settings import indicators as IND  # your file


def _norm(name: str) -> str:
    return (name or "").strip().lower()


def _ctx_key_from_timeframe(tf: str) -> str:
    tf = (tf or "").lower()
    if tf.endswith("m"):
        return f"intraday_{tf}"
    if tf.endswith("h"):
        return f"hourly_{tf}"
    if tf == "1d":
        return "daily"
    if tf == "1w":
        return "weekly"
    if tf == "1mo":
        return "monthly"
    return f"intraday_{tf}"  # safe default


def _find_conf_block(name: str) -> Dict[str, Any]:
    # Your INDICATORS uses uppercase keys ("RSI", "ATR", ...).
    # Make lookup case-insensitive.
    upper_map = {k.upper(): v for k, v in IND.INDICATORS.items()}
    return upper_map.get(name.upper(), {})


def params_for(indicator: str, timeframe: str) -> Dict[str, Any]:
    """Returns params for (indicator, timeframe), resolving:
    contexts[timeframe_key] -> default -> {}
    """
    conf = _find_conf_block(indicator)
    if not conf:
        return {}
    ctx_key = _ctx_key_from_timeframe(timeframe)
    contexts = conf.get("contexts", {})
    if ctx_key in contexts:
        # merge default with context override
        base = dict(conf.get("default") or {})
        base.update(contexts[ctx_key] or {})
        return base
    # fallback to default only
    return dict(conf.get("default") or {})


def min_bars_for_indicator(indicator: str, timeframe: str) -> int:
    """Settings-first min bars policy.
    If an indicator has a 'period' or a common length, we scale it.
    Otherwise fall back to reasonable defaults.
    """
    pname = _norm(indicator)
    p = params_for(indicator, timeframe)

    # Extract a canonical length/period if present
    length = (
        p.get("period")
        or p.get("window")
        or p.get("length")
        or p.get("rolling_window")
        or 14
    )

    try:
        length = int(length)
    except Exception:
        length = 14

    # Per-indicator tuning if needed
    if pname in {"rsi", "atr", "adx", "macd"}:
        return max(30, length * 3)

    if pname in {"vwap", "obv", "volume"}:
        # VWAP/OBV/Volume often need a little less
        return max(25, length * 2)

    # Generic fallback
    return max(30, length * 3)
