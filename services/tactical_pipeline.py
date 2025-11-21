#!/usr/bin/env python3
# ============================================================
# queen/services/tactical_pipeline.py — v2.3 (Bible-aligned)
# STRUCTURE + TREND + ALIGN + VOL + REVERSAL → Tactical_Index / Regime
# ============================================================

from __future__ import annotations

from typing import Any, Dict

import polars as pl

# Pure, circular-free Bible blocks:
from queen.services.bible_engine import (
    compute_structure_block,
    compute_trend_block,
    compute_alignment_block,
    compute_vol_block,
    compute_risk_block,
)

# ============================================================
# 1) STRUCTURE (SPS / CPS / MCS / RPS)
# ============================================================
def pattern_block(
    df: pl.DataFrame,
    indicators: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    if df.is_empty():
        return {}
    try:
        return compute_structure_block(df, indicators or {})
    except Exception:
        return {}

# ============================================================
# 2) TREND (D / W / M trend bias + score)
# ============================================================
def trend_block(
    df: pl.DataFrame,
    indicators: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    try:
        return compute_trend_block(indicators or {})
    except Exception:
        return {}

# ============================================================
# 3) ALIGNMENT (EMA stack + VWAP + CPR)
# ============================================================
def alignment_block(
    df: pl.DataFrame,
    indicators: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Indicator-only alignment block (df reserved for future)."""
    try:
        return compute_alignment_block(indicators or {})
    except Exception:
        return {}

# ============================================================
# 4) REVERSAL (simple RSI/OBV stub)
# ============================================================
def reversal_block(
    df: pl.DataFrame,
    indicators: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    if df.is_empty():
        return {}

    ind = indicators or {}
    rsi = ind.get("RSI") or ind.get("rsi")
    obv = (ind.get("OBV") or ind.get("obv") or "").lower()

    tags, score = [], 0.0
    bias = "None"

    if isinstance(rsi, (int, float)):
        if rsi >= 70:
            bias = "Overbought"; score += 1.0; tags.append("RSI≥70")
        elif rsi <= 30:
            bias = "Oversold"; score += 1.0; tags.append("RSI≤30")

    if "falling" in obv:
        score += 0.5; tags.append("OBV↓")
    elif "rising" in obv:
        score += 0.5; tags.append("OBV↑")

    return {
        "Reversal_Score": round(score, 2),
        "Reversal_Bias": bias,
        "Reversal_Tags": tags,
    }

# ============================================================
# 5) VOLATILITY (ATR regime)
# ============================================================
def volatility_block(
    df: pl.DataFrame,
    indicators: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    ind = indicators or {}
    try:
        return compute_vol_block(df, ind)
    except Exception:
        return {
            "Daily_ATR": ind.get("Daily_ATR"),
            "Daily_ATR_Pct": ind.get("Daily_ATR_Pct"),
            "Risk_Rating": ind.get("Risk_Rating", "Medium"),
            "SL_Zone": ind.get("SL_Zone", "Normal"),
        }

# ============================================================
# 6) RISK (Structure + Trend + Vol)
# ============================================================
def risk_block(
    df: pl.DataFrame,
    indicators: Dict[str, Any] | None,
    structure: Dict[str, Any] | None,
    trend: Dict[str, Any] | None,
    vol: Dict[str, Any] | None,
    pos: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    try:
        return compute_risk_block(
            structure or {},
            trend or {},
            vol or {},
            indicators=indicators or {},
            pos=pos,
        )
    except Exception:
        return {}

# ============================================================
# 7) TACTICAL BRAIN (Bible fusion → Tactical_Index)
# ============================================================
def tactical_block(metrics: Dict[str, Any], interval: str = "15m") -> Dict[str, Any]:
    if not metrics:
        return {}

    struct_type  = metrics.get("Structure_Type")
    struct_conf  = float(metrics.get("Structure_Confidence") or 0.0)
    micro_pullback = bool(metrics.get("Micro_Pullback"))
    is_retest    = bool(metrics.get("Is_Retesting") or metrics.get("Is_Retesting_Level"))

    trend_bias   = metrics.get("Trend_Bias", "Range")
    trend_score  = float(metrics.get("Trend_Score") or 0.0)

    risk_rating  = (metrics.get("Risk_Rating") or "Medium").title()
    reversal_score = float(metrics.get("Reversal_Score") or 0.0)

    ema_bias = (metrics.get("EMA_BIAS") or metrics.get("ema_bias") or "").title()

    ti = 0.0
    drivers: list[str] = []

    # STRUCTURE
    if struct_type in {"SPS", "CPS"}:
        base = 3.0 * max(0.3, struct_conf)
        ti += base; drivers.append(f"{struct_type} x{struct_conf:.2f}")
        if micro_pullback:
            ti += 1.0; drivers.append("Micro Pullback")
        if is_retest:
            ti += 0.5; drivers.append("Retest")
    elif struct_type in {"MCS", "RPS"}:
        base = 2.0 * max(0.3, struct_conf)
        ti += base; drivers.append(f"{struct_type} x{struct_conf:.2f}")

    # TREND
    if trend_bias == "Bullish":
        ti += min(3.0, trend_score / 3.0)
        drivers.append(f"Trend {trend_bias} ({trend_score:.1f})")
    elif trend_bias == "Bearish":
        ti -= min(2.0, trend_score / 4.0)
        drivers.append(f"Trend {trend_bias} ({trend_score:.1f})")

    # EMA confirmation
    if ema_bias == "Bullish":
        ti += 1.0; drivers.append("EMA Bullish")
    elif ema_bias == "Bearish":
        ti -= 0.5; drivers.append("EMA Bearish")

    # REVERSAL caution
    if reversal_score > 0:
        ti -= min(1.0, reversal_score / 2.0)
        drivers.append(f"Reversal {reversal_score:.1f}")

    # RISK (ATR)
    if risk_rating == "Low":
        ti += 0.5; drivers.append("Risk Low")
    elif risk_rating == "High":
        ti -= 0.5; drivers.append("Risk High")

    # Bound 0–10
    tactical_index = max(0.0, min(10.0, ti))
    rscore_norm = round(tactical_index / 10.0, 3)

    # REGIME
    if tactical_index >= 8:
        regime = ("Strong Bullish", "#28a745")
    elif tactical_index >= 5:
        regime = ("Constructive", "#7acb5a")
    elif tactical_index >= 3:
        regime = ("Neutral", "#ffc107")
    elif tactical_index > 0:
        regime = ("Weak / Cautious", "#fd7e14")
    else:
        regime = ("Avoid / Short-only", "#dc3545")

    regime_name, regime_color = regime

    return {
        "Tactical_Index": round(tactical_index, 2),
        "regime": {
            "name": regime_name,
            "label": f"{regime_name} ({tactical_index:.1f})",
            "color": regime_color,
        },
        "RScore_norm": rscore_norm,
        "tactical_drivers": drivers,

        # Bubble up important Bible fields
        "Trend_Bias": trend_bias,
        "Trend_Score": round(trend_score, 2),
        "Trend_Label": metrics.get("Trend_Label"),
        "Trend_Bias_D": metrics.get("Trend_Bias_D"),
        "Trend_Bias_W": metrics.get("Trend_Bias_W"),
        "Trend_Bias_M": metrics.get("Trend_Bias_M"),

        "Structure_Type": struct_type,
        "Structure_Confidence": struct_conf,
        "Micro_Pullback": micro_pullback,
        "Is_Retesting": is_retest,

        "Risk_Rating": risk_rating,
        "Reversal_Score": round(reversal_score, 2),
    }

# ============================================================
# 8) Unified Bible Blocks for cockpit/monitor
# ============================================================
def compute_bible_blocks(
    df: pl.DataFrame,
    indicators: Dict[str, Any],
    interval: str = "15m",
) -> Dict[str, Any]:
    if df.is_empty():
        return {}

    base = indicators or {}

    pt  = pattern_block(df, base)
    rv  = reversal_block(df, base)
    vol = volatility_block(df, base)
    tr  = trend_block(df, base)
    aln = alignment_block(df, base)

    tac_input = {**base, **pt, **rv, **vol, **tr, **aln}
    tc = tactical_block(tac_input, interval=interval)

    merged: Dict[str, Any] = {}
    for blk in (pt, rv, vol, tr, aln, tc):
        if blk:
            merged.update(blk)

    return merged
