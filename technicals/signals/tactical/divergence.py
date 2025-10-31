# ============================================================
# queen/technicals/signals/tactical/divergence.py
# ------------------------------------------------------------
# ⚙️ Volume–Momentum Divergence Engine (v2.0)
# Vectorized Polars: emits Divergence_Signal, Divergence_Score, Divergence_Flag
# ============================================================

from __future__ import annotations

import polars as pl


def detect_divergence(
    df: pl.DataFrame,
    *,
    price_col: str = "close",
    cmv_col: str = "CMV",
    lookback: int = 5,
    threshold: float = 0.02,
) -> pl.DataFrame:
    """Detect CMV–Price divergences (momentum disagreement zones)."""
    if price_col not in df.columns or cmv_col not in df.columns:
        # graceful skip with explicit columns (keeps downstream code happy)
        return df.with_columns(
            [
                pl.lit("➡️ Skipped").alias("Divergence_Signal"),
                pl.lit(0).alias("Divergence_Score"),
                pl.lit("➡️ Skipped").alias("Divergence_Flag"),
            ]
        )

    lb = max(int(lookback), 1)
    thr = float(threshold)

    price_slope = pl.col(price_col) - pl.col(price_col).shift(lb)
    cmv_slope = pl.col(cmv_col) - pl.col(cmv_col).shift(lb)

    bear = (price_slope > thr) & (cmv_slope < -thr)
    bull = (price_slope < -thr) & (cmv_slope > thr)

    signal = (
        pl.when(bear)
        .then(pl.lit("🟥 Bearish Divergence (Momentum Weakening)"))
        .when(bull)
        .then(pl.lit("🟩 Bullish Divergence (Momentum Building)"))
        .otherwise(pl.lit("➡️ Stable"))
        .alias("Divergence_Signal")
    )

    score = (
        pl.when(bear)
        .then(pl.lit(-1))
        .when(bull)
        .then(pl.lit(1))
        .otherwise(pl.lit(0))
        .alias("Divergence_Score")
    )

    flag = (
        pl.when(bear)
        .then(pl.lit("SELL"))
        .when(bull)
        .then(pl.lit("BUY"))
        .otherwise(pl.lit("NEUTRAL"))
        .alias("Divergence_Flag")
    )

    return df.with_columns([signal, score, flag])


def summarize_divergence(df: pl.DataFrame) -> str:
    """Quick summary string; safe if columns missing/empty."""
    if (
        df.is_empty()
        or "Divergence_Score" not in df.columns
        or "Divergence_Flag" not in df.columns
    ):
        return "Bullish: 0 | Bearish: 0 | Last: —"

    bull = int((pl.Series(df["Divergence_Score"]) > 0).sum())
    bear = int((pl.Series(df["Divergence_Score"]) < 0).sum())
    last_flag = (
        str(pl.Series(df["Divergence_Flag"]).drop_nulls().tail(1).to_list()[0])
        if df.height
        else "—"
    )
    return f"Bullish: {bull} | Bearish: {bear} | Last: {last_flag}"


# Registry export (for queen.cli.list_signals)
EXPORTS = {"divergence": detect_divergence}
