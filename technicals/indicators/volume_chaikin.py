# ============================================================
# queen/technicals/indicators/volume_chaikin.py
# ------------------------------------------------------------
# Chaikin Oscillator — Volume Momentum Engine (forward-only)
# Settings-driven, NaN-safe, pure Polars/NumPy.
# Exposes:
#   chaikin(df, timeframe="15m", short_period=None, long_period=None) -> pl.DataFrame
#   summarize_chaikin(df) -> dict
#   attach_chaikin(df, timeframe="15m") -> pl.DataFrame
# Columns returned:
#   ['adl', 'chaikin', 'chaikin_norm', 'chaikin_bias', 'chaikin_flow']
# ============================================================

from __future__ import annotations

import numpy as np
import polars as pl
from queen.helpers.pl_compat import _s2np
from queen.settings.indicator_policy import params_for as _params_for


def _ema_np(series: np.ndarray, span: int) -> np.ndarray:
    if len(series) == 0:
        return np.array([], dtype=float)
    alpha = 2.0 / (span + 1.0)
    out = np.zeros_like(series, dtype=float)
    out[0] = series[0]
    for i in range(1, len(series)):
        out[i] = alpha * series[i] + (1.0 - alpha) * out[i - 1]
    return out


def chaikin(
    df: pl.DataFrame,
    timeframe: str = "15m",
    *,
    short_period: int | None = None,
    long_period: int | None = None,
) -> pl.DataFrame:
    """Compute Chaikin Oscillator & derived volume flow signals.
    Returns a DataFrame with:
      'adl', 'chaikin', 'chaikin_norm', 'chaikin_bias', 'chaikin_flow'
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("chaikin: expected a Polars DataFrame")

    need = {"high", "low", "close", "volume"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"chaikin: missing required columns: {sorted(missing)}")

    # Resolve params from settings (CHAIKIN block), allow overrides
    p = _params_for("CHAIKIN", timeframe) or {}
    sp = int(short_period or p.get("short_period", 3))
    lp = int(long_period or p.get("long_period", 10))

    high = _s2np(df["high"])
    low = _s2np(df["low"])
    close = _s2np(df["close"])
    vol = _s2np(df["volume"])

    denom = high - low
    denom[denom == 0] = 1e-12
    mfm = ((close - low) - (high - close)) / denom
    mfv = mfm * vol

    adl = np.cumsum(mfv)

    adl_ema_s = _ema_np(adl, sp)
    adl_ema_l = _ema_np(adl, lp)
    ch = adl_ema_s - adl_ema_l

    min_v, max_v = float(np.nanmin(ch)), float(np.nanmax(ch))
    if max_v - min_v > 0:
        ch_norm = np.clip((ch - min_v) / (max_v - min_v), 0.0, 1.0)
    else:
        ch_norm = np.zeros_like(ch, dtype=float)

    bias = np.full(len(ch), "neutral", dtype=object)
    bias[ch > 0] = "bullish_flow"
    bias[ch < 0] = "bearish_flow"

    dch = np.diff(ch, prepend=ch[0])
    flow = np.full(len(ch), "stable", dtype=object)
    flow[dch > 0] = "accumulating"
    flow[dch < 0] = "distributing"

    return pl.DataFrame(
        {
            "adl": adl,
            "chaikin": ch,
            "chaikin_norm": ch_norm,
            "chaikin_bias": bias,
            "chaikin_flow": flow,
        }
    )


def summarize_chaikin(df: pl.DataFrame) -> dict:
    """Compact summary for cockpit/fusion layers."""
    if df.is_empty() or "chaikin" not in df.columns:
        return {"status": "empty"}

    last = float(df["chaikin"][-1])
    bias = str(df["chaikin_bias"][-1]) if "chaikin_bias" in df.columns else "neutral"
    flow = str(df["chaikin_flow"][-1]) if "chaikin_flow" in df.columns else "stable"

    state = (
        "🟩 Expanding Volume"
        if "bullish" in bias
        else "🟥 Contracting Volume"
        if "bearish" in bias
        else "⬜ Neutral"
    )
    return {"Chaikin_Osc": round(last, 3), "Bias": bias, "Flow": flow, "State": state}


def attach_chaikin(df: pl.DataFrame, timeframe: str = "15m") -> pl.DataFrame:
    """Attach chaikin outputs to the input DF (by row alignment)."""
    add = chaikin(df, timeframe=timeframe)
    return df.hstack(add)
