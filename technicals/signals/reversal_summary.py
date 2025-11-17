#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/reversal_summary.py — v1.1 (Bible v10.5, strict)
# ------------------------------------------------------------
# Generates a single, clean PatternScore snapshot (last bar):
#
#   • Reads BOOLEAN-derived credibility scores from state.py:
#       hammer_cred, shooting_star_cred,
#       bullish_engulfing_cred, bearish_engulfing_cred, doji_cred
#   • Reads structural signal: base_3w
#   • Reads state signals: vol_delta, rsi_density, liquidity_stability
#
# Output (dict):
#   {
#       "PatternScore": 0..100,
#       "PatternBias": "bullish" | "bearish" | "neutral",
#       "TopPattern": "<name>" | None
#   }
#
# This is what pattern_fusion / Tactical engines consume.
# ============================================================

from __future__ import annotations

from typing import Dict, List, Optional

import polars as pl
import numpy as _np

from queen.helpers.logger import log
from queen.settings import patterns as _PAT

__all__ = ["summarize_reversal_patterns"]


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _pattern_bias(name: Optional[str]) -> str:
    """Resolve bias from settings.patterns; fallback to simple heuristics."""
    if not name:
        return "neutral"
    key = (name or "").strip().lower()

    cfg = _PAT.JAPANESE.get(key) or _PAT.CUMULATIVE.get(key) or {}
    bias = (cfg.get("bias") or "").strip().lower()
    if bias in {"bullish", "bearish", "neutral"}:
        return bias

    # Heuristic fallback if bias not explicitly set in settings
    if "bullish" in key or "hammer" in key:
        return "bullish"
    if "bearish" in key or "shooting_star" in key:
        return "bearish"
    return "neutral"


def _last_float(df: pl.DataFrame, col: str) -> float:
    s = df[col]
    return float(s[-1]) if len(s) else 0.0


def _last_bool(df: pl.DataFrame, col: str) -> bool:
    s = df[col]
    if not len(s):
        return False
    v = s[-1]
    if v is None:
        return False
    return bool(v)


# ------------------------------------------------------------
# Main Reversal Summary
# ------------------------------------------------------------
def summarize_reversal_patterns(
    df: pl.DataFrame,
    *,
    context: str = "intraday_15m",
    patterns: Optional[List[str]] = None,
) -> Dict[str, object]:
    """
    Summarize pattern + credibility + structural & state features into:
        • PatternScore (0..100)
        • PatternBias   ('bullish' | 'bearish' | 'neutral')
        • TopPattern    (pattern name or None)

    Strict mode:
        - All required *_cred + state columns must be present.
        - Raises ValueError if any required input is missing.
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return {
            "PatternScore": 0.0,
            "PatternBias": "neutral",
            "TopPattern": None,
        }

    # Bible core set (you can extend this later if state.py adds more *_cred)
    if patterns is None:
        patterns = [
            "hammer",
            "shooting_star",
            "bullish_engulfing",
            "bearish_engulfing",
            "doji",
        ]

    cred_cols = [f"{p}_cred" for p in patterns]
    state_cols = ["base_3w", "vol_delta", "rsi_density", "liquidity_stability"]
    required_cols = cred_cols + state_cols

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"summarize_reversal_patterns: missing required columns: {missing}"
        )

    last_idx = df.height - 1

    # -------------------------------
    # Step 1: Pattern credibilities (last bar)
    # -------------------------------
    last_creds: Dict[str, float] = {}
    for p in patterns:
        col = f"{p}_cred"
        s = df[col]
        if last_idx >= len(s):
            raise ValueError(
                f"summarize_reversal_patterns: column '{col}' shorter than DataFrame height"
            )
        v = s[last_idx]
        last_creds[p] = float(v or 0.0)

    # -------------------------------
    # Step 2: Structural flag + state signals
    # -------------------------------
    base_flag = _last_bool(df, "base_3w")
    vol_delta = _last_float(df, "vol_delta")
    rsi_dens = _last_float(df, "rsi_density")
    lqs = _last_float(df, "liquidity_stability")

    # -------------------------------
    # Step 3: Determine top pattern
    # -------------------------------
    top_pattern = None
    top_score = 0.0
    for p, val in last_creds.items():
        if val > top_score:
            top_pattern = p
            top_score = val

    bias = _pattern_bias(top_pattern)

    # -------------------------------
    # Step 4: Combine into PatternScore
    # -------------------------------
    # Base score: credibility of the strongest pattern (0..100)
    score = float(top_score)

    # Structural bonus: base_3w (up to +10)
    if base_flag:
        score += 10.0

    # State bonuses (up to +20 total):
    #   - Volume delta: trend-aligned spike boosts score
    #   - RSI density: stable RSI regime (0..1) → +0..5
    #   - Liquidity stability: stable volume regime (0..1) → +0..5
    #
    # Note: we assume vol_delta is already a bounded state metric, e.g. [-1..+1]
    if top_pattern:
        if bias == "bullish":
            score += max(0.0, vol_delta) * 10.0  # up to +10
        elif bias == "bearish":
            score += max(0.0, -vol_delta) * 10.0
        else:
            # Neutral bias → prefer calm volume (vol_delta near 0)
            score += (1.0 - min(abs(vol_delta), 1.0)) * 5.0

    score += max(0.0, min(rsi_dens, 1.0)) * 5.0
    score += max(0.0, min(lqs, 1.0)) * 5.0

    score = float(_np.clip(score, 0.0, 100.0))

    return {
        "PatternScore": round(score, 2),
        "PatternBias": bias,
        "TopPattern": top_pattern,
    }


if __name__ == "__main__":
    # This is just a shape sanity-check; real runs will use full state.py outputs.
    import numpy as np

    n = 50
    df = pl.DataFrame(
        {
            "hammer_cred": np.linspace(0, 100, n),
            "shooting_star_cred": np.linspace(0, 50, n),
            "bullish_engulfing_cred": np.zeros(n),
            "bearish_engulfing_cred": np.zeros(n),
            "doji_cred": np.zeros(n),
            "base_3w": [False] * (n - 1) + [True],
            "vol_delta": np.linspace(-1, 1, n),
            "rsi_density": np.clip(np.random.uniform(0, 1, n), 0, 1),
            "liquidity_stability": np.clip(np.random.uniform(0, 1, n), 0, 1),
        }
    )
    out = summarize_reversal_patterns(df)
    log.info(f"[ReversalSummary] smoke-test → {out}")
    print("ReversalSummary:", out)
