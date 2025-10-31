# ============================================================
# queen/technicals/signals/tactical/reversal_stack.py
# ------------------------------------------------------------
# 🔥 Tactical Reversal Stack Engine (Phase 4.9)
# Vectorized Polars implementation (no Python loops)
# ============================================================

from __future__ import annotations

import polars as pl


def compute_reversal_stack(
    df: pl.DataFrame,
    *,
    bias_col: str = "Regime_State",
    div_col: str = "Divergence_Signal",
    squeeze_col: str = "Squeeze_Signal",
    trap_col: str = "Liquidity_Trap",
    exhaust_col: str = "Exhaustion_Signal",
    out_score: str = "Reversal_Score",
    out_alert: str = "Reversal_Stack_Alert",
) -> pl.DataFrame:
    """Confluence score (BUY/SELL/Stable) using vectorized rules."""
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    # Ensure the columns exist (as empty strings if missing)
    need = [bias_col, div_col, squeeze_col, trap_col, exhaust_col]
    add = [pl.lit("").alias(c) for c in need if c not in df.columns]
    if add:
        df = df.with_columns(add)

    # Build vectorized component scores
    bias_pts = (
        pl.when(pl.col(bias_col).str.contains("TREND|RANGE", literal=True))
        .then(pl.lit(2))
        .otherwise(pl.lit(0))
    )

    div_pts = (
        pl.when(pl.col(div_col).str.contains("Bullish", literal=True))
        .then(pl.lit(2))
        .when(pl.col(div_col).str.contains("Bearish", literal=True))
        .then(pl.lit(-2))
        .otherwise(pl.lit(0))
    )

    sqz_pts = (
        pl.when(pl.col(squeeze_col).str.contains("Release", literal=True))
        .then(1)
        .otherwise(0)
    )

    trap_pts = (
        pl.when(pl.col(trap_col).str.contains("Bear", literal=True))
        .then(pl.lit(2))
        .when(pl.col(trap_col).str.contains("Bull", literal=True))
        .then(pl.lit(-2))
        .otherwise(pl.lit(0))
    )

    exh_pts = (
        pl.when(pl.col(exhaust_col).str.contains("Bullish", literal=True))
        .then(pl.lit(2))
        .when(pl.col(exhaust_col).str.contains("Bearish", literal=True))
        .then(pl.lit(-2))
        .otherwise(pl.lit(0))
    )

    score = (bias_pts + div_pts + sqz_pts + trap_pts + exh_pts).alias(out_score)

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

# Local smoke
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
        }
    )
    out = compute_reversal_stack(df)
    print(out.select(["Reversal_Score", "Reversal_Stack_Alert"]).tail(8))
