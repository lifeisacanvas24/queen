#!/usr/bin/env python3
# ============================================================
# queen/settings/weights.py — v8.2
# (Only the bits Fusion needs: thresholds + fusion TF weights)
# ============================================================
from __future__ import annotations

# --------- Strategy thresholds (global + optional per-TF) ----------
THRESHOLDS_GLOBAL = {"ENTRY": 0.70, "EXIT": 0.30}
THRESHOLDS_PER_TF = {
    # "intraday_15m": {"ENTRY": 0.72, "EXIT": 0.28},
    # "hourly_1h":    {"ENTRY": 0.71, "EXIT": 0.29},
}


def get_thresholds(tf: str | None = None) -> dict[str, float]:
    """Return {'ENTRY': x, 'EXIT': y}. Per-TF overrides fall back to globals."""
    if tf and tf in THRESHOLDS_PER_TF:
        out = dict(THRESHOLDS_GLOBAL)
        out.update(THRESHOLDS_PER_TF[tf])
        return out
    return dict(THRESHOLDS_GLOBAL)


# --------- Inter-timeframe fusion weight preferences ----------
_FUSION_TF = {
    "intraday_5m": 0.35,
    "intraday_10m": 0.35,
    "intraday_15m": 0.40,
    "intraday_30m": 0.40,
    "hourly_1h": 0.35,
    "hourly_2h": 0.30,
    "hourly_4h": 0.30,
    "daily": 0.25,
    "weekly": 0.20,
    "monthly": 0.15,
}


def fusion_weights_for(present_tfs: list[str]) -> dict[str, float]:
    """Return normalized weights for the given present timeframes.
    Falls back to equal weights if nothing is configured.
    """
    if not present_tfs:
        return {}
    raw = {tf: float(_FUSION_TF.get(tf, 0.0)) for tf in present_tfs}
    if all(v <= 0 for v in raw.values()):
        eq = 1.0 / len(present_tfs)
        return {tf: eq for tf in present_tfs}
    s = sum(v for v in raw.values() if v > 0)
    return {tf: (v / s if s else 0.0) for tf, v in raw.items()}

# ============================================================
# 🔥 Tactical & Reversal Stack Weighting — v1.0 (Bible v10.5+)
# ============================================================

REVERSAL_WEIGHTS = {
    # Regime influence: TREND / RANGE make reversals more meaningful
    "REGIME_WEIGHT": 2,

    # Divergence influence
    "DIVERGENCE_WEIGHT": 2,

    # Squeeze Release adds minor acceleration
    "SQUEEZE_RELEASE_WEIGHT": 1,

    # Liquidity traps (Bear Trap = bullish, Bull Trap = bearish)
    "TRAP_WEIGHT": 2,

    # Exhaustion (Bullish / Bearish)
    "EXHAUSTION_WEIGHT": 2,

    # Pattern Component (from pattern fusion):
    # PatternComponent ∈ [-1, +1]
    # PATTERN_WEIGHT scales it (e.g. 3 → [-3..+3])
    # PATTERN_MIN_MAG ignores tiny noise (<0.2)
    "PATTERN_WEIGHT": 3.0,
    "PATTERN_MIN_MAG": 0.20,
}


def reversal_weights() -> dict:
    """Return a copy of tactical reversal/confluence weights."""
    return dict(REVERSAL_WEIGHTS)

# ============================================================
# 🎯 Tactical Fusion (RScore / VolX / LBX / PatternScore)
# ============================================================

# Component weights for Tactical Index
# Keys must match metric names used in tactical core.
TACTICAL_COMPONENT_WEIGHTS = {
    "RScore": 0.40,        # Regime score
    "VolX": 0.20,          # Volatility (Keltner/VolX)
    "LBX": 0.20,           # Liquidity breadth index
    "PatternScore": 0.20,  # PatternComponent / reversal fusion
}

# Normalization settings for Tactical Index
TACTICAL_NORMALIZATION = {
    "method": "minmax",    # 'minmax' or 'zscore'
    "clip": (0.0, 1.0),    # clamp final Tactical_Index
}


def tactical_component_weights() -> dict[str, float]:
    """Return a copy of Tactical meta-layer component weights."""
    return dict(TACTICAL_COMPONENT_WEIGHTS)


def tactical_normalization() -> dict:
    """Return Tactical normalization config (method, clip)."""
    return dict(TACTICAL_NORMALIZATION)
