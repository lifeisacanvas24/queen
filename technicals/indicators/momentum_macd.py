#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/momentum_macd.py — v3.1 (Bible v10.5)
# ------------------------------------------------------------
# • Config-driven MACD (reads settings/indicator_policy)
# • Uses timeframe tokens ('5m', '15m', '1h', '1d', ...)
# • Outputs:
#     MACD_line, MACD_signal, MACD_hist,
#     MACD_norm, MACD_slope, MACD_crossover
# • Includes:
#     - macd_config()     → active params (for introspection)
#     - summarize_macd()  → cockpit / fusion snapshot
#
# No file I/O, no legacy helpers — pure forward-only.
# ============================================================

from __future__ import annotations

import numpy as np
import polars as pl

from queen.helpers.logger import log
from queen.helpers.pl_compat import ensure_float_series
from queen.helpers.ta_math import (
    ema as _ema_np,
)
from queen.helpers.ta_math import (
    gradient_norm as _grad_norm,
)
from queen.helpers.ta_math import (
    normalize_symmetric as _norm_sym,
)
from queen.settings.indicator_policy import params_for as _params_for

__all__ = ["compute_macd", "summarize_macd", "macd_config"]


# ------------------------------------------------------------
# ⚙️ Config helper
# ------------------------------------------------------------
def macd_config(timeframe: str = "15m") -> dict:
    """Return the MACD configuration resolved from settings for a timeframe token."""
    p = _params_for("MACD", timeframe) or {}
    fast_period = int(p.get("fast_period", 12))
    slow_period = int(p.get("slow_period", 26))
    signal_period = int(p.get("signal_period", 9))
    return {
        "timeframe": timeframe,
        "fast_period": fast_period,
        "slow_period": slow_period,
        "signal_period": signal_period,
    }


# ------------------------------------------------------------
# 🧠 Core MACD Computation
# ------------------------------------------------------------
def compute_macd(df: pl.DataFrame, timeframe: str = "15m") -> pl.DataFrame:
    """Compute MACD and derived fields, driven by settings/indicator_policy.

    Args:
        df: Polars DataFrame with at least 'close' column.
        timeframe: Short token like '5m', '15m', '1h', '1d', ...

    Returns:
        DataFrame with MACD_* columns appended.

    """
    if not isinstance(df, pl.DataFrame) or df.height == 0:
        return df

    if "close" not in df.columns:
        log.warning("[MACD] Missing 'close' column — skipping computation.")
        return df

    cfg = macd_config(timeframe)
    fast_period = cfg["fast_period"]
    slow_period = cfg["slow_period"]
    signal_period = cfg["signal_period"]

    out = df.clone()

    # Safe extraction via pl_compat (float, null-safe)
    close_series = ensure_float_series(out["close"])
    close = close_series.to_numpy()

    n = close.size
    if n < slow_period:
        log.warning(
            f"[MACD] Insufficient data (<{slow_period}) for MACD (tf={timeframe}); "
            "filling zeros."
        )
        zeros = np.zeros_like(close, dtype=float)
        return out.with_columns(
            [
                pl.Series("MACD_line", zeros),
                pl.Series("MACD_signal", zeros),
                pl.Series("MACD_hist", zeros),
                pl.Series("MACD_norm", zeros),
                pl.Series("MACD_slope", zeros),
                pl.Series("MACD_crossover", np.full(n, False)),
            ]
        )

    # EMA-based MACD via shared ta_math EMA
    macd_fast = _ema_np(close, fast_period)
    macd_slow = _ema_np(close, slow_period)
    macd_line = macd_fast - macd_slow
    signal_line = _ema_np(macd_line, signal_period)
    macd_hist = macd_line - signal_line

    macd_line = np.nan_to_num(macd_line, nan=0.0)
    signal_line = np.nan_to_num(signal_line, nan=0.0)
    macd_hist = np.nan_to_num(macd_hist, nan=0.0)

    # Histogram normalization ([-1, 1]) via ta_math
    macd_norm = _norm_sym(macd_hist)

    # Slope normalization (gradient of MACD_line) via ta_math
    slope_norm = _grad_norm(macd_line)

    # Crossovers (boolean)
    crossover = macd_line > signal_line

    return out.with_columns(
        [
            pl.Series("MACD_line", macd_line),
            pl.Series("MACD_signal", signal_line),
            pl.Series("MACD_hist", macd_hist),
            pl.Series("MACD_norm", macd_norm),
            pl.Series("MACD_slope", slope_norm),
            pl.Series("MACD_crossover", crossover),
        ]
    )


# ------------------------------------------------------------
# 📊 Summary (for cockpit/fusion)
# ------------------------------------------------------------
def summarize_macd(df: pl.DataFrame) -> dict:
    """Return structured MACD summary for cockpit/fusion layers."""
    if not isinstance(df, pl.DataFrame) or df.height == 0:
        return {"status": "empty"}

    required = {"MACD_line", "MACD_signal", "MACD_hist"}
    if not required.issubset(set(df.columns)):
        return {"status": "missing", "missing": sorted(required - set(df.columns))}

    last_val = float(df["MACD_line"][-1])
    last_signal = float(df["MACD_signal"][-1])
    hist = float(df["MACD_hist"][-1])
    bias = "bullish" if last_val > last_signal else "bearish"

    return {
        "status": "ok",
        "MACD_line": round(last_val, 3),
        "MACD_signal": round(last_signal, 3),
        "MACD_hist": round(hist, 3),
        "bias": bias,
    }


# ------------------------------------------------------------
# 🧪 Local Dev Diagnostic (Headless, no filesystem)
# ------------------------------------------------------------
if __name__ == "__main__":
    # Simple synthetic sine-wave test
    np.random.seed(42)
    n = 200
    x = np.linspace(0, 8 * np.pi, n)
    close = 100 + np.sin(x) * 5 + np.random.normal(0, 0.5, n)

    df = pl.DataFrame({"close": close})
    df_macd = compute_macd(df, timeframe="15m")
    snap = summarize_macd(df_macd)

    print("📊 [Headless] MACD snapshot:", snap)
    print("Config:", macd_config("15m"))
