# ============================================================
# quant/signals/indicators/momentum_macd.py
# ------------------------------------------------------------
# ⚙️ MACD (Moving Average Convergence Divergence)
# Config-driven, NaN-safe, headless for Quant-Core 4.x
# ============================================================

import json

import numpy as np
import polars as pl

from quant.config import get_indicator_params
from quant.signals.utils_indicator_health import _log_indicator_warning
from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🔧 Exponential Moving Average Helper
# ============================================================
def ema(series: np.ndarray, span: int) -> np.ndarray:
    """Compute Exponential Moving Average (EMA)."""
    if len(series) < span:
        return np.full_like(series, np.nan, dtype=float)
    alpha = 2 / (span + 1)
    ema_vals = np.zeros_like(series, dtype=float)
    ema_vals[0] = series[0]
    for i in range(1, len(series)):
        ema_vals[i] = alpha * series[i] + (1 - alpha) * ema_vals[i - 1]
    return ema_vals


# ============================================================
# 🧠 Core MACD Computation
# ============================================================
def compute_macd(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Compute MACD and normalized momentum metrics."""
    params = get_indicator_params("MACD", context)
    fast_period = params.get("fast_period", 12)
    slow_period = params.get("slow_period", 26)
    signal_period = params.get("signal_period", 9)

    df = df.clone()
    if "close" not in df.columns:
        _log_indicator_warning("MACD", context, "Missing 'close' column — skipping computation.")
        return df

    # --- Safe extraction
    try:
        close = df["close"].to_numpy().astype(float, copy=False)
    except Exception:
        close = np.array(df["close"], dtype=float)

    if len(close) < slow_period:
        _log_indicator_warning("MACD", context, f"Insufficient data (<{slow_period}) for MACD computation.")
        zeros = np.zeros_like(close)
        return df.with_columns([
            pl.Series("MACD_line", zeros),
            pl.Series("MACD_signal", zeros),
            pl.Series("MACD_hist", zeros),
            pl.Series("MACD_norm", zeros),
            pl.Series("MACD_slope", zeros),
            pl.Series("MACD_crossover", np.full(len(close), False)),
        ])

    # --- EMA computation
    macd_fast = ema(close, fast_period)
    macd_slow = ema(close, slow_period)
    macd_line = macd_fast - macd_slow
    signal_line = ema(macd_line, signal_period)
    macd_hist = macd_line - signal_line

    macd_hist = np.nan_to_num(macd_hist, nan=0.0)
    macd_line = np.nan_to_num(macd_line, nan=0.0)
    signal_line = np.nan_to_num(signal_line, nan=0.0)

    # --- Normalization (safe)
    with np.errstate(all="ignore"):
        max_abs = np.nanmax(np.abs(macd_hist))
    if not np.isfinite(max_abs) or max_abs == 0:
        max_abs = 1.0
        _log_indicator_warning("MACD", context, "All-NaN slice encountered — normalization skipped.")
    macd_norm = np.clip(macd_hist / max_abs, -1, 1)

    # --- Slope normalization
    slope = np.gradient(macd_line)
    with np.errstate(all="ignore"):
        slope_max = np.nanmax(np.abs(slope))
    slope_max = slope_max if np.isfinite(slope_max) and slope_max != 0 else 1.0
    slope_norm = np.clip(slope / slope_max, -1, 1)

    # --- Crossovers
    crossover = macd_line > signal_line

    return df.with_columns([
        pl.Series("MACD_line", macd_line),
        pl.Series("MACD_signal", signal_line),
        pl.Series("MACD_hist", macd_hist),
        pl.Series("MACD_norm", macd_norm),
        pl.Series("MACD_slope", slope_norm),
        pl.Series("MACD_crossover", crossover),
    ])


# ============================================================
# 📊 Summary
# ============================================================
def summarize_macd(df: pl.DataFrame) -> dict:
    """Return structured MACD summary for cockpit/fusion layers."""
    if df.height == 0 or "MACD_line" not in df.columns:
        return {"status": "empty"}

    last_val = float(df["MACD_line"][-1])
    last_signal = float(df["MACD_signal"][-1])
    hist = float(df["MACD_hist"][-1])
    bias = "bullish" if last_val > last_signal else "bearish"

    return {
        "MACD_line": round(last_val, 3),
        "MACD_signal": round(last_signal, 3),
        "MACD_hist": round(hist, 3),
        "bias": bias
    }


# ============================================================
# 🧪 Local Dev Diagnostic (Headless Snapshot)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 200
    x = np.linspace(0, 8 * np.pi, n)
    close = 100 + np.sin(x) * 5 + np.random.normal(0, 0.5, n)

    df = pl.DataFrame({"close": close})
    df = compute_macd(df, context="intraday_15m")
    summary = summarize_macd(df)

    # ✅ Write headless diagnostic snapshot via config path
    snapshot_path = get_dev_snapshot_path("macd")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"📊 [Headless] MACD snapshot written → {snapshot_path}")
