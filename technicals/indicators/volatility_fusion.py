#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/volatility_fusion.py — v1.0
# Fuses Keltner (+ optional ATR proxy) into a normalized VolX
# ============================================================
from __future__ import annotations
import numpy as np
import polars as pl


try:
    # Prefer relative import (works reliably when running tests as modules)
    from .vol_keltner import compute_keltner
except Exception:
    # Fallback absolute import (in case of direct script execution)
    from queen.technicals.indicators.vol_keltner import compute_keltner  # type: ignore

from queen.settings.indicator_policy import params_for as _params_for
from queen.settings import settings as S
from queen.helpers.logger import log


def compute_volatility_fusion(df: pl.DataFrame, timeframe: str = "15m") -> pl.DataFrame:
    """Fuse volatility diagnostics from Keltner (+ATR proxy)."""
    if df.is_empty():
        return df

    need = {"high", "low", "close"}
    missing = need - set(df.columns)
    if missing:
        log.warning(f"[VOL_FUSION] missing columns: {sorted(missing)}")
        return df

    p = _params_for("VOL_FUSION", timeframe) or {}
    normalize_window = int(p.get("normalize_window", 50))
    weight_keltner = float(p.get("weight_keltner", 0.7))
    weight_atr = float(p.get("weight_atr", 0.3))
    bias_threshold = float(p.get("bias_threshold", 0.6))

    # 1) Keltner base
    kc = compute_keltner(df, context=timeframe)
    if "KC_norm" not in kc.columns:
        log.warning("[VOL_FUSION] KC_norm missing from Keltner output")
        return kc
    kc_norm = kc["KC_norm"].to_numpy().astype(float, copy=False)

    # 2) ATR proxy (optional)
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
    bias[volx_norm < (1 - bias_threshold)] = "squeeze"

    return kc.with_columns(
        [
            pl.Series("volx", volx),
            pl.Series("volx_norm", volx_norm),
            pl.Series("volx_bias", bias),
        ]
    )


def summarize_volatility(df: pl.DataFrame) -> dict:
    """Return structured summary for cockpit/fusion layers."""
    if df.is_empty() or "volx_norm" not in df.columns:
        return {"status": "empty"}
    last = float(df["volx_norm"][-1])
    bias = str(df["volx_bias"][-1])
    state = (
        "📈 Expansion"
        if bias == "expansion"
        else "⚠️ Squeeze"
        if bias == "squeeze"
        else "➡️ Stable"
    )
    return {"VolX_norm": round(last, 3), "VolX_bias": bias, "State": state}


# Optional headless diagnostic (respects settings)
if __name__ == "__main__":
    rng = np.random.default_rng(42)
    n = 250
    base = np.linspace(100, 120, n) + rng.normal(0, 2.0, n)
    high = base + rng.uniform(0.5, 2.0, n)
    low = base - rng.uniform(0.5, 2.0, n)
    close = base + rng.normal(0, 1.0, n)
    df = pl.DataFrame({"high": high, "low": low, "close": close})

    fused = compute_volatility_fusion(df, timeframe="intraday_15m")
    summary = summarize_volatility(fused)

    snap = S.dev_snapshot_path("volatility_fusion")
    import json

    with open(snap, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"📊 [Headless] Volatility Fusion snapshot → {snap}")
