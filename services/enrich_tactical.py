#!/usr/bin/env python3
# ============================================================
# queen/services/enrich_tactical.py — v1.0
# Tactical / Pattern / Volatility enricher for cockpit rows
# ------------------------------------------------------------
# Purpose:
#   Take base indicator snapshot (from services/scoring.compute_indicators)
#   and enrich it with:
#     • Pattern fusion / reversal summary
#     • Volatility fusion (VolX)
#     • Tactical core (Tactical_Index + regime)
#
# This file does NOT compute those metrics itself — it only merges the
# already-computed dicts into a single "indd" payload that action_for()
# can use.
#
# Forward-only, DRY:
#   • No overlapping logic with scoring.py
#   • Pure dict transforms, 100% polars-agnostic (df is handled upstream)
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional


def _merge(dst: Dict[str, Any], src: Optional[Dict[str, Any]]) -> None:
    """Shallow-merge `src` into `dst` (in-place), skipping None."""
    if not isinstance(src, dict):
        return
    for k, v in src.items():
        if v is not None:
            dst[k] = v


def enrich_indicators(
    base: Dict[str, Any],
    *,
    tactical: Optional[Dict[str, Any]] = None,
    pattern: Optional[Dict[str, Any]] = None,
    reversal: Optional[Dict[str, Any]] = None,
    volatility: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a new dict = base indicators + tactical/pattern/volatility metrics.

    Parameters
    ----------
    base:
        Output of compute_indicators(df) – must at least contain CMP, RSI, ATR, etc.
    tactical:
        Output of TacticalCore.compute_tactical_index(...) – e.g.:
          {
            "RScore_norm": 0.91,
            "VolX_norm": 0.75,
            "LBX_norm": 1.0,
            "PatternScore_norm": 0.0,
            "Tactical_Index": 0.717,
            "regime": {...},
            "_meta": {...},
          }
    pattern:
        Pattern fusion / reversal summary – e.g.:
          {
            "PatternScore": 5.56,
            "PatternBias": "neutral",
            "TopPattern": None,
            "PatternComponent": 0.0,
            "PatternScoreSigned": 0.0,
          }
    reversal:
        Output from reversal_stack / confluence engine – e.g.:
          {
            "Reversal_Score": 4.5,
            "Reversal_Stack_Alert": "🟡 Potential Reversal",
          }
    volatility:
        Output from volatility_fusion.summarize_volatility(...) – e.g.:
          {
            "status": "ok",
            "VolX_norm": 0.75,
            "VolX_bias": "expansion",
            "State": "📈 Expansion",
          }

    Returns
    -------
    dict:
        New dict with everything merged. scoring.action_for() will
        automatically pick up:
          • PatternScore / PatternComponent / PatternBias / TopPattern
          • Reversal_Score / Reversal_Stack_Alert
          • Tactical_Index / regime / RScore_norm / VolX_norm / LBX_norm

    Notes
    -----
    - No mutation of `base` in-place: we copy first for safety.
    - Any unknown keys from tactical/pattern/reversal/volatility are also
      preserved so future engines can consume them.

    """
    out: Dict[str, Any] = dict(base)  # shallow copy

    # Pattern fusion / summary
    if isinstance(pattern, dict):
        # Normalize common keys into the names that scoring.action_for looks for
        if "PatternComponent" in pattern and "PatternScore" not in pattern:
            # If only component is given, treat that as PatternScore as well
            pattern.setdefault("PatternScore", pattern["PatternComponent"])
        _merge(out, pattern)

    # Reversal stack / confluence
    if isinstance(reversal, dict):
        # Ensure canonical key names
        if "Reversal_Score" in reversal:
            out["Reversal_Score"] = reversal["Reversal_Score"]
        if "Reversal_Stack_Alert" in reversal:
            out["Reversal_Stack_Alert"] = reversal["Reversal_Stack_Alert"]
        # Keep any extra metadata too
        _merge(out, reversal)

    # Volatility fusion (VolX)
    if isinstance(volatility, dict):
        # We mainly care about VolX_norm / VolX_bias / State, but keep all
        _merge(out, volatility)

    # Tactical core: RScore_norm, VolX_norm, LBX_norm, PatternScore_norm, Tactical_Index, regime
    if isinstance(tactical, dict):
        # We explicitly map Tactical_Index and regime, rest are kept as-is
        if "Tactical_Index" in tactical:
            out["Tactical_Index"] = tactical["Tactical_Index"]
        if "regime" in tactical:
            out["regime"] = tactical["regime"]
        _merge(out, tactical)

    return out
