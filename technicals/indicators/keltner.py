#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/keltner.py — v3.1 (Bible v10.5)
# ------------------------------------------------------------
# ⚙️ Keltner Channel — Volatility Envelope Engine
# • Config-driven via settings/indicator_policy ("KELTNER")
# • Uses context ("intraday_15m") + timeframe token ("15m")
# • Measures volatility compression & expansion zones
#
# Exposes:
#   compute_keltner(df, context="intraday_15m", timeframe=None) -> pl.DataFrame
#   summarize_keltner(df) -> dict
#   compute_volatility_index(df) -> float (0..1)
#
# No file I/O, no legacy helpers, no vol_keltner.
# ============================================================

from __future__ import annotations

import numpy as np
import polars as pl

from queen.helpers.logger import log
from queen.helpers.ta_math import atr_wilder as _atr_wilder
from queen.helpers.ta_math import ema as _ema_np
from queen.helpers.ta_math import normalize_0_1 as _norm_0_1
from queen.settings.indicator_policy import params_for as _params_for
from queen.settings.timeframes import context_to_token

__all__ = ["compute_keltner", "summarize_keltner", "compute_volatility_index"]


# ============================================================
# 🔧 Helpers
# ============================================================


# ============================================================
# 🧠 Core Keltner Channel Computation (Config + Diagnostics)
# ============================================================
def compute_keltner(
    df: pl.DataFrame,
    *,
    context: str = "intraday_15m",
    timeframe: str | None = None,
) -> pl.DataFrame:
    """Compute Keltner Channel and volatility metrics (headless, settings-driven).

    Args:
        df: Polars DataFrame with 'high','low','close'.
        context: settings context key (e.g. 'intraday_15m').
        timeframe: optional token override (e.g. '15m'); if None, derived from context.

    Returns:
        DataFrame with KC_* columns attached.

    """
    if not isinstance(df, pl.DataFrame) or df.height == 0:
        return df

    tf_token = (timeframe or context_to_token(context)).strip().lower()

    p = _params_for("KELTNER", tf_token) or {}
    ema_period = int(p.get("ema_period", 20))
    atr_mult = float(p.get("atr_mult", 2.0))
    atr_period = int(p.get("atr_period", 14))
    squeeze_window = int(p.get("squeeze_window", 10))
    squeeze_thresh = float(p.get("squeeze_threshold", 0.8))
    expansion_thresh = float(p.get("expansion_threshold", 1.2))

    out = df.clone()

    # Validate columns
    for col in ("high", "low", "close"):
        if col not in out.columns:
            log.warning(
                f"[KELTNER] Missing '{col}' column — skipping computation "
                f"(context={context}, tf={tf_token})."
            )
            return out

    high = out["high"].to_numpy().astype(float, copy=False)
    low = out["low"].to_numpy().astype(float, copy=False)
    close = out["close"].to_numpy().astype(float, copy=False)

    if close.size < ema_period + 2:
        log.warning(
            f"[KELTNER] Insufficient data (<{ema_period + 2}) for EMA/ATR "
            f"(context={context}, tf={tf_token}). Returning flat defaults."
        )
        zeros = np.zeros_like(close, dtype=float)
        return out.with_columns(
            [
                pl.Series("KC_mid", zeros),
                pl.Series("KC_upper", zeros),
                pl.Series("KC_lower", zeros),
                pl.Series("KC_width", zeros),
                pl.Series("KC_width_pct", zeros),
                pl.Series("KC_norm", zeros),
                pl.Series("KC_Bias", ["➡️ Stable"] * close.size),
            ]
        )

    # Core Keltner computations via ta_math
    mid = _ema_np(close, ema_period)
    atr = _atr_wilder(high, low, close, period=atr_period)
    upper = mid + atr_mult * atr
    lower = mid - atr_mult * atr

    # Volatility width metrics
    channel_width = upper - lower
    width_pct = np.divide(
        channel_width,
        mid,
        out=np.zeros_like(channel_width, dtype=float),
        where=mid != 0,
    ) * 100.0

    # Normalized width [0,1] using shared helper
    width_norm = _norm_0_1(width_pct)

    # Squeeze / expansion detection
    squeeze_window = max(int(squeeze_window), 1)
    kernel = np.ones(squeeze_window, dtype=float) / float(squeeze_window)
    roll = np.convolve(width_norm, kernel, mode="same")
    squeeze_flag = width_norm < (roll * squeeze_thresh)
    expansion_flag = width_norm > (roll * expansion_thresh)

    vol_bias = np.full(width_norm.size, "➡️ Stable", dtype=object)
    vol_bias[squeeze_flag] = "🟡 Squeeze"
    vol_bias[expansion_flag] = "🟢 Expansion"

    return out.with_columns(
        [
            pl.Series("KC_mid", mid),
            pl.Series("KC_upper", upper),
            pl.Series("KC_lower", lower),
            pl.Series("KC_width", channel_width),
            pl.Series("KC_width_pct", width_pct),
            pl.Series("KC_norm", width_norm),
            pl.Series("KC_Bias", vol_bias),
        ]
    )


# ============================================================
# 🔍 Summary for Cockpit / Fusion Layers
# ============================================================
def summarize_keltner(df: pl.DataFrame) -> dict:
    """Return structured summary for tactical layer."""
    if not isinstance(df, pl.DataFrame) or df.height == 0:
        return {"status": "empty"}

    if "KC_Bias" not in df.columns:
        return {"status": "missing", "missing": ["KC_Bias"]}

    last_bias = str(df["KC_Bias"][-1])
    last_width = (
        float(df["KC_width_pct"][-1]) if "KC_width_pct" in df.columns else np.nan
    )

    state = (
        "⚠️ Tight Squeeze"
        if "Squeeze" in last_bias
        else "📈 Expanding"
        if "Expansion" in last_bias
        else "➡️ Stable"
    )

    return {
        "status": "ok",
        "KC_width_pct": round(float(last_width), 2) if np.isfinite(last_width) else None,
        "KC_state": state,
        "Bias": last_bias,
    }


# ============================================================
# ⚡ Tactical Volatility Index (VolX)
# ============================================================
def compute_volatility_index(df: pl.DataFrame) -> float:
    """Returns a normalized 0–1 volatility intensity score derived from
    the Keltner Channel width. Used by Tactical Fusion Engine.
    """
    try:
        if not isinstance(df, pl.DataFrame) or df.is_empty():
            return 0.5

        # Ensure KC columns exist — compute them if not
        if "KC_norm" not in df.columns:
            df = compute_keltner(df)

        volx = float(df["KC_norm"].mean())
        if not np.isfinite(volx):
            return 0.5
        return round(max(0.0, min(1.0, volx)), 3)
    except Exception as e:
        log.warning(f"[KELTNER] compute_volatility_index failed → {e}")
        return 0.5


# ============================================================
# 🧪 Local Dev Diagnostic (Headless)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 200
    base = np.linspace(100, 110, n) + np.random.normal(0, 1.5, n)
    high = base + np.random.uniform(0.5, 1.5, n)
    low = base - np.random.uniform(0.5, 1.5, n)
    close = base + np.random.normal(0, 0.8, n)

    df = pl.DataFrame({"high": high, "low": low, "close": close})
    df = compute_keltner(df, context="intraday_15m")
    summary = summarize_keltner(df)
    volx = compute_volatility_index(df)

    print("📊 [Headless] Keltner summary:", summary)
    print("⚡ Volatility index (VolX):", volx)
