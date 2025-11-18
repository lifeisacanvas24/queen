#!/usr/bin/env python3
# ============================================================
# queen/services/tactical_pipeline.py — v2.0 (Bible-aligned)
# STRUCTURE + TREND + VOL + REVERSAL → Tactical_Index / Regime
# ============================================================

from __future__ import annotations

from typing import Any, Dict

import polars as pl

from queen.services.bible_engine import (
    compute_structure_block,
    compute_trend_block,
)

# If later you add dedicated reversal / volatility Bible helpers,
# you can import them here. For now we keep them lightweight.


# --------------------------------------------------------------
# 1. Pattern / Structure block (SPS / MCS / CPS / RPS)
# --------------------------------------------------------------
def pattern_block(df: pl.DataFrame, indicators: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Thin wrapper over Bible structure block.

    Expected output keys:
      Structure_Type, Structure_Confidence,
      Swing_Highs, Swing_Lows,
      Micro_Pullback, Is_Retesting
    """
    if df.is_empty():
        return {}
    try:
        return compute_structure_block(df, indicators or {})
    except Exception:
        return {}


# --------------------------------------------------------------
# 2. TREND block (multi-horizon D/W/M)
# --------------------------------------------------------------
def trend_block(df: pl.DataFrame, indicators: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Trend is EMA-based; df is unused for now (kept for future)."""
    try:
        return compute_trend_block(indicators or {})
    except Exception:
        return {}


# --------------------------------------------------------------
# 3. Reversal block (simple RSI/OBV-aware stub for now)
# --------------------------------------------------------------
def reversal_block(df: pl.DataFrame, indicators: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if df.is_empty():
        return {}

    ind = indicators or {}
    rsi = ind.get("RSI")
    obv = (ind.get("OBV") or "").lower()

    tags = []
    score = 0.0
    bias = "None"

    if isinstance(rsi, (int, float)):
        if rsi >= 70:
            bias = "Overbought"
            score += 1.0
            tags.append("RSI≥70")
        elif rsi <= 30:
            bias = "Oversold"
            score += 1.0
            tags.append("RSI≤30")

    if "falling" in obv:
        score += 0.5
        tags.append("OBV↓")
    elif "rising" in obv:
        score += 0.5
        tags.append("OBV↑")

    return {
        "Reversal_Score": round(score, 2),
        "Reversal_Bias": bias,
        "Reversal_Tags": tags,
    }


# --------------------------------------------------------------
# 4. Volatility / Risk block (wrap existing ATR risk fields)
# --------------------------------------------------------------
def volatility_block(df: pl.DataFrame, indicators: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ind = indicators or {}
    return {
        "Daily_ATR": ind.get("Daily_ATR"),
        "Daily_ATR_Pct": ind.get("Daily_ATR_Pct"),
        "Risk_Rating": ind.get("Risk_Rating", "Medium"),
        "SL_Zone": ind.get("SL_Zone", "Normal"),
    }


# --------------------------------------------------------------
# 5. Tactical (Bible brain) block
# --------------------------------------------------------------
def tactical_block(metrics: Dict[str, Any], interval: str = "15m") -> Dict[str, Any]:
    """Fuse STRUCTURE + TREND + VOL + REVERSAL into a tactical view.

    Returns:
      Tactical_Index (0–10)
      regime: {name,label,color}
      RScore_norm (0–1 normalised tactical score)
      plus passthrough of key Bible fields (Trend_Score, Trend_Bias, etc.)

    """
    if not metrics:
        return {}

    # --- unpack safe bits ---
    struct_type = metrics.get("Structure_Type")      # SPS / MCS / CPS / RPS / None
    struct_conf = float(metrics.get("Structure_Confidence") or 0.0)
    micro_pullback = bool(metrics.get("Micro_Pullback"))
    is_retest = bool(metrics.get("Is_Retesting"))

    trend_bias = metrics.get("Trend_Bias", "Range")
    trend_score = float(metrics.get("Trend_Score") or 0.0)

    risk_rating = (metrics.get("Risk_Rating") or "Medium").title()
    reversal_score = float(metrics.get("Reversal_Score") or 0.0)

    ema_bias = (metrics.get("EMA_BIAS") or metrics.get("ema_bias") or "").title()

    # ---------- Tactical_Index construction ----------
    ti = 0.0
    drivers: list[str] = []

    # 1) Structure weight
    if struct_type in {"SPS", "CPS"}:
        base = 3.0 * max(0.3, struct_conf)
        ti += base
        drivers.append(f"{struct_type} x{struct_conf:.2f}")
        if micro_pullback:
            ti += 1.0
            drivers.append("Micro Pullback")
        if is_retest:
            ti += 0.5
            drivers.append("Retest")

    elif struct_type in {"MCS", "RPS"}:
        base = 2.0 * max(0.3, struct_conf)
        ti += base
        drivers.append(f"{struct_type} x{struct_conf:.2f}")

    # 2) Trend weight
    if trend_bias == "Bullish":
        ti += min(3.0, trend_score / 3.0)
        drivers.append(f"Trend {trend_bias} ({trend_score:.1f})")
    elif trend_bias == "Bearish":
        ti -= min(2.0, trend_score / 4.0)
        drivers.append(f"Trend {trend_bias} ({trend_score:.1f})")

    # 3) EMA stack confirmation
    if ema_bias == "Bullish":
        ti += 1.0
        drivers.append("EMA Bullish")
    elif ema_bias == "Bearish":
        ti -= 0.5
        drivers.append("EMA Bearish")

    # 4) Reversal caution / opportunity
    if reversal_score > 0:
        # Treat positive reversal score as "turn possible" → slight caution
        ti -= min(1.0, reversal_score / 2.0)
        drivers.append(f"Reversal stack {reversal_score:.1f}")

    # 5) Risk adjustment (ATR)
    if risk_rating == "Low":
        ti += 0.5
        drivers.append("Risk Low")
    elif risk_rating == "High":
        ti -= 0.5
        drivers.append("Risk High")

    # clamp to 0–10 for the cockpit index
    tactical_index = max(0.0, min(10.0, ti))
    rscore_norm = round(tactical_index / 10.0, 3)

    # ---------- Regime label ----------
    if tactical_index >= 8:
        regime_name = "Strong Bullish"
        regime_color = "#28a745"
    elif tactical_index >= 5:
        regime_name = "Constructive"
        regime_color = "#7acb5a"
    elif tactical_index >= 3:
        regime_name = "Neutral"
        regime_color = "#ffc107"
    elif tactical_index > 0:
        regime_name = "Weak / Cautious"
        regime_color = "#fd7e14"
    else:
        regime_name = "Avoid / Short-only"
        regime_color = "#dc3545"

    regime = {
        "name": regime_name,
        "label": f"{regime_name} ({tactical_index:.1f})",
        "color": regime_color,
    }

    return {
        "Tactical_Index": round(tactical_index, 2),
        "regime": regime,
        "RScore_norm": rscore_norm,

        # Bubble up key Bible metrics so scoring / cockpit_row can attach them
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

        "tactical_drivers": drivers,
    }
