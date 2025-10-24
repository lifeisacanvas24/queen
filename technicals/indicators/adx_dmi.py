# ============================================================
# quant/signals/indicators/trend_adx_dmi.py
# ------------------------------------------------------------
# ⚙️ ADX + DMI (Average Directional Movement Index)
# Config-driven, NaN-safe, headless for Quant-Core 4.x
# ============================================================

import json

import numpy as np
import polars as pl

from quant.config import get_indicator_params
from quant.signals.utils_indicator_health import _log_indicator_warning
from quant.utils.path_manager import get_dev_snapshot_path


# ============================================================
# 🧠 Core ADX / DMI Computation
# ============================================================
def compute_adx(df: pl.DataFrame, context: str = "default") -> pl.DataFrame:
    """Compute ADX/DMI with config parameters and diagnostic logging."""
    params = get_indicator_params("ADX", context)
    period = params.get("period", 14)
    thr_trend = params.get("threshold_trend", 25)
    thr_consol = params.get("threshold_consolidation", 15)

    df = df.clone()
    for col in ["high", "low", "close"]:
        if col not in df.columns:
            _log_indicator_warning(
                "ADX", context, f"Missing '{col}' column — skipping."
            )
            return df

    high = df["high"].to_numpy().astype(float)
    low = df["low"].to_numpy().astype(float)
    close = df["close"].to_numpy().astype(float)

    if len(high) < period + 2:
        _log_indicator_warning(
            "ADX", context, f"Insufficient data (<{period+2}) for ADX."
        )
        zeros = np.zeros_like(high)
        return df.with_columns(
            [
                pl.Series("ADX", zeros),
                pl.Series("DI_plus", zeros),
                pl.Series("DI_minus", zeros),
                pl.Series("ADX_trend", ["⚪ Neutral"] * len(high)),
            ]
        )

    # --- Directional movements
    up_move = np.diff(high, prepend=high[0])
    down_move = np.diff(low, prepend=low[0]) * -1
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    # --- True range
    tr = np.maximum.reduce(
        [
            high - low,
            np.abs(high - np.roll(close, 1)),
            np.abs(low - np.roll(close, 1)),
        ]
    )
    tr[0] = high[0] - low[0]

    # --- Wilder smoothing
    def wilder_smooth(values, p):
        smoothed = np.zeros_like(values)
        smoothed[p - 1] = np.sum(values[:p])
        for i in range(p, len(values)):
            smoothed[i] = smoothed[i - 1] - (smoothed[i - 1] / p) + values[i]
        return smoothed

    tr_s = wilder_smooth(tr, period)
    plus_s = wilder_smooth(plus_dm, period)
    minus_s = wilder_smooth(minus_dm, period)

    with np.errstate(all="ignore"):
        di_plus = 100 * (plus_s / tr_s)
        di_minus = 100 * (minus_s / tr_s)
        dx = 100 * np.abs(di_plus - di_minus) / np.maximum(di_plus + di_minus, 1e-9)

    adx = np.zeros_like(dx)
    adx[period - 1] = np.nanmean(dx[:period])
    for i in range(period, len(dx)):
        adx[i] = ((adx[i - 1] * (period - 1)) + dx[i]) / period
    adx = np.nan_to_num(adx)

    # --- Trend classification
    trend_state = np.full(len(adx), "⚪ Neutral", dtype=object)
    trend_state[adx >= thr_trend] = "🟢 Trending"
    trend_state[adx <= thr_consol] = "🟡 Consolidating"

    return df.with_columns(
        [
            pl.Series("ADX", adx),
            pl.Series("DI_plus", di_plus),
            pl.Series("DI_minus", di_minus),
            pl.Series("ADX_trend", trend_state),
        ]
    )


# ============================================================
# 📊 Diagnostic Summary (Headless)
# ============================================================
def summarize_adx(df: pl.DataFrame) -> dict:
    """Return structured ADX summary for cockpit/fusion layers."""
    if df.height == 0 or "ADX" not in df.columns:
        return {"status": "empty"}

    last_adx = float(df["ADX"][-1])
    last_plus = float(df["DI_plus"][-1])
    last_minus = float(df["DI_minus"][-1])
    bias = str(df["ADX_trend"][-1])

    strength = (
        "🟩 Strong" if last_adx > 25 else "🟨 Moderate" if last_adx > 15 else "⬜ Weak"
    )

    return {
        "ADX": round(last_adx, 2),
        "DI_plus": round(last_plus, 2),
        "DI_minus": round(last_minus, 2),
        "Strength": strength,
        "Trend_Bias": bias,
    }


# ============================================================
# ⚡ Tactical Liquidity Bias Accessor (LBX)
# ============================================================
def compute_lbx(df: pl.DataFrame) -> float:
    """Compute a 0–1 normalized trend bias score for Tactical Fusion Engine.
    Derived from ADX average strength and directional alignment.
    """
    try:
        if df.is_empty():
            return 0.5

        # ensure ADX columns exist — compute if missing
        if "ADX" not in df.columns:
            df = compute_adx(df)

        adx_val = float(np.clip(df["ADX"].mean() / 50.0, 0.0, 1.0))
        di_plus = float(df["DI_plus"].mean()) if "DI_plus" in df.columns else 0.0
        di_minus = float(df["DI_minus"].mean()) if "DI_minus" in df.columns else 0.0

        # directional strength bias
        dir_bias = np.tanh((di_plus - di_minus) / 50.0)
        lbx = np.clip((adx_val * 0.7) + (dir_bias * 0.3), 0.0, 1.0)

        return round(float(lbx), 3)
    except Exception:
        return 0.5


# ============================================================
# 🧪 Local Dev Diagnostic (Headless Snapshot)
# ============================================================
if __name__ == "__main__":
    np.random.seed(42)
    n = 200
    base = np.linspace(100, 110, n) + np.random.normal(0, 1.5, n)
    high = base + np.random.uniform(0.5, 2.0, n)
    low = base - np.random.uniform(0.5, 2.0, n)
    close = base + np.random.normal(0, 0.5, n)
    df = pl.DataFrame({"high": high, "low": low, "close": close})

    df = compute_adx(df, context="intraday_15m")
    summary = summarize_adx(df)

    # ✅ Headless diagnostic snapshot
    snapshot_path = get_dev_snapshot_path("adx")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Optional echo for dev
    print(f"📊 [Headless] ADX snapshot written → {snapshot_path}")
