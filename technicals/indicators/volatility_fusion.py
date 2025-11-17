#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/volatility_fusion.py — v2.0 (Bible v10.5)
# ------------------------------------------------------------
# Fuses Keltner (+ optional ATR proxy) into a normalized VolX.
#
# Exposes:
#   compute_volatility_fusion(df, context="intraday_15m") -> pl.DataFrame
#   summarize_volatility(df) -> dict
#
# Uses:
#   • indicator_policy["VOL_FUSION"][tf_token]
#   • compute_keltner(...) from keltner.py
#
# No vol_keltner, no snapshot files — pure forward-only.
# ============================================================

from __future__ import annotations

import numpy as np
import polars as pl

from queen.helpers.logger import log
from queen.settings.indicator_policy import params_for as _params_for
from .keltner import compute_keltner
from queen.settings.timeframes import context_to_token

__all__ = ["compute_volatility_fusion", "summarize_volatility"]



def compute_volatility_fusion(
    df: pl.DataFrame,
    context: str = "intraday_15m",
) -> pl.DataFrame:
    """Fuse volatility diagnostics from Keltner (+ATR proxy) into VolX.

    Args:
        df: Polars DataFrame with 'high','low','close'.
        context: settings context key (e.g. 'intraday_15m').

    Returns:
        DataFrame with Keltner columns + volx, volx_norm, volx_bias.
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    need = {"high", "low", "close"}
    missing = need - set(df.columns)
    if missing:
        log.warning(f"[VOL_FUSION] missing columns: {sorted(missing)}")
        return df

    tf_token = context_to_token(context)

    p = _params_for("VOL_FUSION", tf_token) or {}
    normalize_window = int(p.get("normalize_window", 50))  # kept for future use
    weight_keltner = float(p.get("weight_keltner", 0.7))
    weight_atr = float(p.get("weight_atr", 0.3))
    bias_threshold = float(p.get("bias_threshold", 0.6))

    # 1) Keltner base (Bible v10.5 keltner)
    kc = compute_keltner(df, context=context, timeframe=tf_token)
    if "KC_norm" not in kc.columns:
        log.warning("[VOL_FUSION] KC_norm missing from Keltner output")
        return kc

    kc_norm = kc["KC_norm"].to_numpy().astype(float, copy=False)

    # 2) ATR proxy (optional placeholder)
    # If you later add a native ATR-normalizer, plug it here.
    atr_norm = kc_norm * 0.9

    # 3) Weighted VolX
    volx = (weight_keltner * kc_norm) + (weight_atr * atr_norm)

    # 4) Rolling normalization (simple expanding bounds)
    with np.errstate(all="ignore"):
        roll_max = np.maximum.accumulate(volx)
        roll_min = np.minimum.accumulate(volx)

    denom = np.maximum(roll_max - roll_min, 1e-9)
    volx_norm = np.clip((volx - roll_min) / denom, 0.0, 1.0)

    # 5) Bias
    bias = np.full(len(volx_norm), "stable", dtype=object)
    bias[volx_norm > bias_threshold] = "expansion"
    bias[volx_norm < (1.0 - bias_threshold)] = "squeeze"

    return kc.with_columns(
        [
            pl.Series("volx", volx),
            pl.Series("volx_norm", volx_norm),
            pl.Series("volx_bias", bias),
        ]
    )


def summarize_volatility(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit/fusion layers."""
    if not isinstance(df, pl.DataFrame) or df.height == 0:
        return {"status": "empty"}

    if "volx_norm" not in df.columns or "volx_bias" not in df.columns:
        return {"status": "missing", "missing": ["volx_norm", "volx_bias"]}

    last = float(df["volx_norm"][-1])
    bias = str(df["volx_bias"][-1])
    state = (
        "📈 Expansion"
        if bias == "expansion"
        else "⚠️ Squeeze"
        if bias == "squeeze"
        else "➡️ Stable"
    )
    return {"status": "ok", "VolX_norm": round(last, 3), "VolX_bias": bias, "State": state}


# 🧪 Local Dev Diagnostic (headless)
if __name__ == "__main__":
    rng = np.random.default_rng(42)
    n = 250
    base = np.linspace(100, 120, n) + rng.normal(0, 2.0, n)
    high = base + rng.uniform(0.5, 2.0, n)
    low = base - rng.uniform(0.5, 2.0, n)
    close = base + rng.normal(0, 1.0, n)
    df = pl.DataFrame({"high": high, "low": low, "close": close})

    fused = compute_volatility_fusion(df, context="intraday_15m")
    summary = summarize_volatility(fused)

    print("📊 [Headless] Volatility Fusion summary:", summary)
