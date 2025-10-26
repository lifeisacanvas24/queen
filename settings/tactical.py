#!/usr/bin/env python3
# ============================================================
# queen/settings/tactical.py — Tactical Fusion Engine Config (v8.1)
# ============================================================
from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# ⚙️ Input Weight Map
# ------------------------------------------------------------
INPUTS: Dict[str, Dict[str, Any]] = {
    "RScore": {"source": "metrics.regime_strength", "weight": 0.5, "normalize": True},
    "VolX": {"source": "metrics.volatility_index", "weight": 0.3, "normalize": True},
    "LBX": {"source": "metrics.liquidity_breadth", "weight": 0.2, "normalize": True},
}

# ------------------------------------------------------------
# ⚖️ Normalization Parameters
# ------------------------------------------------------------
NORMALIZATION: Dict[str, Any] = {"method": "zscore", "clip": (0.0, 1.0)}

# ------------------------------------------------------------
# 🧮 Output Definition
# ------------------------------------------------------------
OUTPUT: Dict[str, Any] = {"name": "Tactical_Index", "rounding": 3}

# ------------------------------------------------------------
# 🧭 Regime Thresholds & Presentation
# ------------------------------------------------------------
REGIMES: Dict[str, Any] = {
    "thresholds": {"bearish": 0.3, "neutral": 0.7},
    "labels": {
        "bearish": "Bearish Regime",
        "neutral": "Neutral Zone",
        "bullish": "Bullish Regime",
    },
    "colors": {"bearish": "#ef4444", "neutral": "#3b82f6", "bullish": "#22c55e"},
}


# ------------------------------------------------------------
# 🧠 Helpers
# ------------------------------------------------------------
def _sum_weights() -> float:
    return float(sum(float(v.get("weight", 0.0)) for v in INPUTS.values()))


def get_weights(normalized: bool = False) -> Dict[str, float]:
    """Return a {input: weight} map. If normalized=True, force sum to 1.0."""
    raw = {k: float(v.get("weight", 0.0)) for k, v in INPUTS.items()}
    if not normalized:
        return raw
    s = sum(raw.values()) or 1.0
    return {k: (w / s) for k, w in raw.items()}


def normalized_view() -> Dict[str, Any]:
    """Snapshot suitable for dashboards / CLI."""
    return {
        "inputs": {
            k: {**v, "weight": get_weights(normalized=True)[k]}
            for k, v in INPUTS.items()
        },
        "normalization": NORMALIZATION,
        "output": OUTPUT,
        "regimes": REGIMES,
        "_sum_raw": _sum_weights(),
    }


def validate() -> Dict[str, Any]:
    """Light sanity checks."""
    errs = []
    # weights must be non-negative
    for k, v in INPUTS.items():
        w = v.get("weight", 0)
        if w is None or float(w) < 0:
            errs.append(f"{k}: weight must be >= 0")
    # label/color keys present
    for key in ("bearish", "neutral", "bullish"):
        if key not in REGIMES.get("labels", {}):
            errs.append(f"REGIMES.labels missing '{key}'")
        if key not in REGIMES.get("colors", {}):
            errs.append(f"REGIMES.colors missing '{key}'")
    return {"ok": not errs, "errors": errs, "sum_raw": round(_sum_weights(), 6)}


# ------------------------------------------------------------
# 🧠 Summary
# ------------------------------------------------------------
def summary() -> Dict[str, Any]:
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
    from pprint import pprint

    print("🎯 Queen Tactical Fusion Config")
    pprint(summary())
    print("validate:", validate())
    print("weights (raw):", get_weights(False))
    print("weights (norm):", get_weights(True))
