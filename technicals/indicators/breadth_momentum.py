# ============================================================
# quant/signals/indicators/breadth_momentum.py
# ------------------------------------------------------------
# ⚙️ Breadth Momentum Engine — Short-term Market Acceleration
# Config-driven, NaN-safe, diagnostic-logged, and headless
# ============================================================

import json

import numpy as np
import polars as pl

from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🧠 Core Breadth Momentum Computation
# ============================================================
# ============================================================
# Tactical Regime Strength (RScore)
# ============================================================
def compute_rscore(df):
    """Derive a Regime Strength score from breadth momentum.
    Returns 0–1 normalized bullish strength measure.
    """
    try:
        if "advancers" in df.columns and "decliners" in df.columns:
            adv = df["advancers"].mean()
            dec = df["decliners"].mean()
            breadth_ratio = adv / (adv + dec + 1e-6)
            return round(float(breadth_ratio), 3)
        if "close" in df.columns:
            # fallback proxy: positive close momentum fraction
            mom = (df["close"].diff() > 0).mean()
            return round(float(mom), 3)
    except Exception:
        pass
    return 0.5


# ============================================================
# 📊 Diagnostic Summary (Headless)
# ============================================================
def summarize_breadth_momentum(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit/fusion layers."""
    if df.is_empty() or "Breadth_Momentum_Bias" not in df.columns:
        return {"status": "empty"}

    last_val = float(df["Breadth_Momentum"][-1])
    bias = str(df["Breadth_Momentum_Bias"][-1])

    state = (
        "Strong Expansion"
        if last_val > 0.4
        else "Mild Expansion"
        if last_val > 0.15
        else "Weak Contraction"
        if last_val < -0.15
        else "Deep Contraction"
        if last_val < -0.4
        else "Stable"
    )

    return {"Breadth_Momentum": round(last_val, 3), "Bias": bias, "State": state}


# ============================================================
# ⚡ Tactical Regime Strength Accessor (RScore)
# ============================================================
def compute_regime_strength(df: pl.DataFrame) -> float:
    """Compute a regime strength score (0–1) for Tactical Fusion Engine.
    Uses breadth expansion (advancers/decliners) or momentum fraction.
    """
    try:
        if df.is_empty():
            return 0.5

        if "advancers" in df.columns and "decliners" in df.columns:
            adv = df["advancers"].mean()
            dec = df["decliners"].mean()
            ratio = adv / (adv + dec + 1e-6)
            return round(float(np.clip(ratio, 0.0, 1.0)), 3)

        if "close" in df.columns:
            mom = (df["close"].diff() > 0).mean()
            return round(float(np.clip(mom, 0.0, 1.0)), 3)

    except Exception:
        pass
    return 0.5


# ============================================================
# 🧪 Standalone Test (Headless, Config-driven Snapshot)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 100
    cmv = np.sin(np.linspace(0, 5, n)) + np.random.normal(0, 0.05, n)
    sps = np.cos(np.linspace(0, 5, n)) + np.random.normal(0, 0.05, n)
    df = pl.DataFrame({"CMV": cmv, "SPS": sps})

    df = compute_breadth_momentum(df, context="intraday_15m")
    summary = summarize_breadth_momentum(df)

    # ✅ Headless diagnostic snapshot via config path
    snapshot_path = get_dev_snapshot_path("breadth_momentum")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Optional console echo in dev mode
    print(f"📊 [Headless] Snapshot written → {snapshot_path}")
