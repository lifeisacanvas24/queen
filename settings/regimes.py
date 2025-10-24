# queen/settings/regimes.py

"""Market Regime Configuration (v1.0)
----------------------------------
Defines volatility, trend, and liquidity regimes used
across Tactical Fusion Engine (TFE), strategy blending,
and adaptive weighting systems.
"""

from __future__ import annotations

from typing import Dict

# ------------------------------------------------------------
# 🧠 Regime Parameters
# ------------------------------------------------------------

REGIMES: Dict[str, dict] = {
    "BULLISH": {
        "trend_bias": 1,
        "volatility_state": "expansion",
        "liquidity_state": "rising",
        "color": "#22c55e",
        "description": "Trend expansion phase — risk-on, breakout conditions active.",
        "thresholds": {
            "rsi_min": 55,
            "adx_min": 20,
            "obv_slope": "positive",
            "vix_state": "falling",
        },
        "actions": {
            "risk_multiplier": 1.2,
            "position_sizing": "aggressive",
            "indicator_sensitivity": 0.9,
        },
    },
    "NEUTRAL": {
        "trend_bias": 0,
        "volatility_state": "balanced",
        "liquidity_state": "stable",
        "color": "#3b82f6",
        "description": "Range-bound phase — mixed momentum, mean-reversion favored.",
        "thresholds": {
            "rsi_min": 45,
            "adx_min": 15,
            "vix_state": "flat",
        },
        "actions": {
            "risk_multiplier": 1.0,
            "position_sizing": "moderate",
            "indicator_sensitivity": 1.0,
        },
    },
    "BEARISH": {
        "trend_bias": -1,
        "volatility_state": "rising",
        "liquidity_state": "contracting",
        "color": "#ef4444",
        "description": "Downtrend or correction phase — volatility spikes, liquidity fades.",
        "thresholds": {
            "rsi_max": 45,
            "adx_min": 20,
            "vix_state": "rising",
        },
        "actions": {
            "risk_multiplier": 0.6,
            "position_sizing": "defensive",
            "indicator_sensitivity": 1.2,
        },
    },
}

# ------------------------------------------------------------
# ⚙️ Regime Derivation Logic (Stateless Helper)
# ------------------------------------------------------------


def derive_regime(metrics: dict) -> str:
    """Derive current regime based on dynamic metrics.
    Expected keys: 'rsi', 'adx', 'vix_change', 'obv_slope'
    """
    rsi = metrics.get("rsi", 50)
    adx = metrics.get("adx", 15)
    vix = metrics.get("vix_change", 0)
    obv = metrics.get("obv_slope", 0)

    if rsi >= 55 and adx >= 20 and vix < 0 and obv > 0:
        return "BULLISH"
    if rsi <= 45 and adx >= 20 and vix > 0:
        return "BEARISH"
    return "NEUTRAL"


def get_regime_config(regime: str) -> dict:
    """Get the full regime configuration safely."""
    return REGIMES.get(regime.upper(), REGIMES["NEUTRAL"])


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    sample = {"rsi": 60, "adx": 25, "vix_change": -2, "obv_slope": 1}
    regime = derive_regime(sample)
    print(f"📊 Derived regime: {regime}")
    print(get_regime_config(regime))
