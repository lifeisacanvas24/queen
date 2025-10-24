#!/usr/bin/env python3
# ============================================================
# queen/settings/universe.py — Monthly Universe Model Config (v8.0)
# ============================================================
"""Active Universe Construction Parameters
------------------------------------------
🌐 Purpose:
    Defines weighting, thresholds, and risk filters used to
    build and maintain the active trading universe monthly.

💡 Usage:
    from queen.settings import universe
    factors = universe.FACTORS
"""

from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# 🧩 Version Metadata
# ------------------------------------------------------------
VERSION = "1.0.0"
DESCRIPTION = "Quant-Core Monthly Universe Model Parameters"

# ------------------------------------------------------------
# ⚖️ Factor Weighting
# ------------------------------------------------------------
FACTORS: Dict[str, float] = {
    "momentum": 0.4,
    "liquidity": 0.3,
    "volatility": 0.2,
    "trend": 0.1,
}

# ------------------------------------------------------------
# 📊 Selection Thresholds
# ------------------------------------------------------------
THRESHOLDS: Dict[str, float | int] = {
    "min_turnover": 50_000_000,
    "min_price": 50,
    "max_rank": 300,
}

# ------------------------------------------------------------
# ⏱️ Selection Period Requirements
# ------------------------------------------------------------
SELECTION: Dict[str, int] = {
    "period_days": 30,
    "min_candles": 20,
}

# ------------------------------------------------------------
# ⚠️ Risk Filters
# ------------------------------------------------------------
RISK_FILTERS: Dict[str, float] = {
    "max_beta": 1.5,
    "max_volatility": 0.04,
}

# ------------------------------------------------------------
# 🧾 Fundamental Filters
# ------------------------------------------------------------
FUNDAMENTALS: Dict[str, float] = {
    "min_pe": 5,
    "max_pe": 60,
    "min_market_cap": 1e9,
}


# ------------------------------------------------------------
# 🧠 Utility Helper
# ------------------------------------------------------------
def summary() -> Dict[str, Any]:
    """Return unified configuration overview."""
    return {
        "version": VERSION,
        "factors": FACTORS,
        "thresholds": THRESHOLDS,
        "selection": SELECTION,
        "risk_filters": RISK_FILTERS,
        "fundamentals": FUNDAMENTALS,
    }


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Universe Config")
    pprint(summary())
