#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/adx_dmi.py — v1.1 (Polars + Settings)
# ------------------------------------------------------------
# Pure compute, no I/O. Settings-driven params via indicator_policy.
# Exports:
#   - adx_dmi(df, timeframe="15m", period=None, threshold_trend=None, threshold_consolidation=None)
#   - adx_summary(df_like)
#   - lbx(df_like, timeframe="15m")
# ============================================================

from __future__ import annotations

import numpy as np
import polars as pl
from queen.helpers.pl_compat import _s2np
from queen.settings.indicator_policy import params_for as _params_for


def adx_dmi(
    df: pl.DataFrame,
    timeframe: str = "15m",
    period: int | None = None,
    threshold_trend: int | None = None,
    threshold_consolidation: int | None = None,
) -> pl.DataFrame:
    """Polars/Numpy hybrid — returns a DataFrame with:
      ['adx', 'di_plus', 'di_minus', 'adx_trend']

    Params resolve from settings.indicator_policy (contexts) when timeframe is provided.
    You may override with explicit kwargs.
    """
    if not isinstance(df, pl.DataFrame):
        raise TypeError("adx_dmi: expected a Polars DataFrame")

    need_cols = {"high", "low", "close"}
    if not need_cols.issubset(set(df.columns)):
        missing = sorted(need_cols - set(df.columns))
        raise ValueError(f"adx_dmi: missing required columns: {missing}")

    # Resolve defaults from settings
    if timeframe:
        p = _params_for("ADX_DMI", timeframe) or _params_for("ADX", timeframe) or {}
        period = int(period or p.get("period", 14))
        threshold_trend = int(threshold_trend or p.get("threshold_trend", 25))
        threshold_consolidation = int(
            threshold_consolidation or p.get("threshold_consolidation", 15)
        )
    else:
        period = int(period or 14)
        threshold_trend = int(threshold_trend or 25)
        threshold_consolidation = int(threshold_consolidation or 15)

    # Pull arrays in a forward-safe way
    high = _s2np(df["high"])
    low = _s2np(df["low"])
    close = _s2np(df["close"])

    n = df.height
    if n < period + 2:
        zeros = np.zeros(n, dtype=float)
        return pl.DataFrame(
            {
                "adx": zeros,
                "di_plus": zeros,
                "di_minus": zeros,
                "adx_trend": pl.Series("adx_trend", list(state), dtype=pl.Utf8),
            }
        )

    # Directional movement
    up_move = np.diff(high, prepend=high[0])
    down_move = -np.diff(low, prepend=low[0])
    plus_dm = np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0)

    # True range
    tr = np.maximum.reduce(
        [high - low, np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))]
    )
    tr[0] = max(high[0] - low[0], 1e-12)

    # Wilder smoothing
    def wilder_smooth(values: np.ndarray, p: int) -> np.ndarray:
        sm = np.zeros_like(values, dtype=float)
        sm[p - 1] = np.sum(values[:p])
        for i in range(p, len(values)):
            sm[i] = sm[i - 1] - (sm[i - 1] / p) + values[i]
        return sm

    tr_s = wilder_smooth(tr, period)
    plus_s = wilder_smooth(plus_dm, period)
    minus_s = wilder_smooth(minus_dm, period)

    with np.errstate(all="ignore"):
        di_plus = 100.0 * (plus_s / np.maximum(tr_s, 1e-12))
        di_minus = 100.0 * (minus_s / np.maximum(tr_s, 1e-12))
        dx = 100.0 * np.abs(di_plus - di_minus) / np.maximum(di_plus + di_minus, 1e-12)

    adx = np.zeros_like(dx, dtype=float)
    adx[period - 1] = np.nanmean(dx[:period])
    for i in range(period, len(dx)):
        adx[i] = ((adx[i - 1] * (period - 1)) + dx[i]) / period
    adx = np.nan_to_num(adx)

    # Trend state (plain tokens for rules)
    state = np.full(n, "neutral", dtype=object)
    state[adx >= threshold_trend] = "trending"
    state[adx <= threshold_consolidation] = "consolidating"

    return pl.DataFrame(
        {
            "adx": adx,
            "di_plus": di_plus,
            "di_minus": di_minus,
            "adx_trend": state,
        }
    )


# ------------------------------------------------------------
# Summaries / Helpers
# ------------------------------------------------------------
def adx_summary(df_or_out: pl.DataFrame) -> dict:
    """Accepts either the output of adx_dmi() OR a raw DF (in which case we compute adx_dmi()).
    Returns a compact dict for cockpit/meta layers.
    """
    df = df_or_out
    if not {"adx", "di_plus", "di_minus", "adx_trend"}.issubset(df.columns):
        # Assume raw price DF; compute with default TF
        df = adx_dmi(df_or_out, timeframe="15m")

    last_adx = float(df["adx"][-1])
    last_plus = float(df["di_plus"][-1])
    last_minus = float(df["di_minus"][-1])
    bias = str(df["adx_trend"][-1])

    strength = "strong" if last_adx > 25 else "moderate" if last_adx > 15 else "weak"

    return {
        "adx": round(last_adx, 2),
        "di_plus": round(last_plus, 2),
        "di_minus": round(last_minus, 2),
        "trend_bias": bias,
        "strength": strength,
    }


def lbx(df_or_out: pl.DataFrame, timeframe: str = "15m") -> float:
    """Liquidity Bias (0–1): blend of average ADX and DI alignment.
    Accepts either adx_dmi output or a raw DF.
    """
    if not {"adx", "di_plus", "di_minus"}.issubset(df_or_out.columns):
        out = adx_dmi(df_or_out, timeframe=timeframe)
    else:
        out = df_or_out

    try:
        adx_val = float(np.clip(out["adx"].mean() / 50.0, 0.0, 1.0))
        di_plus = float(np.mean(_s2np(out["di_plus"])))
        di_minus = float(np.mean(_s2np(out["di_minus"])))
        dir_bias = np.tanh((di_plus - di_minus) / 50.0)
        return float(np.clip((adx_val * 0.7) + (dir_bias * 0.3), 0.0, 1.0))
    except Exception:
        return 0.5


# ------------------------------------------------------------
# Registry exports (for autoscan)
# ------------------------------------------------------------
EXPORTS = {
    "adx_dmi": adx_dmi,
    "adx_summary": adx_summary,
    "lbx": lbx,
}
