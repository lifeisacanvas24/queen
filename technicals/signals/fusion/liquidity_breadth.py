#!/usr/bin/env python3
# ============================================================
# Liquidity–Breadth Fusion (LBX) — v2.0
# ============================================================
from __future__ import annotations
import numpy as np
import polars as pl


def compute_liquidity_breadth_fusion(
    df: pl.DataFrame, *, context: str = "default"
) -> pl.DataFrame:
    """Fuse CMV + SPS + Volume into Liquidity–Breadth Index (LBX)."""
    if df.is_empty():
        return df

    out = df
    n = out.height
    zeros = np.zeros(n)

    cmv = out["CMV"].to_numpy() if "CMV" in out.columns else zeros
    sps = out["SPS"].to_numpy() if "SPS" in out.columns else zeros
    vol = out["volume"].to_numpy() if "volume" in out.columns else zeros

    vol_ratio = np.divide(
        vol,
        np.maximum(np.convolve(vol, np.ones(5) / 5, mode="same"), 1),
        out=zeros,
        where=np.isfinite(vol),
    )

    lbx_raw = 0.4 * cmv + 0.4 * sps + 0.2 * _norm01(vol_ratio)
    lbx_norm = _norm01(lbx_raw)

    bias = np.full(n, "⚪ Neutral", dtype=object)
    bias[lbx_norm > 0.6] = "🟢 Risk-On"
    bias[lbx_norm < 0.4] = "🔴 Risk-Off"

    return out.with_columns(
        [
            pl.Series("LBX", lbx_raw),
            pl.Series("LBX_norm", lbx_norm),
            pl.Series("LBX_bias", bias, dtype=pl.Utf8),
        ]
    )


def _norm01(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    lo, hi = np.nanmin(arr), np.nanmax(arr)
    rng = hi - lo
    if rng == 0 or not np.isfinite(rng):
        return np.zeros_like(arr)
    out = (arr - lo) / rng
    return np.clip(out, 0.0, 1.0)
