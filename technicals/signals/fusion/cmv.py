#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/fusion/cmv.py — v2.0
# ------------------------------------------------------------
# ⚙️ Composite Momentum Vector (CMV) — fast Polars version
# ============================================================
from __future__ import annotations

import numpy as np
import polars as pl


# ---------- helpers ----------
def _norm_pm1(
    arr: np.ndarray, lo: float | None = None, hi: float | None = None
) -> np.ndarray:
    if arr.size == 0:
        return arr
    lo = np.nanmin(arr) if lo is None else lo
    hi = np.nanmax(arr) if hi is None else hi
    rng = hi - lo
    if rng == 0 or not np.isfinite(rng):
        return np.zeros_like(arr)
    out = 2.0 * (arr - lo) / rng - 1.0
    return np.clip(out, -1.0, 1.0)


# ---------- core ----------
def compute_cmv(df: pl.DataFrame) -> pl.DataFrame:
    """Compute Composite Momentum Vector (CMV) and bias."""
    if df.is_empty():
        return df

    out = df
    n = out.height
    zeros = np.zeros(n)

    # cache columns once
    rsi = out["rsi_14"].to_numpy() if "rsi_14" in out.columns else zeros
    obv = out["obv"].to_numpy() if "obv" in out.columns else zeros
    sps = out["SPS"].to_numpy() if "SPS" in out.columns else zeros
    vol = out["volume"].to_numpy() if "volume" in out.columns else zeros
    pat = out["pattern_bias"].to_numpy() if "pattern_bias" in out.columns else zeros

    vol_ratio = (
        np.divide(
            vol,
            np.maximum(np.convolve(vol, np.ones(5) / 5, mode="same"), 1),
            out=zeros,
            where=np.isfinite(vol),
        )
        - 1
    )

    cmv_raw = (
        0.25 * _norm_pm1(rsi, 0, 100)
        + 0.20 * _norm_pm1(obv)
        + 0.20 * _norm_pm1(vol_ratio)
        + 0.25 * _norm_pm1(sps)
        + 0.10 * pat
    )

    cmv_smooth = np.convolve(cmv_raw, np.ones(5) / 5, mode="same")

    bias = np.full(n, "🟨 Neutral", dtype=object)
    bias[cmv_smooth >= 0.8] = "🟩 Strong Bullish"
    bias[(cmv_smooth >= 0.4) & (cmv_smooth < 0.8)] = "🟢 Mild Bullish"
    bias[cmv_smooth <= -0.8] = "🟥 Strong Bearish"
    bias[(cmv_smooth <= -0.4) & (cmv_smooth > -0.8)] = "🔻 Mild Bearish"

    trend_up = np.diff(cmv_smooth, prepend=cmv_smooth[0]) > 0
    flip = np.concatenate(([False], bias[1:] != bias[:-1]))

    return out.with_columns(
        [
            pl.Series("CMV_raw", cmv_raw),
            pl.Series("CMV_smooth", cmv_smooth),
            pl.Series("CMV", cmv_smooth),
            pl.Series("CMV_Bias", bias, dtype=pl.Utf8),
            pl.Series("CMV_TrendUp", trend_up.astype(int)),
            pl.Series("CMV_Flip", flip),
        ]
    )
