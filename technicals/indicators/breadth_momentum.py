# ============================================================
# queen/technicals/indicators/breadth_momentum.py
# ------------------------------------------------------------
# ⚙️ Breadth Momentum — short-term market acceleration
# Settings-driven, NaN-safe, Polars-only, headless-friendly
# ============================================================

from __future__ import annotations

import math

import numpy as np
import polars as pl
from queen.settings.indicator_policy import params_for as _params_for


# ------------------------------------------------------------
# 🧠 Core computation
# ------------------------------------------------------------
def compute_breadth_momentum(df: pl.DataFrame, timeframe: str = "1d") -> pl.DataFrame:
    """Compute breadth momentum & bias.

    Preferred inputs:
      • CMV, SPS  (continuous breadth drivers)
    Optional fallback:
      • advancers, decliners

    Outputs:
      • Breadth_Momentum       ∈ [-1, 1] (float)
      • Breadth_Momentum_Bias  one of {🟢 Bullish, ⚪ Neutral, 🔴 Bearish}
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    # Params from settings (indicator_policy INDICATORS / contexts)
    p = _params_for("BREADTH_MOMENTUM", timeframe) or {}
    fast = int(p.get("fast_window", 5))
    slow = int(p.get("slow_window", 20))
    thr_expand = float(p.get("threshold_expand", 0.15))
    thr_contract = float(p.get("threshold_contract", -0.15))
    clip_abs = float(p.get("clip_abs", 1.0))

    out = df.clone()
    cols = set(out.columns)
    has_cmv_sps = {"CMV", "SPS"}.issubset(cols)
    has_adv_dec = {"advancers", "decliners"}.issubset(cols)

    if has_cmv_sps:
        out = out.with_columns(
            [
                pl.col("CMV").cast(pl.Float64).fill_null(0).fill_nan(0).alias("CMV"),
                pl.col("SPS").cast(pl.Float64).fill_null(0).fill_nan(0).alias("SPS"),
            ]
        )
        out = out.with_columns(
            [
                (
                    (pl.col("CMV") - pl.col("CMV").rolling_mean(slow))
                    / (pl.col("CMV").rolling_std(slow).fill_null(1e-9))
                ).alias("_cmv_z"),
                (
                    (pl.col("SPS") - pl.col("SPS").rolling_mean(slow))
                    / (pl.col("SPS").rolling_std(slow).fill_null(1e-9))
                ).alias("_sps_z"),
            ]
        )
        out = out.with_columns(
            ((pl.col("_cmv_z") + pl.col("_sps_z")) / 2.0)
            .rolling_mean(fast)
            .clip(-clip_abs, clip_abs)
            .alias("Breadth_Momentum")
        ).drop(["_cmv_z", "_sps_z"])

    elif has_adv_dec:
        out = out.with_columns(
            [
                pl.col("advancers").cast(pl.Float64).fill_null(0).fill_nan(0),
                pl.col("decliners").cast(pl.Float64).fill_null(0).fill_nan(0),
            ]
        )
        out = out.with_columns(
            (pl.col("advancers") / (pl.col("advancers") + pl.col("decliners") + 1e-9))
            .clip(0.0, 1.0)
            .alias("_ratio")
        )
        out = out.with_columns(
            ((pl.col("_ratio") * 2.0) - 1.0)
            .rolling_mean(fast)
            .clip(-1.0, 1.0)
            .alias("Breadth_Momentum")
        ).drop(["_ratio"])

    else:
        # Nothing to compute
        return out

    # Bias buckets
    out = out.with_columns(
        pl.when(pl.col("Breadth_Momentum") > thr_expand)
        .then(pl.lit("🟢 Bullish"))
        .when(pl.col("Breadth_Momentum") < thr_contract)
        .then(pl.lit("🔴 Bearish"))
        .otherwise(pl.lit("⚪ Neutral"))
        .alias("Breadth_Momentum_Bias")
    )
    return out


# ------------------------------------------------------------
# 📊 Summary helper (cockpit/fusion)
# ------------------------------------------------------------
def summarize_breadth_momentum(df: pl.DataFrame) -> dict:
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return {"status": "empty"}
    if (
        "Breadth_Momentum" not in df.columns
        or "Breadth_Momentum_Bias" not in df.columns
    ):
        return {"status": "empty"}

    try:
        last_val = float(df["Breadth_Momentum"][-1])
    except Exception:
        last_val = float("nan")
    bias = str(df["Breadth_Momentum_Bias"][-1])

    state = (
        "Strong Expansion"
        if (not math.isnan(last_val) and last_val > 0.4)
        else "Mild Expansion"
        if (not math.isnan(last_val) and last_val > 0.15)
        else "Weak Contraction"
        if (not math.isnan(last_val) and last_val < -0.15)
        else "Deep Contraction"
        if (not math.isnan(last_val) and last_val < -0.4)
        else "Stable"
    )

    return {
        "status": "ok",
        "Breadth_Momentum": round(last_val, 3) if not math.isnan(last_val) else 0.0,
        "Bias": bias,
        "State": state,
    }


# ------------------------------------------------------------
# ⚡ Regime strength (0–1) accessor
# ------------------------------------------------------------
def compute_regime_strength(df: pl.DataFrame) -> float:
    try:
        if not isinstance(df, pl.DataFrame) or df.is_empty():
            return 0.5

        if {"advancers", "decliners"}.issubset(set(df.columns)):
            adv = float(pl.mean(df["advancers"])) if df["advancers"].len() else 0.0
            dec = float(pl.mean(df["decliners"])) if df["decliners"].len() else 0.0
            ratio = adv / (adv + dec + 1e-9)
            return float(np.clip(ratio, 0.0, 1.0))

        if "Breadth_Momentum" in df.columns and df["Breadth_Momentum"].len():
            v = float(df["Breadth_Momentum"][-1])
            return float(np.clip((v + 1.0) / 2.0, 0.0, 1.0))
    except Exception:
        pass
    return 0.5


# ------------------------------------------------------------
# 🧪 Local sanity (no I/O)
# ------------------------------------------------------------
if __name__ == "__main__":
    n = 120
    x = np.linspace(0, 6, n)
    cmv = np.sin(x) + np.random.normal(0, 0.1, n)
    sps = np.cos(x) + np.random.normal(0, 0.1, n)
    demo = pl.DataFrame({"CMV": cmv, "SPS": sps})
    out = compute_breadth_momentum(demo, timeframe="intraday_15m")
    print(out.select(["Breadth_Momentum", "Breadth_Momentum_Bias"]).tail(5))
    print(summarize_breadth_momentum(out))
    print("Regime strength:", compute_regime_strength(out))
