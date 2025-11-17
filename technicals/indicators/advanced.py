#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/advanced.py — v3.0 (Bible v10.5)
# ------------------------------------------------------------
# Clean advanced indicator layer:
#   • Bollinger Bands
#   • Supertrend
#   • ATR Channels
#   • ATR baseline (from core)
#
#   • Bible v10.5 STATE LAYER INTEGRATION:
#         attach_state_features(df, context, patterns=[...])
#
# ZERO backward-compatibility.
# ZERO legacy params.
# ============================================================

from __future__ import annotations

from typing import Any, Dict

import polars as pl

from queen.helpers.logger import log
from queen.settings.indicator_policy import params_for as _params_for
from queen.settings.timeframes import context_to_token

from .core import atr as _atr
from .state import attach_state_features

__all__ = [
    "bollinger_bands",
    "supertrend",
    "atr_channels",
    "attach_advanced",
    "EXPORTS",
]



# ------------------------------------------------------------
# 1) Bollinger Bands
# ------------------------------------------------------------
def bollinger_bands(
    df: pl.DataFrame,
    period: int = 20,
    stddev: float = 2.0,
    column: str = "close",
):
    if df.is_empty() or column not in df.columns:
        return (
            pl.Series("bb_mid", []),
            pl.Series("bb_upper", []),
            pl.Series("bb_lower", []),
        )

    mid = df[column].rolling_mean(window_size=period).alias("bb_mid")
    std = df[column].rolling_std(window_size=period)
    upper = (mid + stddev * std).alias("bb_upper")
    lower = (mid - stddev * std).alias("bb_lower")
    return mid, upper, lower


# ------------------------------------------------------------
# 2) Supertrend
# ------------------------------------------------------------
def supertrend(
    df: pl.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
):
    if df.is_empty() or not {"high", "low", "close"}.issubset(df.columns):
        return pl.Series("supertrend", [])

    high = df["high"].cast(pl.Float64)
    low = df["low"].cast(pl.Float64)
    close = df["close"].cast(pl.Float64)
    n = df.height

    atr_series = _atr(df, period=period).fill_null(strategy="forward")
    hl2 = ((high + low) / 2.0).cast(pl.Float64)

    upper = (hl2 + multiplier * atr_series).to_numpy()
    lower = (hl2 - multiplier * atr_series).to_numpy()
    close_np = close.to_numpy()

    out_vals = []
    in_up = True

    for i in range(n):
        if i == 0:
            out_vals.append(float(hl2[0]))
            continue

        cu, pu = upper[i], upper[i - 1]
        cl, pl_ = lower[i], lower[i - 1]

        if cu < pu or close_np[i - 1] > pu:
            cu = max(cu, pu)
        if cl > pl_ or close_np[i - 1] < pl_:
            cl = min(cl, pl_)

        if in_up and close_np[i] < cl:
            in_up = False
        elif not in_up and close_np[i] > cu:
            in_up = True

        out_vals.append(cl if in_up else cu)

    return pl.Series("supertrend", out_vals)


# ------------------------------------------------------------
# 3) ATR Channels
# ------------------------------------------------------------
def atr_channels(
    df: pl.DataFrame,
    period: int = 14,
    multiplier: float = 1.5,
):
    if df.is_empty() or "close" not in df.columns:
        return pl.Series("atr_upper", []), pl.Series("atr_lower", [])

    a = _atr(df, period=period)
    upper = (df["close"] + multiplier * a).alias("atr_upper")
    lower = (df["close"] - multiplier * a).alias("atr_lower")
    return upper, lower


# ------------------------------------------------------------
# 4) Settings param resolver
# ------------------------------------------------------------
def _resolve_params(tf: str) -> Dict[str, Any]:
    p_b = _params_for("BOLL", tf) or {}
    p_st = _params_for("SUPER_TREND", tf) or {}
    p_atr = _params_for("ATR", tf) or {}
    p_ac = _params_for("ATR_CHANNELS", tf) or {}

    return {
        "boll_period": int(p_b.get("period", 20)),
        "boll_std": float(p_b.get("stddev", 2.0)),
        "st_period": int(p_st.get("period", 10)),
        "st_mult": float(p_st.get("multiplier", 3.0)),
        "atr_period": int(p_atr.get("period", 14)),
        "atr_ch_mult": float(p_ac.get("multiplier", 1.5)),
    }


# ------------------------------------------------------------
# 5) attach_advanced — FINAL clean version
# ------------------------------------------------------------
def attach_advanced(
    df: pl.DataFrame,
    context: str = "intraday_15m",
) -> pl.DataFrame:
    """Attach:
    • ATR baseline
    • Bollinger Bands
    • Supertrend
    • ATR Channels
    • Bible v10.5 State Features (Volume Delta, RSI Density, LQS)
    • Pattern Credibility (hammer/doji/engulfings/shooting_star)
    """
    if df.is_empty():
        return df

    out = df.clone()
    tf = context_to_token(context)
    p = _resolve_params(tf)

    # ATR
    try:
        out = out.with_columns(_atr(out, period=p["atr_period"]))
    except Exception as e:
        log.warning(f"[ADV] ATR failed: {e}")

    # Bollinger
    try:
        mid, up, lo = bollinger_bands(out, p["boll_period"], p["boll_std"])
        out = out.with_columns([mid, up, lo])
    except Exception as e:
        log.warning(f"[ADV] Bollinger failed: {e}")

    # Supertrend
    try:
        st = supertrend(out, p["st_period"], p["st_mult"])
        out = out.with_columns(st)
    except Exception as e:
        log.warning(f"[ADV] Supertrend failed: {e}")

    # ATR Channels
    try:
        upc, loc = atr_channels(out, p["atr_period"], p["atr_ch_mult"])
        out = out.with_columns([upc, loc])
    except Exception as e:
        log.warning(f"[ADV] ATR channels failed: {e}")

    # Bible v10.5 State Layer + Pattern Credibility
    out = attach_state_features(
        out,
        context=context,
        patterns=[
            "hammer",
            "shooting_star",
            "bullish_engulfing",
            "bearish_engulfing",
            "doji",
        ],
    )

    return out


# Registry export
EXPORTS = {
    "bollinger_bands": bollinger_bands,
    "supertrend": supertrend,
    "atr_channels": atr_channels,
    "attach_advanced": attach_advanced,
}
