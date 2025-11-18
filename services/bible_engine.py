#!/usr/bin/env python3
# ============================================================
# queen/services/bible_engine.py — v1.0
# Bible SUPREME Blocks (Phase 2)
#
# This module will gradually host:
#   • compute_structure_block  (SPS / MCS / CPS / RPS)
#   • compute_trend_block      (multi-TF trend bias + strength)
#   • compute_alignment_block  (EMA stack, VWAP, CPR alignment)
#   • compute_reversal_block   (divergences, traps, VDU)
#   • compute_vol_block        (ATR regime, expansion/contraction)
#   • compute_risk_block       (targets + structure + volatility)
#
# For now we implement:
#   ✅ compute_structure_block()
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from queen.helpers.candles import ensure_sorted

__all__ = [
    "compute_structure_block",
]


# ============================================================
# 🔹 Small swing helpers
# ============================================================

@dataclass
class SwingPoints:
    highs: List[float]
    lows: List[float]


def _swing_points(df: pl.DataFrame, window: int = 3, max_points: int = 5) -> SwingPoints:
    """Detect local swing highs/lows using a small neighbourhood window.

    For now we use a simple 3-bar pattern:
      swing_high: high > prev_high & high > next_high
      swing_low : low  < prev_low  & low  < next_low
    """
    if df.is_empty() or df.height < window + 2:
        return SwingPoints([], [])

    base = (
        df.with_columns(
            h_prev=pl.col("high").shift(1),
            h_next=pl.col("high").shift(-1),
            l_prev=pl.col("low").shift(1),
            l_next=pl.col("low").shift(-1),
        )
        .with_columns(
            swing_high=(pl.col("high") > pl.col("h_prev"))
            & (pl.col("high") > pl.col("h_next")),
            swing_low=(pl.col("low") < pl.col("l_prev"))
            & (pl.col("low") < pl.col("l_next")),
        )
    )

    highs = (
        base.filter(pl.col("swing_high"))
        .select("high")
        .to_series()
        .to_list()
    )
    lows = (
        base.filter(pl.col("swing_low"))
        .select("low")
        .to_series()
        .to_list()
    )

    # keep most recent points (max_points each) for classification
    return SwingPoints(highs=highs[-max_points:], lows=lows[-max_points:])


def _slope_sign(values: List[float]) -> float:
    """Return +1 for rising, -1 for falling, 0 for flat/insufficient."""
    if len(values) < 2:
        return 0.0
    first, last = float(values[0]), float(values[-1])
    if last > first * 1.003:   # +0.3% threshold
        return 1.0
    if last < first * 0.997:   # -0.3% threshold
        return -1.0
    return 0.0


def _classify_structure(
    swings: SwingPoints,
    close: float,
    cpr: Optional[float],
    vwap: Optional[float],
) -> Tuple[str, float, bool, bool]:
    """Map swings + context into (structure_type, confidence, micro_pullback, is_retesting).

    SPS  → higher highs + higher lows (trend up)
    RPS  → lower highs + lower lows (trend down)
    CPS  → lows rising but highs not breaking aggressively (bullish correction)
    MCS  → mixed/flat = consolidation / range
    """
    highs, lows = swings.highs, swings.lows
    if len(highs) + len(lows) < 3:
        return "MCS", 0.3, False, False  # not enough structure yet

    hi_slope = _slope_sign(highs)
    lo_slope = _slope_sign(lows)

    structure = "MCS"
    conf = 0.5

    if hi_slope > 0 and lo_slope > 0:
        structure = "SPS"
        conf = 0.8
    elif hi_slope < 0 and lo_slope < 0:
        structure = "RPS"
        conf = 0.8
    elif lo_slope > 0 and hi_slope <= 0:
        structure = "CPS"  # bullish correction / higher lows, capped highs
        conf = 0.7
    elif hi_slope < 0 and lo_slope >= 0:
        structure = "CPS"  # bearish correction inside down leg
        conf = 0.6

    # --- Micro pullback: SPS/CPS but close near recent swing low / CPR / VWAP
    micro_pullback = False
    is_retesting = False

    try:
        last_low = float(lows[-1]) if lows else None
    except Exception:
        last_low = None

    # distance helper in %
    def _pct(a: float, b: float) -> float:
        return abs(a - b) / max(1.0, b) * 100.0

    if structure in {"SPS", "CPS"} and last_low is not None:
        if _pct(close, last_low) <= 0.6:  # within ~0.6% of last swing low
            micro_pullback = True

    # Retest = close very near CPR or VWAP (if available)
    for lvl in (cpr, vwap):
        if lvl is None:
            continue
        if _pct(close, float(lvl)) <= 0.4:
            is_retesting = True
            break

    return structure, conf, micro_pullback, is_retesting


# ============================================================
# 🔺 Public: STRUCTURE block
# ============================================================
def compute_structure_block(
    df: pl.DataFrame,
    indicators: Optional[Dict[str, Any]] = None,
    *,
    lookback: int = 60,
) -> Dict[str, Any]:
    """Bible SUPREME — STRUCTURE block.

    Inputs:
      • df  : intraday OHLCV (any timeframe, Polars DF)
      • indicators (optional): dict from compute_indicators(), so we can
        reuse CMP / CPR / VWAP without recomputing.

    Returns dict with keys:
      • Structure_Type        → "SPS" | "MCS" | "CPS" | "RPS" | "None"
      • Structure_Confidence  → 0.0–1.0
      • Swing_Highs           → last few swing high prices
      • Swing_Lows            → last few swing low prices
      • Micro_Pullback        → bool (price is in a tight pullback zone)
      • Is_Retesting_Level    → bool (retest of CPR/VWAP neighbourhood)
    """
    if df.is_empty() or df.height < 10:
        return {
            "Structure_Type": "None",
            "Structure_Confidence": 0.0,
            "Swing_Highs": [],
            "Swing_Lows": [],
            "Micro_Pullback": False,
            "Is_Retesting_Level": False,
        }

    df = ensure_sorted(df).tail(lookback)

    close_series = df["close"].cast(pl.Float64, strict=False)
    close_val = float(close_series.drop_nulls().tail(1).item())

    cpr = indicators.get("CPR") if indicators else None
    vwap = indicators.get("VWAP") if indicators else None

    swings = _swing_points(df, window=3, max_points=5)
    structure, conf, micro_pullback, is_retesting = _classify_structure(
        swings,
        close_val,
        cpr,
        vwap,
    )

    return {
        "Structure_Type": structure,
        "Structure_Confidence": float(conf),
        "Swing_Highs": swings.highs,
        "Swing_Lows": swings.lows,
        "Micro_Pullback": bool(micro_pullback),
        "Is_Retesting_Level": bool(is_retesting),
    }

# ============================================================
# TREND BLOCK — multi-horizon bias + strength (D / W / M)
# ============================================================


def _safe_pct_diff(a: Optional[float], b: Optional[float]) -> float:
    try:
        if a is None or b is None or b == 0:
            return 0.0
        return float((a - b) / b) * 100.0
    except Exception:
        return 0.0


def _bias_from_above_below(
    price: Optional[float], ref: Optional[float], up_thresh: float = 0.3, dn_thresh: float = -0.3
) -> str:
    """Generic helper: decide bias from how far price is from a reference."""
    if price is None or ref is None:
        return "Range"
    d = _safe_pct_diff(price, ref)
    if d >= up_thresh:
        return "Bullish"
    if d <= dn_thresh:
        return "Bearish"
    return "Range"


def _strength_from_distance(
    price: Optional[float],
    ref: Optional[float],
    tight: float = 0.5,
    medium: float = 1.5,
    strong: float = 3.0,
) -> float:
    """0–3 based on distance in % between price and ref."""
    if price is None or ref is None or ref == 0:
        return 0.0
    dist = abs(_safe_pct_diff(price, ref))
    if dist >= strong:
        return 3.0
    if dist >= medium:
        return 2.0
    if dist >= tight:
        return 1.0
    return 0.5  # very close but still directional


def compute_trend_block(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """Multi-horizon trend view using EMAs + CMP.

    We approximate:
      • Daily trend  (D)  → CMP vs EMA20 + EMA20 vs EMA50
      • Weekly trend (W)  → EMA20 vs EMA50 vs EMA200
      • Monthly trend(M)  → CMP vs EMA200 (slow regime)

    Returns:
      Trend_Bias_D / W / M  ("Bullish" / "Bearish" / "Range")
      Trend_Strength_D / W / M  (0.0–3.0)
      Trend_Bias   (overall majority)
      Trend_Score  (0–10)
      Trend_Label  (short human-readable summary)

    """
    cmp_ = indicators.get("CMP")
    ema20 = indicators.get("EMA20")
    ema50 = indicators.get("EMA50")
    ema200 = indicators.get("EMA200")
    rsi = indicators.get("RSI")

    # --- Daily horizon: CMP vs EMA20 + EMA20 vs EMA50
    d_bias_price = _bias_from_above_below(cmp_, ema20)
    d_bias_stack = _bias_from_above_below(ema20, ema50)
    if d_bias_price == d_bias_stack:
        bias_d = d_bias_price
    else:
        # if mixed, lean to "Range"
        bias_d = "Range"

    strength_d = _strength_from_distance(cmp_, ema20)
    # small RSI boost/penalty
    if isinstance(rsi, (int, float)):
        if rsi >= 60:
            strength_d += 0.5
        elif rsi <= 45:
            strength_d -= 0.5
    strength_d = max(0.0, min(strength_d, 3.0))

    # --- Weekly horizon: EMA20 vs EMA50 vs EMA200
    if ema20 is not None and ema50 is not None and ema200 is not None:
        if ema20 > ema50 > ema200:
            bias_w = "Bullish"
        elif ema20 < ema50 < ema200:
            bias_w = "Bearish"
        else:
            bias_w = "Range"
    else:
        bias_w = "Range"
    # strength from mid vs slow
    strength_w = _strength_from_distance(ema50, ema200)
    strength_w = max(0.0, min(strength_w, 3.0))

    # --- Monthly horizon: CMP vs EMA200 (slow regime)
    bias_m = _bias_from_above_below(cmp_, ema200, up_thresh=0.5, dn_thresh=-0.5)
    strength_m = _strength_from_distance(cmp_, ema200, tight=1.0, medium=3.0, strong=5.0)
    strength_m = max(0.0, min(strength_m, 3.0))

    # --- Composite bias (majority vote of D/W/M ignoring "Range")
    votes = [b for b in (bias_d, bias_w, bias_m) if b != "Range"]
    if not votes:
        bias_overall = "Range"
    else:
        bulls = sum(1 for b in votes if b == "Bullish")
        bears = sum(1 for b in votes if b == "Bearish")
        if bulls > bears:
            bias_overall = "Bullish"
        elif bears > bulls:
            bias_overall = "Bearish"
        else:
            bias_overall = "Range"

    # --- Composite score (0–10)
    # weight daily more, then weekly, then monthly
    raw_score = (3.0 * strength_d) + (2.0 * strength_w) + (1.5 * strength_m)
    # normalize roughly to 0–10
    trend_score = max(0.0, min(raw_score, 10.0))

    label = f"{bias_overall} (D:{bias_d} W:{bias_w} M:{bias_m})"

    return {
        "Trend_Bias_D": bias_d,
        "Trend_Bias_W": bias_w,
        "Trend_Bias_M": bias_m,
        "Trend_Strength_D": round(strength_d, 2),
        "Trend_Strength_W": round(strength_w, 2),
        "Trend_Strength_M": round(strength_m, 2),
        "Trend_Bias": bias_overall,
        "Trend_Score": round(trend_score, 2),
        "Trend_Label": label,
    }


if __name__ == "__main__":
    # lightweight self-test hook

    # Expect the caller to run this with a small DF sample
    print("bible_engine.compute_structure_block — module loaded.")
    # You can do:
    #   from queen.fetchers.upstox_fetcher import fetch_intraday_smart
    #   df = asyncio.run(fetch_intraday_smart("SYRMA", "15m", days=5))
    #   pprint.pp(compute_structure_block(df))
