#!/usr/bin/env python3
# ============================================================
# queen/technicals/fundamentals_gate.py — v3.2 (Final Integration Layer)
# ============================================================
from __future__ import annotations

from typing import Dict, Optional, Sequence

import polars as pl


# from queen.helpers.logger import log # Assume log is available
class Logger:
    def info(self, msg): print(msg)
    def warning(self, msg): print(msg)
    def error(self, msg): print(msg)
log = Logger()

# ------------------------------------------------------------
# Internal Helpers
# ------------------------------------------------------------
def _pick_col(df: pl.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    """Return the name of the first column that exists in the DataFrame."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _ensure_symbol_col(df: pl.DataFrame, preferred: str = "Symbol") -> str:
    col = _pick_col(df, [preferred, preferred.lower(), "symbol", "SYMBOL"])
    if not col:
        raise ValueError(
            "[FUND-GATE] No symbol column found. Expected: Symbol/symbol/SYMBOL"
        )
    return col


def fundamentals_overlay_df(
    fundamentals_df: pl.DataFrame,
    *,
    symbol_col: str = "Symbol",
) -> pl.DataFrame:
    """Selects and returns only the necessary final scoring/filtering columns
    from the full fundamentals DF (output of score_and_filter).
    """
    if fundamentals_df is None or fundamentals_df.is_empty():
        return pl.DataFrame()

    f_sym = _ensure_symbol_col(fundamentals_df, symbol_col)

    # 🚨 REQUIRED COLUMNS from fundamentals_score_engine v3.0 (PowerScore MAX) 🚨
    needed = [
        "Fundamental_Pass",
        "Fundamental_Fail_Reasons",
        "Intrinsic_Bucket",
        "Intrinsic_Score",
        "PowerScore_v1",  # Crucial new composite score
        "Fundamental_Momentum",  # From TS Engine (optional)
        "Earnings_Momentum",  # From TS Engine (optional)
    ]

    # Filter to only Symbol and the needed columns that exist
    selection = [f_sym]
    for col in needed:
        if col in fundamentals_df.columns:
            selection.append(col)

    if len(selection) <= 1:
        log.warning("[FUND-GATE] Fundamentals DF missing core scoring columns.")
        # Return only the Symbol column if scores are missing
        return fundamentals_df.select(f_sym)

    return fundamentals_df.select(selection)


# ------------------------------------------------------------
# Final Gate and Boost Logic (H1 Hybrid Mode)
# ------------------------------------------------------------
def fundamentals_gate_and_boost(
    joined: pl.DataFrame,
    *,
    hard_gate: bool = True,
    boost_map: Optional[Dict[str, float]] = None,
    score_col: str = "Technical_Score",
    alert_col: str = "Technical_Alert",
    out_score_col: Optional[str] = None,
    out_alert_col: str = "Final_Alert",
) -> pl.DataFrame:
    """Applies the fundamental pass/fail as a hard filter on an alert/score
    and optionally applies a multiplier boost based on the score bucket.
    """
    if joined is None or joined.is_empty():
        return pl.DataFrame()

    # Dynamic column discovery
    pass_col = _pick_col(joined, ["Fundamental_Pass"])
    bucket_col = _pick_col(joined, ["Intrinsic_Bucket"])

    # Set default alert column if missing
    if alert_col not in joined.columns:
        joined = joined.with_columns(pl.lit("➡️ Stable").alias(alert_col))

    # 1. HARD GATE: Block Alert if Fundamental_Pass is False or NULL
    if hard_gate and pass_col:
        is_blocked = pl.col(pass_col).is_null() | (pl.col(pass_col) == False)

        joined = joined.with_columns(
            pl.when(is_blocked)
            .then(pl.lit("⛔ Fundamentals Blocked"))
            .otherwise(pl.col(alert_col))
            .alias(out_alert_col)
        )
    else:
        # If hard_gate is False, just copy the alert
        joined = joined.with_columns(pl.col(alert_col).alias(out_alert_col))

    # 2. SOFT BOOST: Apply multiplier to an existing score column
    if (
        boost_map and bucket_col
        and score_col in joined.columns
        and pass_col in joined.columns
    ):
        out_score_col = out_score_col or f"{score_col}_FundBoost"

        boost_expr = pl.lit(1.0) # Default factor

        # Build the conditional expression for the boost factor
        for bucket, factor in boost_map.items():
            # Apply boost only if Fundamental_Pass is True AND bucket matches
            condition = (pl.col(bucket_col) == bucket) & (pl.col(pass_col) == True)
            boost_expr = pl.when(condition).then(pl.lit(float(factor))).otherwise(boost_expr)

        joined = joined.with_columns(
            (pl.col(score_col).cast(pl.Float64) * boost_expr).alias(out_score_col)
        )
        log.info(f"[FUND-GATE] Applied boost to column '{score_col}' via bucket map.")

    return joined


EXPORTS = {
    "fundamentals_gate": {
        "fundamentals_overlay_df": fundamentals_overlay_df,
        "fundamentals_gate_and_boost": fundamentals_gate_and_boost,
    }
}
