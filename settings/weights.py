#!/usr/bin/env python3
# ============================================================
# queen/settings/weights.py — Multi-Timeframe Weight Map (v8.0)
# ============================================================
"""Composite Weight Configuration for Quant Scoring
---------------------------------------------------
📊 Purpose:
    Defines normalized weighting for indicators, meta-layers,
    and pattern confirmations across different timeframes.
    All weights sum ≈ 1.0 per timeframe.

💡 Usage:
    from queen.settings import weights
    tf_weights = weights.TIMEFRAMES["intraday_15m"]
"""

from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# ⏱️ Timeframe-Based Weight Definitions
# ------------------------------------------------------------
TIMEFRAMES: Dict[str, Dict[str, Any]] = {
    "intraday_5m": {
        "indicators": {
            "CPR": 0.2,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.2, "MCS": 0.15, "CPS": 0.1, "RPS": 0.1},
        "patterns": {"japanese": 0.1, "cumulative": 0.05},
        "_note": "Intraday weights favor dynamic state layers (SPS, MCS) since micro-structure shifts are rapid.",
    },
    "intraday_15m": {
        "indicators": {
            "CPR": 0.2,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.25, "MCS": 0.2, "CPS": 0.1, "RPS": 0.1},
        "patterns": {"japanese": 0.1, "cumulative": 0.05},
        "_note": "15m chart is the primary execution timeframe — higher SPS/MCS weight to catch real-time breakouts.",
    },
    "intraday_30m": {
        "indicators": {
            "CPR": 0.2,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.2, "MCS": 0.2, "CPS": 0.1, "RPS": 0.1},
        "patterns": {"japanese": 0.1, "cumulative": 0.1},
        "_note": "30m timeframe balances pattern formations with intraday momentum continuation.",
    },
    "hourly_1h": {
        "indicators": {
            "CPR": 0.15,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.2, "MCS": 0.2, "CPS": 0.15, "RPS": 0.1},
        "patterns": {"japanese": 0.1, "cumulative": 0.1},
        "_note": "Hourly timeframe is a confirmation layer for intraday signals — CPS gains validation emphasis.",
    },
    "daily": {
        "indicators": {
            "CPR": 0.15,
            "VWAP": 0.15,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.15, "MCS": 0.2, "CPS": 0.2, "RPS": 0.15},
        "patterns": {"japanese": 0.1, "cumulative": 0.1},
        "_note": "Daily layer emphasizes CPS (continuation) and RPS (reversal) for macro direction validation.",
    },
    "weekly": {
        "indicators": {
            "CPR": 0.1,
            "VWAP": 0.1,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.1,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.1, "MCS": 0.15, "CPS": 0.2, "RPS": 0.2},
        "patterns": {"japanese": 0.1, "cumulative": 0.15},
        "_note": "Weekly scans emphasize larger continuation/reversal formations — CPS & RPS dominate scoring.",
    },
    "monthly": {
        "indicators": {
            "CPR": 0.1,
            "VWAP": 0.1,
            "OBV": 0.15,
            "RSI": 0.1,
            "ADX": 0.1,
            "WRB": 0.05,
            "ATR": 0.05,
            "VolumeSpike": 0.05,
        },
        "meta_layers": {"SPS": 0.05, "MCS": 0.1, "CPS": 0.25, "RPS": 0.25},
        "patterns": {"japanese": 0.05, "cumulative": 0.2},
        "_note": "Monthly timeframe dominated by CPS (trend persistence) and RPS (macro reversals).",
    },
}

# ------------------------------------------------------------
# 🧠 Global Notes
# ------------------------------------------------------------
GLOBAL_NOTES: Dict[str, str] = {
    "1": "All weights are relative — total per timeframe ≈ 1.0.",
    "2": "In live mode, weights can be dynamically re-normalized by volatility regimes (ATR bands).",
    "3": "Pattern scores feed through CPS/RPS; Indicator scores directly affect SPS/MCS.",
}


# ------------------------------------------------------------
# 🧩 Helper Functions
# ------------------------------------------------------------
def get_weights(timeframe: str) -> Dict[str, Any]:
    """Retrieve weights for a specific timeframe."""
    return TIMEFRAMES.get(timeframe, {})


def available_timeframes() -> list[str]:
    """Return a list of all defined timeframes."""
    return list(TIMEFRAMES.keys())


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Weights Settings")
    pprint(available_timeframes())
    pprint(get_weights("intraday_15m"))
