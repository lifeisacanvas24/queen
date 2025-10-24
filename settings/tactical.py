#!/usr/bin/env python3
# ============================================================
# queen/settings/tactical.py — Tactical Fusion Engine Config (v8.0)
# ============================================================
"""Tactical Fusion Engine — Configuration Constants
---------------------------------------------------
🎯 Purpose:
    Defines how regime (RScore), volatility (VolX), and liquidity (LBX)
    are blended into a single Tactical Index used for higher-order
    strategy inference and dashboard visualization.

💡 Usage:
    from queen.settings import tactical
    tactical.INPUTS["RScore"]["weight"]
"""

from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# ⚙️ Input Weight Map
# ------------------------------------------------------------
INPUTS: Dict[str, Dict[str, Any]] = {
    "RScore": {
        "source": "metrics.regime_strength",
        "weight": 0.5,
        "normalize": True,
    },
    "VolX": {
        "source": "metrics.volatility_index",
        "weight": 0.3,
        "normalize": True,
    },
    "LBX": {
        "source": "metrics.liquidity_breadth",
        "weight": 0.2,
        "normalize": True,
    },
}

# ------------------------------------------------------------
# ⚖️ Normalization Parameters
# ------------------------------------------------------------
NORMALIZATION: Dict[str, Any] = {
    "method": "zscore",
    "clip": (0.0, 1.0),
}

# ------------------------------------------------------------
# 🧮 Output Definition
# ------------------------------------------------------------
OUTPUT: Dict[str, Any] = {
    "name": "Tactical_Index",
    "rounding": 3,
}

# ------------------------------------------------------------
# 🧭 Regime Thresholds & Presentation
# ------------------------------------------------------------
REGIMES: Dict[str, Any] = {
    "thresholds": {
        "bearish": 0.3,
        "neutral": 0.7,
    },
    "labels": {
        "bearish": "Bearish Regime",
        "neutral": "Neutral Zone",
        "bullish": "Bullish Regime",
    },
    "colors": {
        "bearish": "#ef4444",  # 🔴 Red
        "neutral": "#3b82f6",  # 🔵 Blue
        "bullish": "#22c55e",  # 🟢 Green
    },
}


# ------------------------------------------------------------
# 🧠 Utility Helper
# ------------------------------------------------------------
def summary() -> Dict[str, Any]:
    """Return a unified tactical engine summary."""
    return {
        "inputs": INPUTS,
        "normalization": NORMALIZATION,
        "output": OUTPUT,
        "regimes": REGIMES,
    }


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    print("🎯 Queen Tactical Fusion Config")
    from pprint import pprint

    pprint(summary())
