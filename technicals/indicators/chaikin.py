# ============================================================
# queen/technicals/indicators/volume_chaikin.py
# ------------------------------------------------------------
# ⚙️ Chaikin Oscillator — Volume Momentum Engine
# Config-driven, NaN-safe, headless for Quant-Core v4.x
# Measures rate of change in accumulation/distribution
# ============================================================

import json

import numpy as np
import polars as pl
from quant.config import get_indicator_params
from quant.signals.utils_indicator_health import _log_indicator_warning
from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🔧 Helper: Exponential Moving Average
# ============================================================
def ema(series: np.ndarray, span: int) -> np.ndarray:
    """Compute Exponential Moving Average."""
    if len(series) == 0:
        return np.array([])
    alpha = 2 / (span + 1)
    result = np.zeros_like(series, dtype=float)
    result[0] = series[0]
    for i in range(1, len(series)):
        result[i] = alpha * series[i] + (1 - alpha) * result[i - 1]
    return result


# ============================================================
# 🧠 Core Chaikin Computation
# ============================================================
def compute_chaikin(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Compute Chaikin Oscillator and volume momentum metrics."""
    params = get_indicator_params("CHAiKIN", context)
    short_period = params.get("short_period", 3)
    long_period = params.get("long_period", 10)

    df = df.clone()
    required_cols = {"high", "low", "close", "volume"}
    if not required_cols.issubset(df.columns):
        _log_indicator_warning(
            "CHAiKIN",
            context,
            f"Missing required columns {required_cols - set(df.columns)} — skipping computation.",
        )
        return df

    high = df["high"].to_numpy().astype(float)
    low = df["low"].to_numpy().astype(float)
    close = df["close"].to_numpy().astype(float)
    volume = df["volume"].to_numpy().astype(float)

    # Money Flow Multiplier & Volume
    mfm = ((close - low) - (high - close)) / (high - low + 1e-9)
    mfv = mfm * volume

    # Accumulation/Distribution Line
    adl = np.cumsum(mfv)

    # Chaikin Oscillator (EMA difference)
    adl_ema_short = ema(adl, short_period)
    adl_ema_long = ema(adl, long_period)
    chaikin_osc = adl_ema_short - adl_ema_long

    # Normalization
    chaikin_min, chaikin_max = np.nanmin(chaikin_osc), np.nanmax(chaikin_osc)
    if np.isfinite(chaikin_max - chaikin_min) and (chaikin_max - chaikin_min) > 0:
        norm = np.clip((chaikin_osc - chaikin_min) / (chaikin_max - chaikin_min), 0, 1)
    else:
        norm = np.zeros_like(chaikin_osc)
        _log_indicator_warning(
            "CHAiKIN", context, "Zero or invalid normalization range detected."
        )

    # Bias classification
    bias = np.full(len(chaikin_osc), "➡️ Neutral", dtype=object)
    bias[chaikin_osc > 0] = "📈 Bullish Flow"
    bias[chaikin_osc < 0] = "📉 Bearish Flow"

    # Momentum flag (acceleration detection)
    flow_change = np.diff(chaikin_osc, prepend=chaikin_osc[0])
    flow = np.where(
        flow_change > 0,
        "⬆️ Accumulating",
        np.where(flow_change < 0, "⬇️ Distributing", "➡️ Stable"),
    )

    return df.with_columns(
        [
            pl.Series("Chaikin_ADL", adl),
            pl.Series("Chaikin_Osc", chaikin_osc),
            pl.Series("Chaikin_norm", norm),
            pl.Series("Chaikin_Bias", bias),
            pl.Series("Chaikin_Flow", flow),
        ]
    )


# ============================================================
# 📊 Diagnostic Summary
# ============================================================
def summarize_chaikin(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit/fusion layers."""
    if df.is_empty() or "Chaikin_Osc" not in df.columns:
        return {"status": "empty"}

    last_val = float(df["Chaikin_Osc"][-1])
    bias = str(df["Chaikin_Bias"][-1])
    flow = str(df["Chaikin_Flow"][-1])

    state = (
        "🟩 Expanding Volume"
        if "Bullish" in bias
        else "🟥 Contracting Volume"
        if "Bearish" in bias
        else "⬜ Neutral"
    )

    return {
        "Chaikin_Osc": round(last_val, 3),
        "Bias": bias,
        "Flow": flow,
        "State": state,
    }


# ============================================================
# 🧪 Local Dev Diagnostic (Headless Snapshot)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 150
    base = np.linspace(100, 120, n) + np.random.normal(0, 1.5, n)
    high = base + np.random.uniform(0.5, 2.0, n)
    low = base - np.random.uniform(0.5, 2.0, n)
    close = base + np.random.normal(0, 0.5, n)
    volume = np.random.randint(1000, 5000, n)

    df = pl.DataFrame({"high": high, "low": low, "close": close, "volume": volume})
    df = compute_chaikin(df, context="intraday_15m")
    summary = summarize_chaikin(df)

    # ✅ Config-driven snapshot
    snapshot_path = get_dev_snapshot_path("volume_chaikin")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"📊 [Headless] Chaikin snapshot written → {snapshot_path}")
