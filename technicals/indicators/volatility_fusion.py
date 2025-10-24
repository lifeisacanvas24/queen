# ============================================================
# quant/signals/fusion/volatility_fusion.py
# ------------------------------------------------------------
# ⚙️ Volatility Diagnostic Fusion Layer — Quant-Core v4.x
# ------------------------------------------------------------
# Aggregates and normalizes multi-source volatility signals:
#   - Keltner Channel (mandatory)
#   - ATR proxy (optional / future-ready)
#   - Bollinger-style compression (optional)
# Produces: VolX, VolX_norm, and bias classification
# ============================================================

import json

import numpy as np
import polars as pl

from quant.config import get_indicator_params
from quant.signals.indicators.vol_keltner import compute_keltner
from quant.signals.utils_indicator_health import _log_indicator_warning
from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🧠 Volatility Fusion Core
# ============================================================
def compute_volatility_fusion(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Fuse volatility diagnostics from Keltner, ATR (proxy), and Bollinger bands."""
    params = get_indicator_params("VOL_FUSION", context)
    normalize_window = params.get("normalize_window", 50)
    weight_keltner = params.get("weight_keltner", 0.7)
    weight_atr = params.get("weight_atr", 0.3)
    vol_bias_threshold = params.get("bias_threshold", 0.6)

    df = df.clone()
    for col in ["high", "low", "close"]:
        if col not in df.columns:
            _log_indicator_warning("VOL_FUSION", context, f"Missing '{col}' column — cannot compute fusion.")
            return df

    # --- 1️⃣ Keltner Base ---
    df_kc = compute_keltner(df, context=context)
    if "KC_norm" not in df_kc.columns:
        _log_indicator_warning("VOL_FUSION", context, "Keltner output missing KC_norm.")
        return df_kc

    kc_norm = df_kc["KC_norm"].to_numpy().astype(float)

    # --- 2️⃣ ATR Proxy (optional) ---
    try:
        from quant.signals.indicators.vol_atr import compute_atr_indicator
        df_atr = compute_atr_indicator(df, context=context)
        atr_norm = df_atr["ATR_norm"].to_numpy().astype(float)
    except ImportError:
        atr_norm = kc_norm * 0.9
        _log_indicator_warning("VOL_FUSION", context, "vol_atr.py not found — using Keltner ATR proxy.")

    # --- 3️⃣ Fused Volatility Index ---
    volx = (weight_keltner * kc_norm) + (weight_atr * atr_norm)

    # --- 4️⃣ Rolling Normalization ---
    with np.errstate(all="ignore"):
        rolling_max = np.maximum.accumulate(volx)
        rolling_min = np.minimum.accumulate(volx)

    volx_norm = np.divide(
        volx - rolling_min,
        np.maximum(rolling_max - rolling_min, 1e-9),
        out=np.zeros_like(volx),
        where=(rolling_max - rolling_min) != 0
    )
    volx_norm = np.nan_to_num(volx_norm)

    # --- 5️⃣ Bias Classification ---
    bias = np.full(len(volx_norm), "➡️ Stable", dtype=object)
    bias[volx_norm > vol_bias_threshold] = "🟢 Expansion"
    bias[volx_norm < (1 - vol_bias_threshold)] = "🟡 Squeeze"

    # --- 6️⃣ Health Diagnostics ---
    if np.isnan(volx_norm).any():
        _log_indicator_warning("VOL_FUSION", context, "NaN detected in VolX_norm — check input data continuity.")

    return df_kc.with_columns([
        pl.Series("VolX", volx),
        pl.Series("VolX_norm", volx_norm),
        pl.Series("VolX_bias", bias),
    ])


# ============================================================
# 📊 Summary for Cockpit / Fusion Dashboard
# ============================================================
def summarize_volatility(df: pl.DataFrame) -> dict:
    """Return structured summary for tactical overlay."""
    if df.height == 0 or "VolX_norm" not in df.columns:
        return {"status": "empty"}

    last_val = float(df["VolX_norm"][-1])
    last_bias = str(df["VolX_bias"][-1])
    state = (
        "📈 Expansion" if "Expansion" in last_bias
        else "⚠️ Squeeze" if "Squeeze" in last_bias
        else "➡️ Stable"
    )

    return {
        "VolX_norm": round(last_val, 3),
        "VolX_bias": last_bias,
        "State": state
    }


# ============================================================
# 🧪 Local Dev Diagnostic (Headless Snapshot)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 250
    base = np.linspace(100, 120, n) + np.random.normal(0, 2.0, n)
    high = base + np.random.uniform(0.5, 2.0, n)
    low = base - np.random.uniform(0.5, 2.0, n)
    close = base + np.random.normal(0, 1.0, n)
    df = pl.DataFrame({"high": high, "low": low, "close": close})

    df = compute_volatility_fusion(df, context="intraday_15m")
    summary = summarize_volatility(df)

    # ✅ Config-driven snapshot (headless)
    snapshot_path = get_dev_snapshot_path("volatility_fusion")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"📊 [Headless] Volatility Fusion snapshot written → {snapshot_path}")
