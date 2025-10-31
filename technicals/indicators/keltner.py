# ============================================================
# queen/technicals/indicators/keltner.py
# ------------------------------------------------------------
# ⚙️ Keltner Channel — Volatility Envelope Engine
# Config-driven, NaN-safe, headless for Quant-Core v4.x
# Measures volatility compression & expansion zones
# ============================================================

from __future__ import annotations

import numpy as np
import polars as pl
from queen.helpers.io import write_json_atomic  # used in __main__ snapshot (optional)
from queen.settings.indicator_policy import params_for as _params_for
from queen.settings.settings import dev_snapshot_path


# ============================================================
# 🔧 Helpers: EMA and True Range
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


def true_range(high, low, close_prev):
    """True range computation."""
    return np.maximum.reduce(
        [high - low, np.abs(high - close_prev), np.abs(low - close_prev)]
    )


def compute_atr(high, low, close, period=14):
    """Average True Range with Wilder smoothing."""
    if len(high) == 0:
        return np.array([])
    tr = true_range(high, low, np.roll(close, 1))
    atr = np.zeros_like(tr)
    atr[period - 1] = np.nanmean(tr[:period])
    for i in range(period, len(tr)):
        atr[i] = ((atr[i - 1] * (period - 1)) + tr[i]) / period
    return np.nan_to_num(atr)


# ============================================================
# 🧠 Core Keltner Channel Computation (Config + Diagnostics)
# ============================================================
def compute_keltner(df: pl.DataFrame, timeframe: str = "intraday_15m") -> pl.DataFrame:
    """Compute Keltner Channel and volatility metrics (headless, settings-driven)."""
    p = _params_for("KELTNER", timeframe) or {}
    ema_period = int(p.get("ema_period", 20))
    atr_mult = float(p.get("atr_mult", 2.0))
    atr_period = int(p.get("atr_period", 14))
    squeeze_window = int(p.get("squeeze_window", 10))
    squeeze_thresh = float(p.get("squeeze_threshold", 0.8))
    expansion_thresh = float(p.get("expansion_threshold", 1.2))

    df = df.clone()

    # Validate columns
    for col in ["high", "low", "close"]:
        if col not in df.columns:
            _log_indicator_warning(
                "KELTNER", context, f"Missing '{col}' column — skipping computation."
            )
            return df

    high = df["high"].to_numpy().astype(float)
    low = df["low"].to_numpy().astype(float)
    close = df["close"].to_numpy().astype(float)

    if len(close) < ema_period + 2:
        _log_indicator_warning(
            "KELTNER", context, f"Insufficient data (<{ema_period+2}) for EMA/ATR."
        )
        zeros = np.zeros_like(close)
        return df.with_columns(
            [
                pl.Series("KC_mid", zeros),
                pl.Series("KC_upper", zeros),
                pl.Series("KC_lower", zeros),
                pl.Series("KC_norm", zeros),
                pl.Series("KC_Bias", ["➡️ Stable"] * len(close)),
            ]
        )

    # Core Keltner computations
    mid = ema(close, ema_period)
    atr = compute_atr(high, low, close, atr_period)
    upper = mid + atr_mult * atr
    lower = mid - atr_mult * atr

    # Volatility width metrics
    channel_width = upper - lower
    width_pct = (
        np.divide(channel_width, mid, out=np.zeros_like(channel_width), where=mid != 0)
        * 100
    )
    max_width = (
        np.nanmax(width_pct)
        if np.isfinite(np.nanmax(width_pct)) and np.nanmax(width_pct) > 0
        else 1.0
    )
    width_norm = np.nan_to_num(width_pct / max_width)

    # Squeeze / expansion detection
    roll = np.convolve(
        width_norm, np.ones(squeeze_window) / squeeze_window, mode="same"
    )
    squeeze_flag = width_norm < (roll * squeeze_thresh)
    expansion_flag = width_norm > (roll * expansion_thresh)

    vol_bias = np.full(len(width_norm), "➡️ Stable", dtype=object)
    vol_bias[squeeze_flag] = "🟡 Squeeze"
    vol_bias[expansion_flag] = "🟢 Expansion"

    # Build final frame
    return df.with_columns(
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
    if df.height == 0 or "KC_Bias" not in df.columns:
        return {"status": "empty"}

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
        "KC_width_pct": round(float(last_width), 2),
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
        if df.is_empty():
            return 0.5

        # Ensure KC columns exist — compute them if not
        if "KC_norm" not in df.columns:
            df = compute_keltner(df)

        # Volatility intensity = mean normalized band width
        volx = float(df["KC_norm"].mean())
        return round(max(0.0, min(1.0, volx)), 3)
    except Exception:
        return 0.5


# ============================================================
# 🧪 Local Dev Diagnostic (Headless Snapshot)
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
    write_json_atomic(dev_snapshot_path("keltner"), summary)
    print(
        "📊 [Headless] Keltner snapshot written →queen/data/dev_snapshots/keltner.json"
    )
