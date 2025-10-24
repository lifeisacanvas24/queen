# ============================================================
# quant/signals/fusion/market_regime_fusion.py
# ------------------------------------------------------------
# ⚙️ Market Regime Fusion Layer — Quant-Core v4.x
# ------------------------------------------------------------
# Fuses:
#   • Liquidity–Breadth Index (LBX)
#   • Volatility Fusion (VolX_norm)
#   • Trend Momentum (MACD / ADX)
#   • Optional Sentiment / Macro Overlay
# Produces:
#   • RScore (composite regime index)
#   • RScore_norm, RScore_bias, Regime classification
# ============================================================

import json

import numpy as np
import polars as pl
from quant.config import get_indicator_params
from quant.signals.fusion.liquidity_breadth_fusion import (
    compute_liquidity_breadth_fusion,
)
from quant.signals.fusion.volatility_fusion import compute_volatility_fusion
from quant.signals.indicators.adx import compute_adx
from quant.signals.indicators.macd import compute_macd
from quant.signals.utils_indicator_health import _log_indicator_warning
from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🧠 Core Market Regime Fusion
# ============================================================
def compute_market_regime(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Fuse liquidity, breadth, volatility, and trend into unified R-Score."""
    params = get_indicator_params("MARKET_REGIME_FUSION", context)
    weight_liquidity = params.get("weight_liquidity", 0.35)
    weight_volatility = params.get("weight_volatility", 0.25)
    weight_trend = params.get("weight_trend", 0.25)
    weight_sentiment = params.get("weight_sentiment", 0.15)
    bias_threshold = params.get("bias_threshold", 0.6)

    df = df.clone()

    # --- 1️⃣ Liquidity–Breadth Index ---
    if {"high", "low", "close", "volume", "CMV", "SPS"}.issubset(df.columns):
        df_lbx = compute_liquidity_breadth_fusion(df, context=context)
        lbx_norm = df_lbx["LBX_norm"].to_numpy().astype(float)
    else:
        _log_indicator_warning("RScore", context, "Missing LBX prerequisites — using zeros.")
        lbx_norm = np.zeros(len(df))

    # --- 2️⃣ Volatility Fusion ---
    if {"high", "low", "close"}.issubset(df.columns):
        df_vol = compute_volatility_fusion(df, context=context)
        vol_norm = 1 - df_vol["VolX_norm"].to_numpy().astype(float)  # inverted: low vol = risk-on
    else:
        _log_indicator_warning("RScore", context, "Missing OHLC columns — skipping volatility fusion.")
        vol_norm = np.zeros(len(df))

    # --- 3️⃣ Trend Momentum (MACD + ADX) ---
    if "close" in df.columns:
        df_macd = compute_macd(df, context=context)
        df_adx = compute_adx(df, context=context)
        macd_norm = df_macd["MACD_norm"].to_numpy().astype(float)
        adx_norm = np.clip(df_adx["ADX"] / 100, 0, 1)
        trend_strength = (macd_norm + adx_norm) / 2
    else:
        _log_indicator_warning("RScore", context, "Missing close column for trend.")
        trend_strength = np.zeros(len(df))

    # --- 4️⃣ Optional Sentiment (future hook) ---
    # For now, neutral placeholder
    sentiment = np.full(len(df), 0.5)

    # --- 5️⃣ Compute Composite R-Score ---
    rscore = (
        weight_liquidity * lbx_norm +
        weight_volatility * vol_norm +
        weight_trend * trend_strength +
        weight_sentiment * sentiment
    )

    # --- Normalize R-Score ---
    with np.errstate(all="ignore"):
        rolling_max = np.maximum.accumulate(rscore)
        rolling_min = np.minimum.accumulate(rscore)
    rscore_norm = np.divide(
        rscore - rolling_min,
        np.maximum(rolling_max - rolling_min, 1e-9),
        out=np.zeros_like(rscore),
        where=(rolling_max - rolling_min) != 0
    )
    rscore_norm = np.nan_to_num(rscore_norm)

    # --- Regime Bias Classification ---
    bias = np.full(len(rscore_norm), "⚪ Neutral", dtype=object)
    bias[rscore_norm > bias_threshold] = "🟢 Risk-On"
    bias[rscore_norm < (1 - bias_threshold)] = "🔴 Risk-Off"

    return df.with_columns([
        pl.Series("RScore", rscore),
        pl.Series("RScore_norm", rscore_norm),
        pl.Series("RScore_bias", bias),
    ])


# ============================================================
# 📊 Diagnostic Summary
# ============================================================
def summarize_market_regime(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit / dashboard."""
    if df.is_empty() or "RScore_norm" not in df.columns:
        return {"status": "empty"}

    last_val = float(df["RScore_norm"][-1])
    bias = str(df["RScore_bias"][-1])
    regime = (
        "📈 Risk-On Expansion" if "Risk-On" in bias
        else "📉 Risk-Off Contraction" if "Risk-Off" in bias
        else "⚪ Transitional Neutral"
    )

    return {
        "RScore_norm": round(last_val, 3),
        "RScore_bias": bias,
        "Regime": regime,
    }


# ============================================================
# 🧪 Local Dev Diagnostic (Headless Snapshot)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 220
    base = np.linspace(100, 120, n) + np.random.normal(0, 1.5, n)
    high = base + np.random.uniform(0.5, 2.0, n)
    low = base - np.random.uniform(0.5, 2.0, n)
    close = base + np.random.normal(0, 0.8, n)
    volume = np.random.randint(1000, 4000, n)
    cmv = np.sin(np.linspace(0, 5, n)) + np.random.normal(0, 0.05, n)
    sps = np.cos(np.linspace(0, 5, n)) + np.random.normal(0, 0.05, n)

    df = pl.DataFrame({"high": high, "low": low, "close": close, "volume": volume, "CMV": cmv, "SPS": sps})
    df = compute_market_regime(df, context="intraday_15m")
    summary = summarize_market_regime(df)

    # ✅ Config-driven snapshot
    snapshot_path = get_dev_snapshot_path("market_regime_fusion")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"📊 [Headless] Market Regime Fusion snapshot written → {snapshot_path}")
