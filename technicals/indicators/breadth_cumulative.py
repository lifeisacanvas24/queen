# ============================================================
# quant/signals/indicators/breadth_cumulative.py
# ------------------------------------------------------------
# ⚙️ Cumulative Breadth & Persistence Engine (Headless)
# Config-driven, NaN-safe, with diagnostic snapshot logging
# ============================================================

import json

import numpy as np
import polars as pl

from quant.config import get_indicator_params
from quant.signals.utils_indicator_health import _log_indicator_warning
from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🧠 Core Breadth Computation
# ============================================================
def compute_breadth(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Compute cumulative breadth from CMV/SPS columns:
    - CMV_Breadth (rolling mean)
    - SPS_Breadth (rolling mean)
    - Breadth_Persistence (average bias strength)
    - Breadth_Bias (Bullish/Bearish/Neutral)
    """
    params = get_indicator_params("BREADTH_CUMULATIVE", context)
    window = params.get("window", 10)
    threshold_bullish = params.get("threshold_bullish", 0.2)
    threshold_bearish = params.get("threshold_bearish", -0.2)

    df = df.clone()

    # --- Validate required inputs
    required_cols = {"CMV", "SPS"}
    if not required_cols.issubset(df.columns):
        _log_indicator_warning(
            "BREADTH_CUMULATIVE",
            context,
            f"Missing required columns {required_cols - set(df.columns)} — skipping computation."
        )
        return df

    # --- Handle NaN/inf values safely
    df = df.with_columns([
        pl.col("CMV").fill_null(0).fill_nan(0),
        pl.col("SPS").fill_null(0).fill_nan(0)
    ])

    # --- Rolling means
    df = df.with_columns([
        pl.col("CMV").rolling_mean(window_size=window).alias("CMV_Breadth"),
        pl.col("SPS").rolling_mean(window_size=window).alias("SPS_Breadth")
    ])

    # --- Breadth persistence
    df = df.with_columns([
        (((pl.col("CMV_Breadth") + pl.col("SPS_Breadth")) / 2)
         .clip(-1, 1)
         .alias("Breadth_Persistence"))
    ])

    # --- Bias classification
    df = df.with_columns([
        pl.when(pl.col("Breadth_Persistence") > threshold_bullish)
        .then(pl.lit("🟢 Bullish"))
        .when(pl.col("Breadth_Persistence") < threshold_bearish)
        .then(pl.lit("🔴 Bearish"))
        .otherwise(pl.lit("⚪ Neutral"))
        .alias("Breadth_Bias")
    ])

    # --- Health diagnostic
    if df["Breadth_Persistence"].null_count() > 0:
        _log_indicator_warning(
            "BREADTH_CUMULATIVE",
            context,
            "Detected NaN values in Breadth_Persistence — check CMV/SPS sources."
        )

    return df


# ============================================================
# 📊 Diagnostic Summary (Headless)
# ============================================================
def summarize_breadth(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit/fusion layers."""
    if df.is_empty() or "Breadth_Bias" not in df.columns:
        return {"status": "empty"}

    last_persist = float(df["Breadth_Persistence"][-1])
    bias = str(df["Breadth_Bias"][-1])

    strength = (
        "Strong" if abs(last_persist) > 0.6 else
        "Moderate" if abs(last_persist) > 0.3 else
        "Weak"
    )

    return {
        "Breadth_Persistence": round(last_persist, 3),
        "Bias": bias,
        "Strength": strength
    }


# ============================================================
# 🧪 Standalone Headless Test (Config-Driven)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 120
    cmv = np.sin(np.linspace(0, 6, n)) + np.random.normal(0, 0.1, n)
    sps = np.cos(np.linspace(0, 6, n)) + np.random.normal(0, 0.1, n)
    df = pl.DataFrame({"CMV": cmv, "SPS": sps})

    df = compute_breadth(df, context="daily")
    summary = summarize_breadth(df)

    # ✅ Headless diagnostic snapshot (no prints)
    snapshot_path = get_dev_snapshot_path("breadth_cumulative")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Optional console echo in dev mode (safe)
    print(f"📊 [Headless] Snapshot written → {snapshot_path}")
