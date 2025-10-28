# ============================================================
# queen/technicals/indicators/breadth_cumulative.py
# ------------------------------------------------------------
# ⚙️ Cumulative Breadth & Persistence Engine (Headless, Polars)
# Settings-driven via indicator_policy.params_for
# ============================================================

from __future__ import annotations

import math

import polars as pl

# Canonical settings owner
from queen.settings.indicator_policy import params_for as _params_for


# ------------------------------------------------------------
# 🧠 Core Breadth Computation
# ------------------------------------------------------------
def compute_breadth(df: pl.DataFrame, timeframe: str = "1d") -> pl.DataFrame:
    """Compute cumulative breadth from CMV/SPS columns:
    - CMV_Breadth (rolling mean)
    - SPS_Breadth (rolling mean)
    - Breadth_Persistence (avg bias strength in [-1,1])
    - Breadth_Bias (🟢/⚪/🔴)

    Params are pulled from settings.indicator_policy via:
      params_for("BREADTH_CUMULATIVE", timeframe)
    with safe defaults if not present.
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("compute_breadth: expected a Polars DataFrame")

    required = {"CMV", "SPS"}
    if not required.issubset(set(df.columns)):
        # Return passthrough DF (no exception) so callers can chain safely
        return df

    # Resolve params from settings (falls back to sane defaults)
    p = _params_for("BREADTH_CUMULATIVE", timeframe) or {}
    window = int(p.get("window", 10))
    thr_bull = float(p.get("threshold_bullish", 0.2))
    thr_bear = float(p.get("threshold_bearish", -0.2))

    # Null-safe rolling means
    out = (
        df.with_columns(
            [
                pl.col("CMV").cast(pl.Float64).fill_null(0).fill_nan(0).alias("CMV"),
                pl.col("SPS").cast(pl.Float64).fill_null(0).fill_nan(0).alias("SPS"),
            ]
        )
        .with_columns(
            [
                pl.col("CMV").rolling_mean(window).alias("CMV_Breadth"),
                pl.col("SPS").rolling_mean(window).alias("SPS_Breadth"),
            ]
        )
        .with_columns(
            ((pl.col("CMV_Breadth") + pl.col("SPS_Breadth")) / 2.0)
            .clip(-1.0, 1.0)
            .alias("Breadth_Persistence")
        )
        .with_columns(
            pl.when(pl.col("Breadth_Persistence") > thr_bull)
            .then(pl.lit("🟢 Bullish"))
            .when(pl.col("Breadth_Persistence") < thr_bear)
            .then(pl.lit("🔴 Bearish"))
            .otherwise(pl.lit("⚪ Neutral"))
            .alias("Breadth_Bias")
        )
    )

    return out


# ------------------------------------------------------------
# 📊 Diagnostic Summary (Headless)
# ------------------------------------------------------------
def summarize_breadth(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit/fusion layers."""
    if not isinstance(df, pl.DataFrame):
        return {"status": "empty"}

    if (
        df.is_empty()
        or "Breadth_Persistence" not in df.columns
        or "Breadth_Bias" not in df.columns
    ):
        return {"status": "empty"}

    last_persist = df["Breadth_Persistence"][-1]
    try:
        val = float(last_persist) if last_persist is not None else float("nan")
    except Exception:
        val = float("nan")

    bias = str(df["Breadth_Bias"][-1]) if "Breadth_Bias" in df.columns else "⚪ Neutral"

    strength = (
        "Strong"
        if (not math.isnan(val)) and abs(val) > 0.6
        else "Moderate"
        if (not math.isnan(val)) and abs(val) > 0.3
        else "Weak"
    )

    return {
        "status": "ok",
        "Breadth_Persistence": round(val, 3) if not math.isnan(val) else 0.0,
        "Bias": bias,
        "Strength": strength,
    }
