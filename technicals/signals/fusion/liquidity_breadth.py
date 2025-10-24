# ============================================================
# quant/signals/fusion/liquidity_breadth_fusion.py
# ------------------------------------------------------------
# ⚙️ Liquidity–Breadth Fusion Layer — Quant-Core v4.x
# ------------------------------------------------------------
# Combines:
#   • Chaikin (volume momentum)
#   • Breadth Momentum & Persistence
#   • Volatility Fusion (VolX_norm)
# Produces:
#   • LiquidityBreadthIndex (LBX)
#   • LBX_norm, LBX_bias, and Regime classification
# ============================================================

import json

import numpy as np
import polars as pl
from quant.config import get_indicator_params
from quant.signals.fusion.volatility_fusion import compute_volatility_fusion
from quant.signals.indicators.breadth_cumulative import compute_breadth
from quant.signals.indicators.breadth_momentum import compute_breadth_momentum
from quant.signals.indicators.volume_chaikin import compute_chaikin
from quant.signals.utils_indicator_health import _log_indicator_warning
from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🧠 Core Fusion Computation
# ============================================================
def compute_liquidity_breadth_fusion(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Fuse Chaikin + Breadth + Volatility into unified Liquidity–Breadth Index (LBX)."""
    params = get_indicator_params("LIQUIDITY_BREADTH_FUSION", context)
    weight_volume = params.get("weight_volume", 0.4)
    weight_breadth = params.get("weight_breadth", 0.4)
    weight_volatility = params.get("weight_volatility", 0.2)
    normalize_window = params.get("normalize_window", 50)
    bias_threshold = params.get("bias_threshold", 0.6)

    df = df.clone()

    # --- Volume (Chaikin) ---
    if {"high", "low", "close", "volume"}.issubset(df.columns):
        df_vol = compute_chaikin(df, context=context)
        vol_norm = df_vol["Chaikin_norm"].to_numpy().astype(float)
    else:
        _log_indicator_warning("LBX", context, "Missing OHLCV columns — cannot compute Chaikin volume.")
        vol_norm = np.zeros(len(df))

    # --- Breadth Momentum + Persistence ---
    breadth_inputs = {"CMV", "SPS"}
    if breadth_inputs.issubset(df.columns):
        df_bm = compute_breadth_momentum(df, context=context)
        df_bc = compute_breadth(df, context=context)
        breadth_norm = np.clip((df_bm["Breadth_Momentum"].to_numpy() + df_bc["Breadth_Persistence"].to_numpy()) / 2, -1, 1)
    else:
        _log_indicator_warning("LBX", context, f"Missing breadth columns {breadth_inputs - set(df.columns)}.")
        breadth_norm = np.zeros(len(df))

    # --- Volatility (VolX) ---
    if {"high", "low", "close"}.issubset(df.columns):
        df_volx = compute_volatility_fusion(df, context=context)
        volx_norm = df_volx["VolX_norm"].to_numpy().astype(float)
    else:
        _log_indicator_warning("LBX", context, "Missing OHLC columns — cannot compute VolX_norm.")
        volx_norm = np.zeros(len(df))

    # --- Combine Weighted Fusion ---
    lbx = (weight_volume * vol_norm) + (weight_breadth * breadth_norm) + (weight_volatility * (1 - volx_norm))

    # --- Normalize LBX ---
    with np.errstate(all="ignore"):
        rolling_max = np.maximum.accumulate(lbx)
        rolling_min = np.minimum.accumulate(lbx)
    lbx_norm = np.divide(
        lbx - rolling_min,
        np.maximum(rolling_max - rolling_min, 1e-9),
        out=np.zeros_like(lbx),
        where=(rolling_max - rolling_min) != 0
    )
    lbx_norm = np.nan_to_num(lbx_norm)

    # --- Regime Bias ---
    bias = np.full(len(lbx_norm), "⚪ Neutral", dtype=object)
    bias[lbx_norm > bias_threshold] = "🟢 Risk-On"
    bias[lbx_norm < (1 - bias_threshold)] = "🔴 Risk-Off"

    return df.with_columns([
        pl.Series("LBX", lbx),
        pl.Series("LBX_norm", lbx_norm),
        pl.Series("LBX_bias", bias),
    ])


# ============================================================
# 📊 Diagnostic Summary
# ============================================================
def summarize_liquidity_breadth(df: pl.DataFrame) -> dict:
    """Return structured summary for tactical overlay."""
    if df.is_empty() or "LBX_norm" not in df.columns:
        return {"status": "empty"}

    last_val = float(df["LBX_norm"][-1])
    bias = str(df["LBX_bias"][-1])
    regime = (
        "📈 Risk-On" if "Risk-On" in bias
        else "📉 Risk-Off" if "Risk-Off" in bias
        else "⚪ Neutral"
    )

    return {
        "LBX_norm": round(last_val, 3),
        "LBX_bias": bias,
        "Regime": regime,
    }


# ============================================================
# 🧪 Local Dev Diagnostic (Headless Snapshot)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 200
    base = np.linspace(100, 115, n) + np.random.normal(0, 1.2, n)
    high = base + np.random.uniform(0.3, 1.5, n)
    low = base - np.random.uniform(0.3, 1.5, n)
    close = base + np.random.normal(0, 0.5, n)
    volume = np.random.randint(1000, 5000, n)
    cmv = np.sin(np.linspace(0, 4, n)) + np.random.normal(0, 0.05, n)
    sps = np.cos(np.linspace(0, 4, n)) + np.random.normal(0, 0.05, n)

    df = pl.DataFrame({"high": high, "low": low, "close": close, "volume": volume, "CMV": cmv, "SPS": sps})
    df = compute_liquidity_breadth_fusion(df, context="intraday_15m")
    summary = summarize_liquidity_breadth(df)

    # ✅ Config-driven snapshot
    snapshot_path = get_dev_snapshot_path("liquidity_breadth_fusion")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"📊 [Headless] Liquidity-Breadth Fusion snapshot written → {snapshot_path}")
