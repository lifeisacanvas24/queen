#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/tactical/tactical_liquidity_trap.py
# ------------------------------------------------------------
# ⚙️ Liquidity Trap & Absorption Candle Detection (Polars-native)
# Detects false breakouts and smart-money absorption using CMV/SPS
# and volume momentum proxies (MFI/Chaikin). Vectorized & fast.
# ============================================================

from __future__ import annotations
import numpy as np
import polars as pl

# Optional: export into the discovery registry
EXPORTS = {"liquidity_trap": "detect_liquidity_trap"}


def detect_liquidity_trap(
    df: pl.DataFrame,
    *,
    cmv_col: str = "CMV",
    sps_col: str = "SPS",
    mfi_col: str = "MFI",
    chaikin_col: str = "Chaikin_Osc",
    threshold_sps: float = 0.85,
    lookback: int = 5,
) -> pl.DataFrame:
    """
    Adds one column:
      • Liquidity_Trap: "🟥 Bear Trap → Short Squeeze Setup" / "🟩 Bull Trap → Long Liquidation Risk" / "➡️ Stable"
    """
    # Safety
    req = {cmv_col, sps_col}
    if not req.issubset(df.columns):
        return df.with_columns(pl.lit("➡️ Skipped").alias("Liquidity_Trap"))

    out = df.clone()

    # Pull (optional) helpers; if missing, treat as neutral zeros
    has_mfi = mfi_col in out.columns
    has_ch = chaikin_col in out.columns

    cmv = pl.col(cmv_col).fill_null(0.0)
    sps = pl.col(sps_col).fill_null(0.0)
    mfi = pl.col(mfi_col).fill_null(50.0) if has_mfi else pl.lit(50.0)
    ch = pl.col(chaikin_col).fill_null(0.0) if has_ch else pl.lit(0.0)

    # Basic ingredients
    cmv_flip = (cmv.shift(1) * cmv) < 0  # sign change
    sps_exhausted = (sps.shift(1) > threshold_sps) & (sps < sps.shift(1))

    # Volume-absorption proxy:
    # bearish absorption: chaikin<0 & mfi falling
    # bullish absorption: chaikin>0 & mfi < 40
    vol_absorb_bear = (ch < 0) & (mfi < mfi.shift(1))
    vol_absorb_bull = (ch > 0) & (mfi < 40)

    # Class rules
    is_bear_trap = cmv_flip & sps_exhausted & vol_absorb_bear
    is_bull_trap = cmv_flip & sps_exhausted & vol_absorb_bull

    signal = (
        pl.when(is_bear_trap)
        .then(pl.lit("🟥 Bear Trap → Short Squeeze Setup"))
        .when(is_bull_trap)
        .then(pl.lit("🟩 Bull Trap → Long Liquidation Risk"))
        .otherwise(pl.lit("➡️ Stable"))
        .alias("Liquidity_Trap")
    )

    return out.with_columns(signal)
