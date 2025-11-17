#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/tactical/reversal_stack.py — v2.0
# ------------------------------------------------------------
# 🔥 Tactical Reversal Stack Engine (Bible v10.5+)
#
# Inputs (required columns):
#   - Regime_State        (str)   e.g. "TREND", "RANGE", "VOLATILE", ...
#   - Divergence_Signal   (str)   e.g. "Bullish Divergence", "Bearish Divergence"
#   - Squeeze_Signal      (str)   e.g. "Squeeze Release", "Squeeze Ready"
#   - Liquidity_Trap      (str)   e.g. "Bull Trap", "Bear Trap"
#   - Exhaustion_Signal   (str)   e.g. "🟩 Bullish Exhaustion", "🟥 Bearish Exhaustion"
#   - PatternComponent    (float) continuous pattern bias from pattern_fusion /
#                                reversal_summary (typically [-1..+1])
#
# Outputs:
#   - Reversal_Score          (numeric, signed)
#   - Reversal_Stack_Alert    (str)
#
# Strict mode:
#   • If any required input column is missing, we raise ValueError.
#   • 100% Polars, forward-only, no legacy ghosts.
# ============================================================

from __future__ import annotations

import polars as pl

from queen.settings.weights import reversal_weights

# ------------------------------------------------------------
# ⚖️ Weighting scheme (tunable knobs)
# ------------------------------------------------------------
# These define how much each component pulls the Reversal_Score.
# Adjust here if you want to change the "feel" of the stack.
W = reversal_weights()

REGIME_WEIGHT_TREND_RANGE = W["REGIME_WEIGHT"]          # TREND / RANGE environments
DIVERGENCE_WEIGHT = W["DIVERGENCE_WEIGHT"]         # Bullish/Bearish Divergence
SQUEEZE_RELEASE_WEIGHT = W["SQUEEZE_RELEASE_WEIGHT"]         # "Squeeze Release" phase
TRAP_WEIGHT = W["TRAP_WEIGHT"]         # Bear Trap / Bull Trap
EXHAUSTION_WEIGHT = W["EXHAUSTION_WEIGHT"]         # Bullish/Bearish Exhaustion

# Pattern component:
#   • PatternComponent is expected in [-1..+1]
#   • We scale it (PATTERN_WEIGHT) and ignore tiny noise (PATTERN_MIN_MAG)
PATTERN_WEIGHT = W["PATTERN_WEIGHT"] # roughly [-3..+3] contribution
PATTERN_MIN_MAG = W["PATTERN_MIN_MAG"] # below this → treated as noise (0 impact)


def compute_reversal_stack(
    df: pl.DataFrame,
    *,
    bias_col: str = "Regime_State",
    div_col: str = "Divergence_Signal",
    squeeze_col: str = "Squeeze_Signal",
    trap_col: str = "Liquidity_Trap",
    exhaust_col: str = "Exhaustion_Signal",
    pattern_col: str = "PatternComponent",
    out_score: str = "Reversal_Score",
    out_alert: str = "Reversal_Stack_Alert",
) -> pl.DataFrame:
    """Confluence score (BUY/SELL/Stable) with pattern component (strict inputs)."""
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    required_cols = [
        bias_col,
        div_col,
        squeeze_col,
        trap_col,
        exhaust_col,
        pattern_col,
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"compute_reversal_stack: missing required columns: {missing}"
        )

    # ---------------- Component scores ----------------
    # Regime: TREND / RANGE → environment supportive of reversals
    bias_pts = (
        pl.when(pl.col(bias_col).str.contains("TREND|RANGE", literal=True))
        .then(pl.lit(REGIME_WEIGHT_TREND_RANGE))
        .otherwise(pl.lit(0))
    )

    # Divergence: Bullish / Bearish
    div_pts = (
        pl.when(pl.col(div_col).str.contains("Bullish", literal=True))
        .then(pl.lit(DIVERGENCE_WEIGHT))
        .when(pl.col(div_col).str.contains("Bearish", literal=True))
        .then(pl.lit(-DIVERGENCE_WEIGHT))
        .otherwise(pl.lit(0))
    )

    # Squeeze: Release phase adds mild pressure
    sqz_pts = (
        pl.when(pl.col(squeeze_col).str.contains("Release", literal=True))
        .then(pl.lit(SQUEEZE_RELEASE_WEIGHT))
        .otherwise(pl.lit(0))
    )

    # Liquidity Traps: Bear Trap = bullish, Bull Trap = bearish
    trap_pts = (
        pl.when(pl.col(trap_col).str.contains("Bear", literal=True))
        .then(pl.lit(TRAP_WEIGHT))
        .when(pl.col(trap_col).str.contains("Bull", literal=True))
        .then(pl.lit(-TRAP_WEIGHT))
        .otherwise(pl.lit(0))
    )

    # Exhaustion: Bullish / Bearish
    exh_pts = (
        pl.when(pl.col(exhaust_col).str.contains("Bullish", literal=True))
        .then(pl.lit(EXHAUSTION_WEIGHT))
        .when(pl.col(exhaust_col).str.contains("Bearish", literal=True))
        .then(pl.lit(-EXHAUSTION_WEIGHT))
        .otherwise(pl.lit(0))
    )

    # Pattern component:
    #   • continuous [-1..+1]
    #   • ignore tiny noise |x| < PATTERN_MIN_MAG
    #   • scale by PATTERN_WEIGHT for meaningful impact
    pattern_raw = pl.col(pattern_col).cast(pl.Float64)
    pattern_pts = (
        pl.when(pattern_raw.abs() >= PATTERN_MIN_MAG)
        .then(pattern_raw * PATTERN_WEIGHT)
        .otherwise(pl.lit(0.0))
    )

    # Total score
    score = (
        bias_pts
        + div_pts
        + sqz_pts
        + trap_pts
        + exh_pts
        + pattern_pts
    ).alias(out_score)

    # Alert mapping:
    #   • Strong confluence (>= ±5) → BUY / SELL
    #   • Medium confluence (|score| >= 3) → Potential Reversal
    #   • Otherwise → Stable / No strong confluence
    alert = (
        pl.when(score >= 5)
        .then(pl.lit("🟢 Confluence BUY"))
        .when(score <= -5)
        .then(pl.lit("🔴 Confluence SELL"))
        .when(score.abs() >= 3)
        .then(pl.lit("🟡 Potential Reversal"))
        .otherwise(pl.lit("➡️ Stable"))
        .alias(out_alert)
    )

    return df.with_columns([score, alert])


# Registry export
EXPORTS = {"reversal_stack": compute_reversal_stack}


if __name__ == "__main__":
    import numpy as np

    n = 60
    df = pl.DataFrame(
        {
            "Regime_State": np.random.choice(
                ["TREND", "RANGE", "VOLATILE", "NEUTRAL"], n
            ),
            "Divergence_Signal": np.random.choice(
                ["Bullish Divergence", "Bearish Divergence", ""], n
            ),
            "Squeeze_Signal": np.random.choice(
                ["Squeeze Ready", "Squeeze Release", ""], n
            ),
            "Liquidity_Trap": np.random.choice(["Bull Trap", "Bear Trap", ""], n),
            "Exhaustion_Signal": np.random.choice(
                ["🟩 Bullish Exhaustion", "🟥 Bearish Exhaustion", "➡️ Stable", ""], n
            ),
            "PatternComponent": np.random.uniform(-1, 1, size=n),
        }
    )
    out = compute_reversal_stack(df)
    print(out.select(["Reversal_Score", "Reversal_Stack_Alert"]).tail(8))
