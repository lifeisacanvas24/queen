#!/usr/bin/env python3
# ============================================================
# queen/settings/indicators.py — Indicator Parameter Config (v8.1)
# Case-insensitive access + validation (forward-only)
# ============================================================
from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# 📊 Indicator Parameter Map
# NOTE: keys are uppercase by convention; lookups are case-insensitive.
# ------------------------------------------------------------
INDICATORS: Dict[str, Dict[str, Any]] = {
    # ========================================================
    # RSI (Relative Strength Index)
    # ========================================================
    "RSI": {
        "default": {"period": 14, "overbought": 70, "oversold": 30, "signal_smooth": 3},
        "KELTNER": {
            "ema_period": 20,
            "atr_mult": 2.0,
            "atr_period": 14,
            "squeeze_window": 10,
            "squeeze_threshold": 0.8,
            "expansion_threshold": 1.2,
        },
        "VOL_FUSION": {
            "normalize_window": 50,
            "weight_keltner": 0.7,
            "weight_atr": 0.3,
            "bias_threshold": 0.6,
        },
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
            "_note": "Rolling CMV/SPS mean for breadth persistence and bias polarity detection.",
        },
        "BREADTH_MOMENTUM": {
            "default": {
                "roc_window": 5,
                "smooth_window": 3,
                "threshold_expand": 0.15,
                "threshold_contract": -0.15,
            },
            "contexts": {
                "intraday_5m": {
                    "roc_window": 3,
                    "smooth_window": 2,
                    "threshold_expand": 0.2,
                    "threshold_contract": -0.2,
                },
                "intraday_15m": {
                    "roc_window": 5,
                    "smooth_window": 3,
                    "threshold_expand": 0.15,
                    "threshold_contract": -0.15,
                },
                "hourly_1h": {
                    "roc_window": 7,
                    "smooth_window": 3,
                    "threshold_expand": 0.1,
                    "threshold_contract": -0.1,
                },
                "daily": {
                    "roc_window": 10,
                    "smooth_window": 5,
                    "threshold_expand": 0.08,
                    "threshold_contract": -0.08,
                },
                "weekly": {
                    "roc_window": 15,
                    "smooth_window": 7,
                    "threshold_expand": 0.05,
                    "threshold_contract": -0.05,
                },
            },
            "_note": "Measures short-term momentum shifts in composite breadth (CMV + SPS rate of change).",
        },
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
    # ========================================================
    # ATR (Average True Range)
    # ========================================================
    "ATR": {
        "default": {"period": 14, "multiplier": 1.5},
        "contexts": {
            "intraday_5m": {"period": 14, "multiplier": 1.2},
            "intraday_15m": {"period": 14, "multiplier": 1.5},
            "hourly_1h": {"period": 14, "multiplier": 1.6},
            "daily": {"period": 14, "multiplier": 2.0},
            "weekly": {"period": 14, "multiplier": 2.5},
            "monthly": {"period": 14, "multiplier": 3.0},
        },
        "_note": "ATR used for volatility normalization, stop-loss zones, and target laddering.",
    },
    # ========================================================
    # VWAP
    # ========================================================
    "VWAP": {
        "default": {"anchored": False, "rolling_window": 20},
        "contexts": {
            "intraday_5m": {"anchored": False, "rolling_window": 15},
            "intraday_15m": {"anchored": False, "rolling_window": 20},
            "hourly_1h": {"anchored": True, "rolling_window": 25},
            "daily": {"anchored": True, "rolling_window": 30},
            "weekly": {"anchored": True, "rolling_window": 40},
        },
        "_note": "Rolling VWAP preferred for live; anchored VWAP for swing confirmation.",
    },
    # ========================================================
    # OBV (On-Balance Volume)
    # ========================================================
    "OBV": {
        "default": {"smoothing": "EMA", "window": 20},
        "contexts": {
            "intraday_5m": {"smoothing": "EMA", "window": 10},
            "intraday_15m": {"smoothing": "EMA", "window": 20},
            "hourly_1h": {"smoothing": "EMA", "window": 30},
            "daily": {"smoothing": "EMA", "window": 40},
            "weekly": {"smoothing": "EMA", "window": 50},
        },
        "_note": "OBV slope and HH/LL sequences drive MCS and CPS scoring.",
    },
    # ========================================================
    # ADX (Trend Strength)
    # ========================================================
    "ADX": {
        "default": {"period": 14, "threshold_trend": 25, "threshold_consolidation": 15},
        "contexts": {
            "intraday_5m": {
                "period": 10,
                "threshold_trend": 25,
                "threshold_consolidation": 15,
            },
            "intraday_15m": {
                "period": 14,
                "threshold_trend": 25,
                "threshold_consolidation": 15,
            },
            "hourly_1h": {
                "period": 14,
                "threshold_trend": 20,
                "threshold_consolidation": 10,
            },
            "daily": {
                "period": 14,
                "threshold_trend": 20,
                "threshold_consolidation": 10,
            },
            "weekly": {
                "period": 14,
                "threshold_trend": 20,
                "threshold_consolidation": 10,
            },
        },
        "_note": "ADX validates breakouts and trends; used in MCS computation.",
    },
    # ========================================================
    # CPR (Central Pivot Range)
    # ========================================================
    "CPR": {
        "default": {"pivot_method": "classic", "compression_threshold": 0.3},
        "contexts": {
            "intraday_15m": {"pivot_method": "classic", "compression_threshold": 0.3},
            "hourly_1h": {"pivot_method": "classic", "compression_threshold": 0.25},
            "daily": {"pivot_method": "classic", "compression_threshold": 0.2},
        },
        "_note": "CPR width compression indicates high SPS potential setups.",
    },
    # ========================================================
    # MACD
    # ========================================================
    "MACD": {
        "default": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        "contexts": {
            "intraday_15m": {"fast_period": 8, "slow_period": 21, "signal_period": 9},
            "hourly_1h": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            "daily": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
            "weekly": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        },
        "_note": "MACD histogram slope drives SPS/MCS crossover anticipation.",
    },
    # ========================================================
    # Ichimoku
    # ========================================================
    "ICHIMOKU": {
        "default": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52, "displacement": 26},
        "contexts": {
            "intraday_15m": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52},
            "hourly_1h": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52},
            "daily": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52},
            "weekly": {"tenkan": 9, "kijun": 26, "senkou_span_b": 52},
        },
        "_note": "Tenkan/Kijun + Span A/B confluence validates trend direction.",
    },
    # ========================================================
    # Heikin Ashi
    # ========================================================
    "HEIKINASHI": {
        "default": {"smoothing": "EMA", "window": 3},
        "contexts": {
            "intraday_15m": {"smoothing": "EMA", "window": 3},
            "hourly_1h": {"smoothing": "EMA", "window": 3},
            "daily": {"smoothing": "EMA", "window": 3},
            "weekly": {"smoothing": "EMA", "window": 3},
        },
        "_note": "Heikin-Ashi smoothing applied before CPS computation for trend bias.",
    },
    # ========================================================
    # Volume
    # ========================================================
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
        "_note": "VDU = Volume Dry-Up; Spike = Volume ≥ spike_factor × 10-bar avg.",
    },
}

# ------------------------------------------------------------
# 🧠 Helpers
# ------------------------------------------------------------
_VALID_CONTEXTS = {
    "intraday_5m",
    "intraday_15m",
    "hourly_1h",
    "daily",
    "weekly",
    "monthly",
}


def _norm(s: str) -> str:
    return (s or "").strip()


def _key_upper(name: str) -> str:
    return _norm(name).upper()


def get_indicator(name: str) -> Dict[str, Any]:
    """Retrieve configuration block (case-insensitive)."""
    return INDICATORS.get(_key_upper(name)) or INDICATORS.get(name) or {}


def list_indicators() -> list[str]:
    return list(INDICATORS.keys())


def validate() -> dict:
    """Validate structure, positive numeric params, and context keys."""
    errs: list[str] = []
    for ind_name, cfg in INDICATORS.items():
        if ind_name != ind_name.upper():
            errs.append(f"{ind_name}: indicator keys should be UPPERCASE")
        ctxs = cfg.get("contexts", {})
        if ctxs and not isinstance(ctxs, dict):
            errs.append(f"{ind_name}: contexts must be dict")
        for ckey, params in (ctxs or {}).items():
            if ckey not in _VALID_CONTEXTS:
                errs.append(f"{ind_name}: unknown context '{ckey}'")
            for pkey in (
                "period",
                "window",
                "fast_period",
                "slow_period",
                "signal_period",
                "rolling_window",
            ):
                if pkey in (params or {}):
                    val = params[pkey]
                    if not isinstance(val, int) or val <= 0:
                        errs.append(
                            f"{ind_name}.{ckey}: {pkey} must be +int, got {val}"
                        )
        for sub_name, sub in cfg.items():
            if sub_name in {"default", "contexts", "_note"}:
                continue
            if isinstance(sub, dict) and "contexts" in sub:
                for ckey, params in (sub["contexts"] or {}).items():
                    if ckey not in _VALID_CONTEXTS:
                        errs.append(f"{ind_name}.{sub_name}: unknown context '{ckey}'")
    return {"ok": not errs, "errors": errs}


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Indicator Configurations")
    pprint(list_indicators())
    pprint(get_indicator("RSI"))
    print("validate →", validate())
