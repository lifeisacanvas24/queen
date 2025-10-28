# ============================================================
# queen/technicals/signals/tactical/reversal_stack.py
# ------------------------------------------------------------
# 🔥 Tactical Reversal Stack Engine (Phase 4.8)
# Combines Bias Regime, Divergence, Squeeze, Liquidity Trap,
# and Exhaustion to issue Confluence Reversal Alerts.
# ============================================================

import numpy as np
import polars as pl


def compute_reversal_stack(
    df: pl.DataFrame,
    bias_col: str = "Regime_State",
    div_col: str = "Divergence_Signal",
    squeeze_col: str = "Squeeze_Signal",
    trap_col: str = "Liquidity_Trap",
    exhaust_col: str = "Exhaustion_Signal",
) -> pl.DataFrame:
    """Generates a unified Reversal_Stack_Alert and confidence score.

    Scoring weights:
        Bias Reversal ........  +2
        Divergence ............  +2
        Squeeze Release .......  +1
        Liquidity Trap ........  +2
        Exhaustion ............  +2
    """
    df = df.clone()

    # Ensure columns exist
    required = [bias_col, div_col, squeeze_col, trap_col, exhaust_col]
    for col in required:
        if col not in df.columns:
            df = df.with_columns(pl.lit("").alias(col))

    n = len(df)
    score = np.zeros(n, dtype=float)
    alert = np.full(n, "➡️ Stable", dtype=object)

    bias = df[bias_col].to_list()
    div = df[div_col].to_list()
    squeeze = df[squeeze_col].to_list()
    trap = df[trap_col].to_list()
    exhaust = df[exhaust_col].to_list()

    for i in range(n):
        s = 0
        # Bias Regime reversal context
        if isinstance(bias[i], str):
            if "TREND" in bias[i] or "RANGE" in bias[i]:
                s += 2

        # Divergence bullish/bearish
        if isinstance(div[i], str):
            if "Bullish" in div[i]:
                s += 2
            elif "Bearish" in div[i]:
                s -= 2

        # Squeeze breakout
        if isinstance(squeeze[i], str) and "Release" in squeeze[i]:
            s += 1

        # Liquidity traps
        if isinstance(trap[i], str):
            if "Bear" in trap[i]:
                s += 2
            elif "Bull" in trap[i]:
                s -= 2

        # Exhaustion signals
        if isinstance(exhaust[i], str):
            if "Bullish" in exhaust[i]:
                s += 2
            elif "Bearish" in exhaust[i]:
                s -= 2

        score[i] = s

        # --- Alert synthesis ---
        if s >= 5:
            alert[i] = "🟢 Confluence BUY"
        elif s <= -5:
            alert[i] = "🔴 Confluence SELL"
        elif abs(s) >= 3:
            alert[i] = "🟡 Potential Reversal"
        else:
            alert[i] = "➡️ Stable"

    df = df.with_columns(
        [
            pl.Series("Reversal_Score", score),
            pl.Series("Reversal_Stack_Alert", alert),
        ]
    )

    return df


# ----------------------------------------------------------------------
# 🧪 Stand-alone test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    n = 60
    np.random.seed(42)
    df = pl.DataFrame(
        {
            "Regime_State": np.random.choice(["TREND", "RANGE", "VOLATILE"], n),
            "Divergence_Signal": np.random.choice(
                ["Bullish Divergence", "Bearish Divergence", ""], n
            ),
            "Squeeze_Signal": np.random.choice(
                ["Squeeze Ready", "Squeeze Release", ""], n
            ),
            "Liquidity_Trap": np.random.choice(["Bull Trap", "Bear Trap", ""], n),
            "Exhaustion_Signal": np.random.choice(
                ["🟩 Bullish Exhaustion", "🟥 Bearish Exhaustion", "➡️ Stable"], n
            ),
        }
    )

    out = compute_reversal_stack(df)
    print(
        out.select(
            [
                "Regime_State",
                "Divergence_Signal",
                "Exhaustion_Signal",
                "Reversal_Score",
                "Reversal_Stack_Alert",
            ]
        ).tail(10)
    )
