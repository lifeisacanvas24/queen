#!/usr/bin/env python3
# ============================================================
# queen/settings/meta_layers.py — Market State Meta-Layer Configuration (v8.0)
# ============================================================
"""Meta-Layer Signal Configuration
-----------------------------------
🧠 Purpose:
    Defines Setup Pressure (SPS), Momentum Continuation (MCS),
    Continuation Pattern (CPS), and Reversal Pressure (RPS) parameters
    across multiple timeframes.

💡 Usage:
    from queen.settings import meta_layers
    sps = meta_layers.META_LAYERS["SPS"]
"""

from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# 🧩 Meta-Layer Configuration
# ------------------------------------------------------------
META_LAYERS: Dict[str, Dict[str, Any]] = {
    # ========================================================
    # SPS — Setup Pressure Score
    # ========================================================
    "SPS": {
        "description": "Setup Pressure Score — measures coil/compression before breakout using CPR, ATR, and volume dry-up signals.",
        "contexts": {
            "intraday_5m": {
                "timeframe": "5m",
                "lookback": 60,
                "min_cpr_compressions": 4,
                "volume_factor": 0.8,
            },
            "intraday_15m": {
                "timeframe": "15m",
                "lookback": 40,
                "min_cpr_compressions": 3,
                "volume_factor": 0.8,
            },
            "intraday_30m": {
                "timeframe": "30m",
                "lookback": 30,
                "min_cpr_compressions": 2,
                "volume_factor": 0.75,
            },
            "hourly_1h": {
                "timeframe": "1H",
                "lookback": 30,
                "min_cpr_compressions": 2,
                "volume_factor": 0.7,
            },
            "daily": {
                "timeframe": "1D",
                "lookback": 20,
                "min_cpr_compressions": 2,
                "volume_factor": 0.7,
            },
        },
        "_note": "SPS is elevated when CPR width < 0.3×avg width and volume < 0.8×10-bar average.",
    },
    # ========================================================
    # MCS — Momentum Continuation Score
    # ========================================================
    "MCS": {
        "description": "Momentum Continuation Score — quantifies post-breakout strength using WRB count, RSI slope, and OBV alignment.",
        "contexts": {
            "intraday_5m": {
                "timeframe": "5m",
                "lookback": 25,
                "min_wrbs": 3,
                "rsi_window": 14,
                "obv_window": 20,
            },
            "intraday_15m": {
                "timeframe": "15m",
                "lookback": 20,
                "min_wrbs": 2,
                "rsi_window": 14,
                "obv_window": 20,
            },
            "hourly_1h": {
                "timeframe": "1H",
                "lookback": 15,
                "min_wrbs": 1,
                "rsi_window": 14,
                "obv_window": 20,
            },
            "daily": {
                "timeframe": "1D",
                "lookback": 10,
                "min_wrbs": 1,
                "rsi_window": 14,
                "obv_window": 20,
            },
        },
        "_note": "MCS > 1.0 when WRBs appear with RSI > 55 and OBV > 5-bar average.",
    },
    # ========================================================
    # CPS — Continuation Pattern Strength
    # ========================================================
    "CPS": {
        "description": "Continuation Pattern Strength — persistence of structural Japanese or cumulative patterns in recent windows.",
        "contexts": {
            "intraday_15m": {
                "timeframe": "15m",
                "lookback": 60,
                "pattern_count_window": 20,
                "min_repeat_patterns": 3,
            },
            "hourly_1h": {
                "timeframe": "1H",
                "lookback": 60,
                "pattern_count_window": 20,
                "min_repeat_patterns": 2,
            },
            "daily": {
                "timeframe": "1D",
                "lookback": 60,
                "pattern_count_window": 20,
                "min_repeat_patterns": 2,
            },
            "weekly": {
                "timeframe": "1W",
                "lookback": 26,
                "pattern_count_window": 12,
                "min_repeat_patterns": 1,
            },
        },
        "_note": "CPS increases when similar bullish/bearish patterns reappear within lookback period with rising OBV.",
    },
    # ========================================================
    # RPS — Reversal Pressure Score
    # ========================================================
    "RPS": {
        "description": "Reversal Pressure Score — anticipates exhaustion using RSI divergence, volume spike, and CPR rejection.",
        "contexts": {
            "intraday_15m": {
                "timeframe": "15m",
                "lookback": 40,
                "divergence_window": 10,
                "rsi_threshold": 65,
                "volume_spike_factor": 1.3,
            },
            "daily": {
                "timeframe": "1D",
                "lookback": 20,
                "divergence_window": 7,
                "rsi_threshold": 70,
                "volume_spike_factor": 1.4,
            },
            "weekly": {
                "timeframe": "1W",
                "lookback": 12,
                "divergence_window": 4,
                "rsi_threshold": 75,
                "volume_spike_factor": 1.5,
            },
        },
        "_note": "RPS > 1.0 when RSI divergence + volume spike near CPR R2/S2 zones.",
    },
}


# ------------------------------------------------------------
# 🧠 Helper Functions
# ------------------------------------------------------------
def get_meta_layer(name: str) -> Dict[str, Any]:
    """Retrieve configuration block for a given meta-layer."""
    return META_LAYERS.get(name.upper(), {})


def list_meta_layers() -> list[str]:
    """List all available meta-layers."""
    return list(META_LAYERS.keys())


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Meta-Layer Configuration")
    pprint(list_meta_layers())
    pprint(get_meta_layer("SPS"))
