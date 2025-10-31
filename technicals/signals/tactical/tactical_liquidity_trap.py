# ============================================================
# queen/technicals/signals/tactical/tactical_liquidity_trap.py
# ------------------------------------------------------------
# ⚙️ Liquidity Trap & Absorption (Polars-native, vectorized)
# Detects false breakouts + absorption using CMV/SPS and volume flow.
# ============================================================

from __future__ import annotations

import polars as pl

__all__ = ["detect_liquidity_trap"]


def detect_liquidity_trap(
    df: pl.DataFrame,
    *,
    cmv_col: str = "CMV",
    sps_col: str = "SPS",
    mfi_col: str = "MFI",
    chaikin_col: str = "Chaikin_Osc",
    threshold_sps: float = 0.85,
    lookback: int = 5,
    out_col: str = "Liquidity_Trap",
    out_score_col: str = "Liquidity_Trap_Score",
) -> pl.DataFrame:
    """Vectorized trap detection.

    Rules (per bar):
      • CMV sign flip AND SPS exhaustion (post-peak cool-off)
      • + bearish absorption: Chaikin<0 & MFI↓  → 🟥 Bear Trap (short squeeze risk)
      • + bullish absorption: Chaikin>0 & MFI<40 → 🟩 Bull Trap (long liquidation risk)

    Outputs:
      - {out_col}: 🟥/🟩/➡️
      - {out_score_col}: +2 (bear trap), -2 (bull trap), 0 (stable)
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    # Require CMV & SPS; otherwise mark as skipped
    req = {cmv_col, sps_col}
    if not req.issubset(df.columns):
        return df.with_columns(pl.lit("➡️ Skipped").alias(out_col))

    # Ensure optional inputs exist (neutral fallbacks)
    add_cols = []
    if mfi_col not in df.columns:
        add_cols.append(pl.lit(50.0).alias(mfi_col))  # neutral mid MFI
    if chaikin_col not in df.columns:
        add_cols.append(pl.lit(0.0).alias(chaikin_col))  # neutral flow
    if add_cols:
        df = df.with_columns(add_cols)

    cmv = pl.col(cmv_col).cast(pl.Float64).fill_null(0.0)
    sps = pl.col(sps_col).cast(pl.Float64).fill_null(0.0)
    mfi = pl.col(mfi_col).cast(pl.Float64).fill_null(50.0)
    ch = pl.col(chaikin_col).cast(pl.Float64).fill_null(0.0)

    # 1) CMV flip density in last `lookback` bars
    flip1 = (cmv.sign() != cmv.shift(1).sign()).cast(pl.Int8)
    flips_window = flip1.rolling_sum(lookback).fill_null(0)

    # 2) SPS exhaustion: was high recently and now cooling
    sps_peak = sps.shift(1).rolling_max(lookback).fill_null(0.0)
    sps_exhaust = (sps_peak > threshold_sps) & (sps < sps.shift(1))

    # 3) Absorption proxies
    absorb_bear = (ch < 0) & (mfi < mfi.shift(1))  # selling into strength
    absorb_bull = (ch > 0) & (mfi < 40)  # buying into weak hands

    # 4) Classify (vectorized)
    is_bear_trap = (flips_window > 0) & sps_exhaust & absorb_bear
    is_bull_trap = (flips_window > 0) & sps_exhaust & absorb_bull

    score = (
        pl.when(is_bear_trap)
        .then(pl.lit(2))
        .when(is_bull_trap)
        .then(pl.lit(-2))
        .otherwise(pl.lit(0))
        .alias(out_score_col)
    )
    label = (
        pl.when(is_bear_trap)
        .then(pl.lit("🟥 Bear Trap → Short Squeeze Setup"))
        .when(is_bull_trap)
        .then(pl.lit("🟩 Bull Trap → Long Liquidation Risk"))
        .otherwise(pl.lit("➡️ Stable"))
        .alias(out_col)
    )

    return df.with_columns([score, label])


# Registry export (callable, not a string)
EXPORTS = {"liquidity_trap": detect_liquidity_trap}

# ── Local smoke ─────────────────────────────────────────────
if __name__ == "__main__":
    import numpy as np

    n = 120
    df = pl.DataFrame(
        {
            "CMV": np.sin(np.linspace(0, 10, n)),  # oscillating CMV to force flips
            "SPS": np.clip(np.random.uniform(0.6, 0.95, n), 0, 1),
            "MFI": np.random.uniform(30, 70, n),
            "Chaikin_Osc": np.random.uniform(-1, 1, n),
        }
    )
    out = detect_liquidity_trap(df)
    print(out.select(["Liquidity_Trap_Score", "Liquidity_Trap"]).tail(8))
