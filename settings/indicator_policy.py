#!/usr/bin/env python3
# ============================================================
# queen/settings/indicator_policy.py — v2.3 (Resolver + MinBars)
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

__all__ = [
    "params_for",
    "has_indicator",
    "available_contexts",
    "validate_policy",
    "min_bars_for_indicator",
    "INDICATOR_MIN_BARS",
]

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

    Resolution order:
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
    return sorted(ctxs.keys())

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

def _alerts_defaults() -> dict:
    # Provide resilient defaults if DEFAULTS lacks ALERTS
    base = getattr(S, "DEFAULTS", {}) or {}
    alerts = base.get("ALERTS", {}) if isinstance(base, dict) else {}
    return {
        "INDICATOR_MIN_MULT": int(alerts.get("INDICATOR_MIN_MULT", 3)),
        "INDICATOR_MIN_FLOOR": int(alerts.get("INDICATOR_MIN_FLOOR", 30)),
    }

def _safe_int(v: Any, fallback: int) -> int:
    try:
        return int(v)
    except Exception:
        return fallback

def min_bars_for_indicator(indicator: str, timeframe: str) -> int:
    """Settings-first min bars policy.

    Uses DEFAULTS.ALERTS.{INDICATOR_MIN_MULT, INDICATOR_MIN_FLOOR}
    and derives a canonical 'length' from known param names.

    Special-cases:
      • EMA_CROSS → max(fast, slow)
      • MACD      → use slow_period
      • ICHIMOKU  → use max(tenkan, kijun, senkou_span_b)
      • Volume/VWAP family → slightly lenient
    """
    cfg = _alerts_defaults()
    mult = cfg["INDICATOR_MIN_MULT"]
    floor_ = cfg["INDICATOR_MIN_FLOOR"]

    p = params_for(indicator, timeframe)
    name = _norm(indicator)

    # Special derivations
    if name in {"ema_cross"}:
        length = max(_safe_int(p.get("fast", 20), 20), _safe_int(p.get("slow", 50), 50))
    elif name in {"macd"}:
        length = _safe_int(p.get("slow_period", 26), 26)
    elif name in {"ichimoku"}:
        length = max(
            _safe_int(p.get("tenkan", 9), 9),
            _safe_int(p.get("kijun", 26), 26),
            _safe_int(p.get("senkou_span_b", 52), 52),
        )
    else:
        length = (
            p.get("period")
            or p.get("length")
            or p.get("window")
            or p.get("rolling_window")
            or p.get("fast_period")
            or p.get("slow_period")
            or 14
        )
        length = _safe_int(length, 14)

    # Leniency for flow/volume/VWAP family
    if name in {"vwap", "obv", "volume", "price_minus_vwap", "chaikin", "mfi", "volume_chaikin"}:
        return max(floor_ - 5, length * max(1, mult - 1))

    return max(floor_, length * mult)

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
