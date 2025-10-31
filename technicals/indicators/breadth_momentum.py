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
def compute_breadth_momentum(
    df: pl.DataFrame,
    context: str | None = None,  # kept for API uniformity
    lookback: int = 20,
    **kwargs,
) -> pl.DataFrame:
    if df.is_empty():
        return df

    cols = df.columns
    src = "SPS" if "SPS" in cols else ("CMV" if "CMV" in cols else None)
    if src is None:
        return df

    s = df[src].cast(pl.Float64)
    mom = (s - s.shift(int(lookback))).alias("breadth_momentum")

    # Normalize to [-1, 1] using scalar abs max from the Series
    absmax = float(mom.abs().max() or 0.0)
    denom = absmax if absmax > 1e-9 else 1.0
    mom_norm = (mom / denom).alias("breadth_mom_norm")

    return df.with_columns([mom, mom_norm])


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
