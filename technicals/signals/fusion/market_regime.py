#!/usr/bin/env python3
# ============================================================
# Market Regime Fusion (RScore) — v2.0
# ============================================================
from __future__ import annotations
import numpy as np
import polars as pl
from queen.helpers.logger import log
from queen.technicals.signals.fusion.cmv import compute_cmv
from queen.technicals.signals.fusion.liquidity_breadth import (
    compute_liquidity_breadth_fusion,
)


def _norm01(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    lo, hi = np.nanmin(arr), np.nanmax(arr)
    rng = hi - lo
    if rng == 0 or not np.isfinite(rng):
        return np.zeros_like(arr)
    return np.clip((arr - lo) / rng, 0.0, 1.0)


def compute_market_regime(
    df: pl.DataFrame, *, context: str = "default"
) -> pl.DataFrame:
    """Compute composite RScore and bias classification."""
    if df.is_empty():
        return df

    out = df
    n = out.height
    zeros = np.zeros(n)

    # 1️⃣ Liquidity–Breadth
    try:
        lbx_df = compute_liquidity_breadth_fusion(out)
        lbx_norm = lbx_df["LBX_norm"].to_numpy()
    except Exception as e:
        log.warning(f"[RScore] LBX skipped → {e}")
        lbx_norm = zeros

    # 2️⃣ Volatility proxy (ATR-lite)
    high = out["high"].to_numpy() if "high" in out.columns else zeros
    low = out["low"].to_numpy() if "low" in out.columns else zeros
    close = out["close"].to_numpy() if "close" in out.columns else zeros
    tr = np.maximum.reduce([high - low, np.abs(high - close), np.abs(low - close)])
    vol_norm = 1.0 - _norm01(np.convolve(tr, np.ones(5) / 5, mode="same"))

    # 3️⃣ Trend proxy (CMV)
    try:
        cmv_df = compute_cmv(out)
        cmv_arr = _norm01(np.abs(cmv_df["CMV_smooth"].to_numpy()))
    except Exception as e:
        log.warning(f"[RScore] CMV skipped → {e}")
        cmv_arr = zeros

    # 4️⃣ Composite RScore
    rscore = 0.35 * lbx_norm + 0.25 * vol_norm + 0.25 * cmv_arr + 0.15 * 0.5
    rscore_norm = _norm01(rscore)

    bias = np.full(n, "⚪ Neutral", dtype=object)
    bias[rscore_norm > 0.6] = "🟢 Risk-On"
    bias[rscore_norm < 0.4] = "🔴 Risk-Off"

    return out.with_columns(
        [
            pl.Series("RScore", rscore),
            pl.Series("RScore_norm", rscore_norm),
            pl.Series("RScore_bias", bias, dtype=pl.Utf8),
        ]
    )
