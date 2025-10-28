#!/usr/bin/env python3
# ============================================================
# queen/settings/indicator_policy.py — v0.3 (Settings-driven + TF-owned parsing)
# ============================================================
from __future__ import annotations

from typing import Any, Dict

from queen.settings import indicators as IND
from queen.settings import settings as S  # access DEFAULTS
from queen.settings import timeframes as TF  # single owner for tokens


def _norm(name: str) -> str:
    return (name or "").strip().lower()


def _ctx_key_from_timeframe(token: str) -> str:
    """Map any TF token to a context key, using TF as the single owner.

    minutes → 'intraday_{n}m'
    hours   → 'hourly_{n}h'
    days    → 'daily'
    weeks   → 'weekly'
    months  → 'monthly'
    """
    s = TF.normalize_tf(token)
    unit, n = TF.parse_tf(s)  # raises on bad input (good)
    if unit == "minutes":
        return f"intraday_{n}m"
    if unit == "hours":
        return f"hourly_{n}h"
    if unit == "days":
        return "daily"
    if unit == "weeks":
        return "weekly"
    if unit == "months":
        return "monthly"
    # extremely defensive fallback
    return f"intraday_{s}"


def _find_conf_block(name: str) -> Dict[str, Any]:
    # INDICATORS uses UPPERCASE keys — make lookup case-insensitive.
    upper_map = {k.upper(): v for k, v in IND.INDICATORS.items()}
    return upper_map.get((name or "").upper(), {})


def params_for(indicator: str, timeframe: str) -> Dict[str, Any]:
    """Return params for (indicator, timeframe).

    Resolution order:
      contexts[ctx_key] (merged over default) → default → {}
    """
    conf = _find_conf_block(indicator)
    if not conf:
        return {}
    ctx_key = _ctx_key_from_timeframe(timeframe)
    contexts = conf.get("contexts", {}) or {}
    if ctx_key in contexts:
        base = dict(conf.get("default") or {})
        base.update(contexts[ctx_key] or {})
        return base
    return dict(conf.get("default") or {})


def min_bars_for_indicator(indicator: str, timeframe: str) -> int:
    """Settings-first min bars policy.
    - Uses DEFAULTS.ALERTS.{INDICATOR_MIN_MULT, INDICATOR_MIN_FLOOR}
    - Derives a canonical 'length' from known param names.
    - Light per-indicator tuning (volume-style need slightly fewer bars).
    """
    alerts = S.DEFAULTS.get("ALERTS", {})
    INDICATOR_MIN_MULT = int(alerts.get("INDICATOR_MIN_MULT", 3))
    INDICATOR_MIN_FLOOR = int(alerts.get("INDICATOR_MIN_FLOOR", 30))

    pname = _norm(indicator)
    p = params_for(indicator, timeframe)

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

    if pname in {"vwap", "obv", "volume"}:
        return max(INDICATOR_MIN_FLOOR - 5, length * max(1, INDICATOR_MIN_MULT - 1))

    return max(INDICATOR_MIN_FLOOR, length * INDICATOR_MIN_MULT)


# ------------------------------------------------------------
# Per-indicator min bars overrides (merged with DEFAULTS)
# ------------------------------------------------------------
_BASE_MIN_BARS = dict(S.DEFAULTS.get("INDICATOR_MIN_BARS", {}) or {})

INDICATOR_MIN_BARS = {
    **_BASE_MIN_BARS,
    # light opinionated defaults; tweak freely
    "ema": 60,
    "ema_slope": 60,
    "ema_cross": 120,  # slow=50 → ~100–150 bars is reasonable
    "vwap": 40,
    "price_minus_vwap": 40,
}

if __name__ == "__main__":
    print("params_for(RSI, 1d) →", params_for("RSI", "1d"))
    print("min_bars_for_indicator(RSI, 1d) →", min_bars_for_indicator("RSI", "1d"))
    print("INDICATOR_MIN_BARS →", INDICATOR_MIN_BARS)
