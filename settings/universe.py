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

from queen.settings import timeframes as TF

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


def selection_window_days(timeframe_token: str) -> int:
    """Days of data typically needed to run selection at `timeframe_token`."""
    TF.validate_token(timeframe_token)
    # honor explicit period_days; also cover min_candles at this tf
    days_by_period = int(SELECTION.get("period_days", 30))
    days_by_bars = TF.window_days_for_tf(
        timeframe_token, int(SELECTION.get("min_candles", 20))
    )
    return max(days_by_period, days_by_bars)


def min_bars_for_selection(timeframe_token: str) -> int:
    """Minimum bars required to satisfy SELECTION['min_candles'] at `timeframe_token`."""
    TF.validate_token(timeframe_token)
    return int(SELECTION.get("min_candles", 20))


def validate() -> dict:
    """Light checks for config correctness."""
    errs = []

    # factors ~ 1.0 (±0.25 tolerance)
    s = sum(float(v) for v in FACTORS.values())
    if not (0.75 <= s <= 1.25):
        errs.append(f"FACTORS sum={round(s,4)} should be ≈1.0 (±0.25 tol)")

    # types / non-negatives
    if SELECTION.get("period_days", 0) <= 0:
        errs.append("SELECTION.period_days must be > 0")
    if SELECTION.get("min_candles", 0) <= 0:
        errs.append("SELECTION.min_candles must be > 0")

    ok = not errs
    return {"ok": ok, "errors": errs, "count": len(FACTORS)}


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Universe Config")
    pprint(summary())
