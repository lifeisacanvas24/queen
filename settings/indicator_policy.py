#!/usr/bin/env python3
# ============================================================
# queen/settings/indicator_policy.py — v2.1 (Resolver + MinBars)
# ------------------------------------------------------------
# Resolves per-timeframe params from INDICATORS registry.
# Depends on:
#   • queen/settings/indicators.py   (data only; no back imports)
#   • queen/helpers/common.py        (timeframe_key utility)
#   • queen/settings/settings.py     (DEFAULTS for min-bars tuning)
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from queen.helpers.common import timeframe_key as _ctx_key_from_timeframe
from queen.settings import indicators as IND
from queen.settings import settings as S  # for DEFAULTS.* knobs


# ------------------------------------------------------------
# 🔎 Internal lookup (case-insensitive via indicators.get_block)
# ------------------------------------------------------------
def _find_block(name: str) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    return IND.get_block(name)


# ------------------------------------------------------------
# 🧭 Public API — params
# ------------------------------------------------------------
def params_for(indicator: str, timeframe: str) -> Dict[str, Any]:
    """Return parameters for (indicator, timeframe).

    Resolution order (no legacy fallbacks):
      contexts[ctx_key] merged over default  →  default  →  {}
    where ctx_key is produced by helpers.common.timeframe_key
      e.g. '15m' → 'intraday_15m', '1h' → 'hourly_1h', '1d' → 'daily'
    """
    block = _find_block(indicator)
    if not block:
        return {}

    default = dict(block.get("default") or {})
    contexts = block.get("contexts") or {}

    ctx_key = _ctx_key_from_timeframe(timeframe)
    if ctx_key in contexts:
        out = dict(default)
        out.update(contexts[ctx_key] or {})
        return out

    return default


def has_indicator(name: str) -> bool:
    return _find_block(name) is not None


def available_contexts(indicator: str) -> list[str]:
    blk = _find_block(indicator)
    if not blk:
        return []
    ctxs = blk.get("contexts") or {}
    return list(ctxs.keys())


def validate_policy() -> Dict[str, Any]:
    """Validate both registry and policy-level assumptions."""
    reg = IND.validate_registry()
    errs = list(reg.get("errors", []))
    return {"ok": reg.get("ok", False) and not errs, "errors": errs}


# ------------------------------------------------------------
# 📏 Min bars policy
# ------------------------------------------------------------
def _norm(s: str) -> str:
    return (s or "").strip().lower()


def min_bars_for_indicator(indicator: str, timeframe: str) -> int:
    """Settings-first min bars policy.

    Uses DEFAULTS.ALERTS.{INDICATOR_MIN_MULT, INDICATOR_MIN_FLOOR}
    and derives a canonical 'length' from known param names.
    Slight leniency for volume-style indicators.
    """
    alerts = (S.DEFAULTS or {}).get("ALERTS", {}) if hasattr(S, "DEFAULTS") else {}
    INDICATOR_MIN_MULT = int(alerts.get("INDICATOR_MIN_MULT", 3))
    INDICATOR_MIN_FLOOR = int(alerts.get("INDICATOR_MIN_FLOOR", 30))

    p = params_for(indicator, timeframe)
    length = (
        p.get("period")
        or p.get("length")
        or p.get("window")
        or p.get("rolling_window")
        or p.get("fast_period")
        or p.get("slow_period")
        or 14
    )
    try:
        length = int(length)
    except Exception:
        length = 14

    pname = _norm(indicator)
    if pname in {"vwap", "obv", "volume", "price_minus_vwap"}:
        return max(INDICATOR_MIN_FLOOR - 5, length * max(1, INDICATOR_MIN_MULT - 1))

    return max(INDICATOR_MIN_FLOOR, length * INDICATOR_MIN_MULT)


# ------------------------------------------------------------
# 🔧 Per-indicator static overrides (merged with DEFAULTS)
# ------------------------------------------------------------
_BASE_MIN_BARS = dict(getattr(S, "DEFAULTS", {}).get("INDICATOR_MIN_BARS", {}) or {})

INDICATOR_MIN_BARS = {
    **_BASE_MIN_BARS,
    # opinionated defaults; tune freely
    "ema": 60,
    "ema_slope": 60,
    "ema_cross": 120,
    "vwap": 40,
    "price_minus_vwap": 40,
}

# ------------------------------------------------------------
# 🧪 Self-test
# ------------------------------------------------------------
if __name__ == "__main__":
    print("validate_policy →", validate_policy())
    print("params_for(ADX_DMI, 15m) →", params_for("ADX_DMI", "15m"))
    print("min_bars_for_indicator(RSI, 1d) →", min_bars_for_indicator("RSI", "1d"))
    print("contexts(ADX_DMI) →", available_contexts("ADX_DMI"))
