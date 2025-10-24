# ============================================================
# quant/signals/indicators/volume_mfi.py
# ------------------------------------------------------------
# ⚙️ Money Flow Index (MFI)
# Config-driven, NaN-safe, headless for Quant-Core v4.x
# Detects volume-weighted accumulation & distribution momentum
# ============================================================

import json

import numpy as np
import polars as pl

from quant.config import get_indicator_params
from quant.signals.utils_indicator_health import _log_indicator_warning
from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🧮 Core Money Flow Index Computation
# ============================================================
def compute_mfi(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Compute Money Flow Index (MFI) with config-driven parameters."""
    params = get_indicator_params("MFI", context)
    period = params.get("period", 14)
    overbought = params.get("overbought", 70)
    oversold = params.get("oversold", 30)

    df = df.clone()
    required_cols = {"high", "low", "close", "volume"}
    if not required_cols.issubset(df.columns):
        _log_indicator_warning(
            "MFI",
            context,
            f"Missing required columns {required_cols - set(df.columns)} — skipping computation.",
        )
        return df

    high = df["high"].to_numpy().astype(float)
    low = df["low"].to_numpy().astype(float)
    close = df["close"].to_numpy().astype(float)
    volume = df["volume"].to_numpy().astype(float)

    if len(close) < period + 2:
        _log_indicator_warning("MFI", context, f"Insufficient data (<{period+2}) for MFI.")
        return df

    # Typical Price
    typical_price = (high + low + close) / 3

    # Raw Money Flow
    money_flow = typical_price * volume

    # Positive / Negative flow separation
    positive_flow = np.zeros_like(money_flow)
    negative_flow = np.zeros_like(money_flow)
    for i in range(1, len(typical_price)):
        if typical_price[i] > typical_price[i - 1]:
            positive_flow[i] = money_flow[i]
        elif typical_price[i] < typical_price[i - 1]:
            negative_flow[i] = money_flow[i]

    # Rolling sums (efficient convolution)
    pos_sum = np.convolve(positive_flow, np.ones(period), "valid")
    neg_sum = np.convolve(negative_flow, np.ones(period), "valid")

    # Money Flow Ratio and MFI
    mfr = np.divide(pos_sum, neg_sum + 1e-9)
    mfi = 100 - (100 / (1 + mfr))

    # Pad to align with input
    mfi_full = np.concatenate([np.full(period - 1, np.nan), mfi])
    mfi_norm = np.clip(mfi_full / 100, 0, 1)

    # Bias classification
    bias = np.full(len(mfi_full), "➡️ Neutral", dtype=object)
    bias[mfi_full > overbought] = "📉 Distribution"
    bias[mfi_full < oversold] = "📈 Accumulation"

    # Flow direction flag
    bias_change = np.concatenate([[0], np.diff(np.nan_to_num(mfi_full, nan=0))])
    flow = np.where(
        bias_change > 0,
        "⬆️ Inflow",
        np.where(bias_change < 0, "⬇️ Outflow", "➡️ Flat"),
    )

    df = df.with_columns([
        pl.Series("MFI", mfi_full),
        pl.Series("MFI_norm", mfi_norm),
        pl.Series("MFI_Bias", bias),
        pl.Series("MFI_Flow", flow),
    ])

    # Diagnostics for NaN
    if np.isnan(mfi_full).any():
        _log_indicator_warning("MFI", context, "Detected NaN values in MFI — incomplete rolling window or invalid input.")

    return df


# ============================================================
# 📊 Diagnostic Summary
# ============================================================
def summarize_mfi(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit/fusion layers."""
    if df.is_empty() or "MFI" not in df.columns:
        return {"status": "empty"}

    last_mfi = float(df["MFI"].drop_nulls()[-1])
    bias = str(df["MFI_Bias"].drop_nulls()[-1])
    flow = str(df["MFI_Flow"].drop_nulls()[-1])

    state = (
        "🟩 Accumulation" if "Accumulation" in bias
        else "🟥 Distribution" if "Distribution" in bias
        else "⬜ Neutral"
    )

    return {
        "MFI": round(last_mfi, 2),
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
    df = compute_mfi(df, context="intraday_15m")
    summary = summarize_mfi(df)

    # ✅ Config-driven snapshot
    snapshot_path = get_dev_snapshot_path("volume_mfi")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"📊 [Headless] Money Flow snapshot written → {snapshot_path}")
