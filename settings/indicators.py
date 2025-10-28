#!/usr/bin/env python3
# ============================================================
# queen/settings/indicators.py — v2.1 (Data-only registry)
# ------------------------------------------------------------
# Single source of truth for indicator default/contexts.
# No imports from indicator_policy to avoid circular imports.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Valid context keys used across the project
_VALID_CONTEXTS = {
    "intraday_5m",
    "intraday_10m",
    "intraday_15m",
    "intraday_30m",
    "hourly_1h",
    "daily",
    "weekly",
    "monthly",
}

# ------------------------------------------------------------------
# 📦 INDICATORS — add/extend here (names are case-insensitive later)
# ------------------------------------------------------------------
INDICATORS: Dict[str, Dict[str, Any]] = {
    # ===================== Core momentum/overlays ======================
    "RSI": {
        "default": {"period": 14, "overbought": 70, "oversold": 30, "signal_smooth": 3},
        "contexts": {
            "intraday_5m": {"period": 14, "signal_smooth": 3},
            "intraday_15m": {"period": 14, "signal_smooth": 3},
            "hourly_1h": {"period": 14, "signal_smooth": 5},
            "daily": {"period": 14, "signal_smooth": 5},
            "weekly": {"period": 14, "signal_smooth": 7},
            "monthly": {"period": 14, "signal_smooth": 7},
        },
        "_note": "RSI cross 50–65 for bullish bias, 35–50 for bearish bias confirmation.",
    },
    "ATR": {
        "default": {"period": 14, "multiplier": 1.5},
        "contexts": {
            "intraday_5m": {"period": 14, "multiplier": 1.2},
            "intraday_15m": {"period": 14, "multiplier": 1.5},
            "intraday_30m": {"period": 14, "multiplier": 1.6},
            "hourly_1h": {"period": 14, "multiplier": 1.6},
            "daily": {"period": 14, "multiplier": 2.0},
            "weekly": {"period": 14, "multiplier": 2.5},
            "monthly": {"period": 14, "multiplier": 3.0},
        },
        "_note": "ATR for volatility normalization, stops, target ladders.",
    },
    "EMA": {
        "default": {"length": 21},
        "contexts": {
            "intraday_5m": {"length": 20},
            "intraday_15m": {"length": 20},
            "daily": {"length": 21},
            "weekly": {"length": 21},
        },
        "_note": "Exponential moving average.",
    },
    "EMA_SLOPE": {
        "default": {"length": 21, "periods": 1},
        "contexts": {
            "intraday_5m": {"length": 20, "periods": 1},
            "daily": {"length": 21, "periods": 1},
        },
        "_note": "Slope of EMA(length) over N periods.",
    },
    "EMA_CROSS": {
        "default": {"fast": 20, "slow": 50},
        "contexts": {
            "intraday_5m": {"fast": 20, "slow": 50},
            "daily": {"fast": 20, "slow": 50},
        },
        "_note": "EMA fast/slow (use crosses_* 0 to detect cross).",
    },
    "MACD": {
        "default": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        "contexts": {
            "intraday_15m": {"fast_period": 8, "slow_period": 21, "signal_period": 9},
            "hourly_1h": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            "daily": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            "weekly": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        },
        "_note": "MACD histogram slope used in SPS/MCS anticipation.",
    },
    # ========================= Volume/flow =============================
    "VWAP": {
        "default": {"anchored": False, "rolling_window": 20},
        "contexts": {
            "intraday_5m": {"anchored": False, "rolling_window": 15},
            "intraday_15m": {"anchored": False, "rolling_window": 20},
            "hourly_1h": {"anchored": True, "rolling_window": 25},
            "daily": {"anchored": True, "rolling_window": 30},
            "weekly": {"anchored": True, "rolling_window": 40},
        },
        "_note": "Rolling VWAP for live; anchored VWAP for swing confirms.",
    },
    "PRICE_MINUS_VWAP": {
        "default": {},
        "contexts": {"intraday_5m": {}},
        "_note": "Close - VWAP (cross 0 → reclaim/loss).",
    },
    "OBV": {
        "default": {"smoothing": "EMA", "window": 20},
        "contexts": {
            "intraday_5m": {"smoothing": "EMA", "window": 10},
            "intraday_15m": {"smoothing": "EMA", "window": 20},
            "hourly_1h": {"smoothing": "EMA", "window": 30},
            "daily": {"smoothing": "EMA", "window": 40},
            "weekly": {"smoothing": "EMA", "window": 50},
        },
        "_note": "OBV slope + HH/LL sequences feed MCS/CPS.",
    },
    "VOLUME": {
        "default": {"vdu_factor": 0.5, "spike_factor": 1.5, "average_window": 10},
        "contexts": {
            "intraday_5m": {
                "vdu_factor": 0.5,
                "spike_factor": 1.5,
                "average_window": 10,
            },
            "intraday_15m": {
                "vdu_factor": 0.5,
                "spike_factor": 1.5,
                "average_window": 10,
            },
            "hourly_1h": {"vdu_factor": 0.6, "spike_factor": 1.4, "average_window": 10},
            "daily": {"vdu_factor": 0.6, "spike_factor": 1.3, "average_window": 10},
            "weekly": {"vdu_factor": 0.6, "spike_factor": 1.2, "average_window": 10},
        },
        "_note": "VDU (dry-up) & spike detection.",
    },
    # ========================= Trend strength ==========================
    "ADX_DMI": {
        "default": {
            "period": 14,
            "threshold_trend": 25,
            "threshold_consolidation": 15,
        },
        "contexts": {
            "intraday_5m": {"period": 14},
            "intraday_10m": {"period": 14},
            "intraday_15m": {"period": 14},
            "intraday_30m": {"period": 14},
            "hourly_1h": {"period": 14},
            "daily": {"period": 14},
        },
        "_note": "Used by adx_dmi() and lbx score.",
    },
    # ========================= Breadth engines =========================
    "BREADTH_CUMULATIVE": {
        "default": {
            "window": 10,
            "threshold_bullish": 0.2,
            "threshold_bearish": -0.2,
        },
        "contexts": {
            "intraday_5m": {
                "window": 8,
                "threshold_bullish": 0.25,
                "threshold_bearish": -0.25,
            },
            "intraday_15m": {
                "window": 10,
                "threshold_bullish": 0.2,
                "threshold_bearish": -0.2,
            },
            "hourly_1h": {
                "window": 12,
                "threshold_bullish": 0.15,
                "threshold_bearish": -0.15,
            },
            "daily": {
                "window": 14,
                "threshold_bullish": 0.1,
                "threshold_bearish": -0.1,
            },
            "weekly": {
                "window": 20,
                "threshold_bullish": 0.1,
                "threshold_bearish": -0.1,
            },
        },
        "_note": "Rolling CMV/SPS mean → persistence & bias.",
    },
    "BREADTH_MOMENTUM": {
        "default": {
            "fast_window": 5,
            "slow_window": 20,
            "threshold_expand": 0.15,
            "threshold_contract": -0.15,
            "clip_abs": 1.0,
        },
        "contexts": {
            "intraday_5m": {"fast_window": 5, "slow_window": 21},
            "intraday_15m": {"fast_window": 5, "slow_window": 20},
            "daily": {"fast_window": 8, "slow_window": 34},
        },
        "_note": "Short-term expansion/contraction of composite breadth.",
    },
    # ========================= Pattern / structure =====================
    "CPR": {
        "default": {"pivot_method": "classic", "compression_threshold": 0.3},
        "contexts": {
            "intraday_15m": {"pivot_method": "classic", "compression_threshold": 0.3},
            "hourly_1h": {"pivot_method": "classic", "compression_threshold": 0.25},
            "daily": {"pivot_method": "classic", "compression_threshold": 0.2},
        },
        "_note": "CPR compression → SPS setups.",
    },
    "ICHIMOKU": {
        "default": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52, "displacement": 26},
        "contexts": {
            "intraday_15m": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52},
            "hourly_1h": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52},
            "daily": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52},
            "weekly": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52},
        },
        "_note": "Tenkan/Kijun + Span confluence.",
    },
    "HEIKINASHI": {
        "default": {"smoothing": "EMA", "window": 3},
        "contexts": {
            "intraday_15m": {"smoothing": "EMA", "window": 3},
            "hourly_1h": {"smoothing": "EMA", "window": 3},
            "daily": {"smoothing": "EMA", "window": 3},
            "weekly": {"smoothing": "EMA", "window": 3},
        },
        "_note": "Heikin-Ashi smoothing for CPS.",
    },
}


# ------------------------------------------------------------------
# 🔎 Tiny helpers (local-only; safe for import anywhere)
# ------------------------------------------------------------------
def list_indicator_names() -> List[str]:
    """Return registry keys as-is (case preserved)."""
    return list(INDICATORS.keys())


def get_block(name: str) -> Optional[Dict[str, Any]]:
    """Case-insensitive access to an indicator block."""
    if not name:
        return None
    # exact first
    if name in INDICATORS:
        return INDICATORS[name]
    # case-insensitive fallback
    up = name.upper()
    for k, v in INDICATORS.items():
        if k.upper() == up:
            return v
    return None


def validate_registry() -> Dict[str, Any]:
    """Light schema check for INDICATORS layout."""
    errs: List[str] = []
    for ind_name, block in INDICATORS.items():
        if not isinstance(block, dict):
            errs.append(f"{ind_name}: must be dict")
            continue

        # default optional dict
        if "default" in block and not isinstance(block["default"], dict):
            errs.append(f"{ind_name}: 'default' must be dict if present")

        # contexts optional dict of dicts with valid keys
        ctxs = block.get("contexts", {})
        if ctxs is not None:
            if not isinstance(ctxs, dict):
                errs.append(f"{ind_name}: 'contexts' must be dict if present")
            else:
                for ctx_key, ctx in ctxs.items():
                    if ctx_key not in _VALID_CONTEXTS:
                        errs.append(f"{ind_name}: unknown context '{ctx_key}'")
                    elif not isinstance(ctx, dict):
                        errs.append(f"{ind_name}.{ctx_key}: context must be dict")

    return {"ok": not errs, "errors": errs, "count": len(INDICATORS)}
