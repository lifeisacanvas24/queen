#!/usr/bin/env python3
# ============================================================
# queen/settings/regimes.py — Market Regime Configuration (v9.1)
# Forward-only, uppercase keys, helpers, Polars export
# ============================================================
from __future__ import annotations

from typing import Dict

import polars as pl  # Polars-only per project convention ✅

# ------------------------------------------------------------
# 🧠 Regime Parameters (UPPERCASE KEYS)
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
        "thresholds": {"rsi_min": 45, "adx_min": 15, "vix_state": "flat"},
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
        "thresholds": {"rsi_max": 45, "adx_min": 20, "vix_state": "rising"},
        "actions": {
            "risk_multiplier": 0.6,
            "position_sizing": "defensive",
            "indicator_sensitivity": 1.2,
        },
    },
}

# Optional ordering for dashboards
REGIME_ORDER = ["BEARISH", "NEUTRAL", "BULLISH"]

# ------------------------------------------------------------
# ⚙️ Regime Derivation (stateless)
# ------------------------------------------------------------
def derive_regime(metrics: dict) -> str:
    """Derive current regime from metrics (rsi, adx, vix_change, obv_slope)."""
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
    return REGIMES.get((regime or "").upper(), REGIMES["NEUTRAL"])


def list_regimes() -> list[str]:
    return list(REGIMES.keys())


def color_for(regime: str) -> str:
    return get_regime_config(regime).get("color", "#9ca3af")  # gray fallback

# ------------------------------------------------------------
# 🧪 Validation & Export
# ------------------------------------------------------------
def validate() -> dict:
    errs: list[str] = []
    for name, cfg in REGIMES.items():
        if name.upper() != name:
            errs.append(f"{name}: regime key must be UPPERCASE")
        for req in (
            "trend_bias",
            "volatility_state",
            "liquidity_state",
            "color",
            "description",
            "thresholds",
            "actions",
        ):
            if req not in cfg:
                errs.append(f"{name}: missing '{req}'")
        acts = cfg.get("actions", {})
        if "risk_multiplier" in acts and not isinstance(acts["risk_multiplier"], (int, float)):
            errs.append(f"{name}: actions.risk_multiplier must be number")
        if "indicator_sensitivity" in acts and not isinstance(acts["indicator_sensitivity"], (int, float)):
            errs.append(f"{name}: actions.indicator_sensitivity must be number")
    return {"ok": len(errs) == 0, "errors": errs, "count": len(REGIMES)}

def to_polars_df() -> pl.DataFrame:
    """Flat view for dashboards / notebooks."""
    rows = []
    for nm, c in REGIMES.items():
        rows.append(
            {
                "Regime": nm,
                "Trend Bias": c.get("trend_bias"),
                "Volatility": c.get("volatility_state"),
                "Liquidity": c.get("liquidity_state"),
                "Risk Multiplier": c.get("actions", {}).get("risk_multiplier"),
                "Indicator Sens": c.get("actions", {}).get("indicator_sensitivity"),
                "Color": c.get("color"),
            }
        )
    # Optional: maintain a stable row order for displays
    order_index = {r: i for i, r in enumerate(REGIME_ORDER)}
    df = pl.DataFrame(rows)
    if "Regime" in df.columns:
        df = df.with_columns(
            pl.col("Regime")
            .map_elements(lambda x: order_index.get(x, 9999))
            .alias("__ord__")
        ).sort("__ord__").drop("__ord__")
    return df

# Alias for code that expects as_polars_df()
as_polars_df = to_polars_df

# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    print("🧭 Regimes:", list_regimes())
    print("validate →", validate())
    print(to_polars_df())
