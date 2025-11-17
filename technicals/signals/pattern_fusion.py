#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/pattern_fusion.py — v1.1 (Bible v10.5, strict)
# ------------------------------------------------------------
# Pattern Fusion Component for the Adaptive Tactical Engine.
#
# Uses:
#   • summarize_reversal_patterns(df, context, patterns)
#     → PatternScore (0..100), PatternBias, TopPattern
#
# Produces a fusion-ready block:
#   {
#       "PatternScore": float (0..100),
#       "PatternBias": "bullish" | "bearish" | "neutral",
#       "TopPattern": "<name>" | None,
#       "PatternScoreSigned": float (-1..+1),
#       "PatternWeight": float,
#       "PatternComponent": float (-PatternWeight..+PatternWeight),
#   }
#
# The fusion core then uses PatternComponent as one of the inputs
# to compute the Tactical Index & regimes.
# ============================================================

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as _np
import polars as pl

from queen.helpers.logger import log
from queen.technicals.signals.reversal_summary import summarize_reversal_patterns

__all__ = ["compute_pattern_component"]


# ------------------------------------------------------------
# Core API
# ------------------------------------------------------------
def compute_pattern_component(
    df: pl.DataFrame,
    *,
    context: str = "intraday_15m",
    patterns: Optional[List[str]] = None,
    weight: float = 0.25,
) -> Dict[str, object]:
    """Compute the Bible v10.5 Pattern component for fusion.

    Args:
        df: Polars OHLCV+state DataFrame
            (pattern_*_cred + base_3w + vol_delta + rsi_density + liquidity_stability).
        context: context key (e.g. 'intraday_15m', 'daily').
        patterns: optional explicit pattern list (default = Bible core set).
        weight: contribution of patterns to the final fusion score.
                PatternComponent ∈ [-weight, +weight].

    Returns:
        dict with:
            PatternScore        (0..100)
            PatternBias         ('bullish' | 'bearish' | 'neutral')
            TopPattern          (name or None)
            PatternScoreSigned  (-1..+1)
            PatternWeight       (weight)
            PatternComponent    (-weight..+weight)

    Strict mode:
        - If summarize_reversal_patterns detects missing inputs, it will raise.
        - We do not swallow or downscale that error.

    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return {
            "PatternScore": 0.0,
            "PatternBias": "neutral",
            "TopPattern": None,
            "PatternScoreSigned": 0.0,
            "PatternWeight": float(weight),
            "PatternComponent": 0.0,
        }

    rev = summarize_reversal_patterns(df, context=context, patterns=patterns)

    score = float(rev.get("PatternScore", 0.0) or 0.0)  # 0..100
    bias = str(rev.get("PatternBias", "neutral") or "neutral").lower()
    top = rev.get("TopPattern")

    # Convert bias → sign
    if bias == "bullish":
        sign = 1.0
    elif bias == "bearish":
        sign = -1.0
    else:
        sign = 0.0

    # Normalize score to -1..+1, then scale by weight
    score_clamped = float(_np.clip(score, 0.0, 100.0))
    signed_norm = (score_clamped / 100.0) * sign
    w = float(weight)
    component = float(_np.clip(signed_norm * w, -w, w))

    return {
        "PatternScore": score_clamped,
        "PatternBias": bias,
        "TopPattern": top,
        "PatternScoreSigned": signed_norm,
        "PatternWeight": w,
        "PatternComponent": component,
    }


# ------------------------------------------------------------
# Optional tiny smoke-test
# ------------------------------------------------------------
if __name__ == "__main__":
    # This smoke test assumes the DF already contains the
    # necessary *_cred + state columns; for a real run, you'd call
    # state.attach_state_features(...) first.
    import numpy as np

    n = 60
    df = pl.DataFrame(
        {
            "hammer_cred": np.linspace(0, 100, n),
            "shooting_star_cred": np.zeros(n),
            "bullish_engulfing_cred": np.zeros(n),
            "bearish_engulfing_cred": np.zeros(n),
            "doji_cred": np.zeros(n),
            "base_3w": [False] * (n - 1) + [True],
            "vol_delta": np.linspace(-1, 1, n),
            "rsi_density": np.clip(np.random.uniform(0, 1, n), 0, 1),
            "liquidity_stability": np.clip(np.random.uniform(0, 1, n), 0, 1),
        }
    )

    blk = compute_pattern_component(df, context="intraday_15m", weight=0.25)
    log.info(f"[PatternFusion] smoke-test block → {blk}")
    print("PatternFusion block:", blk)
