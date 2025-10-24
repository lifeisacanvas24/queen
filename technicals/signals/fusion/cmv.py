# ============================================================
# quant/signals/fusion_cmv.py
# ------------------------------------------------------------
# ⚙️ Composite Momentum Vector (CMV) Engine
# Fuses momentum, volume, volatility, and setup pressure into
# a single directional quant signal for your cockpit.
# ============================================================

import numpy as np
import polars as pl


# ============================================================
# 🔧 Helper — Normalization
# ============================================================
def normalize_series(series: np.ndarray, min_val: float = None, max_val: float = None) -> np.ndarray:
    """Normalize series between -1.0 and +1.0."""
    arr = np.array(series, dtype=float)
    if min_val is None:
        min_val = np.nanmin(arr)
    if max_val is None:
        max_val = np.nanmax(arr)
    if max_val - min_val == 0:
        return np.zeros_like(arr)
    scaled = 2 * (arr - min_val) / (max_val - min_val) - 1
    return np.clip(scaled, -1, 1)


# ============================================================
# 🧠 Core CMV Computation
# ============================================================
# ============================================================
# 🧠 Core CMV Computation
# ============================================================
def compute_cmv(df: pl.DataFrame) -> pl.DataFrame:
    """Compute Composite Momentum Vector (CMV) and bias classification."""
    df = df.clone()

    # --- Safety Guards ---
    required_cols = ["rsi_14", "obv", "SPS", "close", "volume"]
    for c in required_cols:
        if c not in df.columns:
            df = df.with_columns(pl.lit(0).alias(c))

    # --- Normalize Inputs ---
    norm_rsi = normalize_series(df["rsi_14"].to_numpy(), 0, 100)
    norm_obv = normalize_series(df["obv"].to_numpy())
    norm_sps = normalize_series(df["SPS"].to_numpy())
    norm_vpr = normalize_series(
        (df["volume"].to_numpy() / np.maximum(df["volume"].rolling_mean(5).fill_nan(0).to_numpy(), 1)) - 1
    )

    # Optional pattern bias (if available)
    pattern_bias = df["pattern_bias"].to_numpy() if "pattern_bias" in df.columns else np.zeros(len(df))

    # --- Composite Fusion Formula ---
    cmv_raw = (
        0.25 * norm_rsi
        + 0.20 * norm_obv
        + 0.20 * norm_vpr
        + 0.25 * norm_sps
        + 0.10 * pattern_bias
    )

    # --- Smooth the CMV ---
    cmv_smooth = np.convolve(cmv_raw, np.ones(5) / 5, mode="same")

    # --- Bias Classification ---
    bias_labels = []
    cmv_trend = []
    cmv_flip = []

    for i in range(len(cmv_smooth)):
        val = cmv_smooth[i]

        if val >= 0.8:
            bias = "🟩 Strong Bullish"
        elif val >= 0.4:
            bias = "🟢 Mild Bullish"
        elif val <= -0.8:
            bias = "🟥 Strong Bearish"
        elif val <= -0.4:
            bias = "🔻 Mild Bearish"
        else:
            bias = "🟨 Neutral"

        bias_labels.append(bias)

        # --- Trend detection ---
        if i > 0:
            if cmv_smooth[i] > cmv_smooth[i - 1]:
                cmv_trend.append(1)
            elif cmv_smooth[i] < cmv_smooth[i - 1]:
                cmv_trend.append(0)
            else:
                cmv_trend.append(None)
        else:
            cmv_trend.append(None)

        # --- Flip detection ---
        if i > 1:
            prev_bias = bias_labels[i - 1]
            cmv_flip.append(prev_bias != bias)
        else:
            cmv_flip.append(False)

    # --- Attach Canonical & Derived CMV Columns ---
    df = df.with_columns([
        pl.Series("CMV_raw", cmv_raw),
        pl.Series("CMV_smooth", cmv_smooth),
        pl.Series("CMV", cmv_smooth),        # ✅ Canonical CMV column for tactical engines
        pl.Series("CMV_Bias", bias_labels),
        pl.Series("CMV_TrendUp", cmv_trend),
        pl.Series("CMV_Flip", cmv_flip)
    ])

    return df

# ============================================================
# 🔍 Diagnostic Utility
# ============================================================
def summarize_cmv(df: pl.DataFrame) -> str:
    """Summarize CMV statistics for quick cockpit diagnostics."""
    avg_cmv = float(df["CMV_smooth"].mean())
    flips = int(np.sum(df["CMV_Flip"].to_numpy()))
    return f"Avg CMV: {avg_cmv:.3f} | Bias: {df['CMV_Bias'][-1]} | Flips: {flips}"
