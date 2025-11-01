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
