#!/usr/bin/env python3
# ============================================================
# queen/services/bible_engine.py — v1.3
# Bible SUPREME Blocks (Phase 2, pure — no circular imports)
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from queen.helpers.candles import ensure_sorted, last_close
from queen.fetchers.nse_fetcher import fetch_nse_bands

__all__ = [
    "compute_structure_block",
    "compute_trend_block",
    "compute_vol_block",
    "compute_risk_block",
    "compute_alignment_block",
    "trade_validity_block",
    "compute_indicators_plus_bible",
]

# ============================================================
# 🔹 Small swing helpers
# ============================================================

@dataclass
class SwingPoints:
    highs: List[float]
    lows: List[float]


def _swing_points(df: pl.DataFrame, window: int = 3, max_points: int = 5) -> SwingPoints:
    """Detect local swing highs/lows using a small neighbourhood window."""
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
    """Map swings + context into (structure_type, confidence, micro_pullback, is_retesting)."""
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
        structure = "CPS"
        conf = 0.7
    elif hi_slope < 0 and lo_slope >= 0:
        structure = "CPS"
        conf = 0.6

    # --- Micro pullback: SPS/CPS but close near recent swing low / CPR / VWAP
    micro_pullback = False
    is_retesting = False

    try:
        last_low = float(lows[-1]) if lows else None
    except Exception:
        last_low = None

    def _pct(a: float, b: float) -> float:
        return abs(a - b) / max(1.0, b) * 100.0

    if structure in {"SPS", "CPS"} and last_low is not None:
        if _pct(close, last_low) <= 0.6:
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
    """Bible SUPREME — STRUCTURE block."""
    if df.is_empty() or df.height < 10:
        return {
            "Structure_Type": "None",
            "Structure_Confidence": 0.0,
            "Swing_Highs": [],
            "Swing_Lows": [],
            "Micro_Pullback": False,
            "Is_Retesting": False,
            "Is_Retesting_Level": False,  # alias
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
        # Canonical key:
        "Is_Retesting": bool(is_retesting),
        # Backward-compatible alias:
        "Is_Retesting_Level": bool(is_retesting),
    }


# ============================================================
# TREND BLOCK — multi-horizon bias + strength (D / W / M-ish)
# ============================================================

def _safe_pct_diff(a: Optional[float], b: Optional[float]) -> float:
    try:
        if a is None or b is None or b == 0:
            return 0.0
        return float((a - b) / b) * 100.0
    except Exception:
        return 0.0


def _bias_from_above_below(
    price: Optional[float],
    ref: Optional[float],
    up_thresh: float = 0.3,
    dn_thresh: float = -0.3,
) -> str:
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
    if price is None or ref is None or ref == 0:
        return 0.0
    dist = abs(_safe_pct_diff(price, ref))
    if dist >= strong:
        return 3.0
    if dist >= medium:
        return 2.0
    if dist >= tight:
        return 1.0
    return 0.5


def compute_trend_block(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """Multi-horizon trend view using EMAs + CMP (single-DF approximation)."""
    ind = indicators or {}

    df = ind.get("_df")  # optional Polars DF injected by caller

    cmp_ = ind.get("CMP") or ind.get("cmp")
    if cmp_ is None and isinstance(df, pl.DataFrame) and not df.is_empty():
        try:
            cmp_ = float(last_close(df))
        except Exception:
            cmp_ = None

    def _g(*keys):
        for k in keys:
            if k in ind and ind.get(k) is not None:
                return ind.get(k)
        return None

    ema20 = _g("EMA20", "ema20")
    ema50 = _g("EMA50", "ema50")
    ema200 = _g("EMA200", "ema200")
    rsi = _g("RSI", "rsi")

    # --- Daily horizon: CMP vs EMA20 + EMA20 vs EMA50
    d_bias_price = _bias_from_above_below(cmp_, ema20)
    d_bias_stack = _bias_from_above_below(ema20, ema50)
    if d_bias_price == d_bias_stack:
        bias_d = d_bias_price
    else:
        bias_d = "Range"

    strength_d = _strength_from_distance(cmp_, ema20)
    if isinstance(rsi, (int, float)):
        if rsi >= 60:
            strength_d += 0.5
        elif rsi <= 45:
            strength_d -= 0.5
    strength_d = max(0.0, min(strength_d, 3.0))

    # --- Weekly horizon: EMA20 vs EMA50 vs EMA200 (slow stack feel)
    if ema20 is not None and ema50 is not None and ema200 is not None:
        if ema20 > ema50 > ema200:
            bias_w = "Bullish"
        elif ema20 < ema50 < ema200:
            bias_w = "Bearish"
        else:
            bias_w = "Range"
    else:
        bias_w = "Range"

    strength_w = _strength_from_distance(ema50, ema200)
    strength_w = max(0.0, min(strength_w, 3.0))

    # --- Monthly horizon: CMP vs EMA200 (very slow regime)
    bias_m = _bias_from_above_below(cmp_, ema200, up_thresh=0.5, dn_thresh=-0.5)
    strength_m = _strength_from_distance(cmp_, ema200, tight=1.0, medium=3.0, strong=5.0)
    strength_m = max(0.0, min(strength_m, 3.0))

    # --- Composite bias
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

    # --- Composite score (0–10-ish)
    raw_score = (3.0 * strength_d) + (2.0 * strength_w) + (1.5 * strength_m)
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


# ============================================================
# VOL BLOCK — ATR / volatility regime
# ============================================================

def compute_vol_block(
    df: pl.DataFrame,
    indicators: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Volatility / ATR regime block."""
    ind = indicators or {}
    cmp_ = ind.get("CMP") or ind.get("cmp")

    daily_atr = ind.get("Daily_ATR")
    daily_atr_pct = ind.get("Daily_ATR_Pct")
    atr_intraday = ind.get("ATR") or ind.get("atr") or ind.get("atr_intraday")

    # --- derive Daily_ATR_Pct if missing but we have ATR + CMP
    if daily_atr is None and atr_intraday is not None:
        daily_atr = atr_intraday

    if daily_atr_pct is None and daily_atr is not None and cmp_:
        try:
            daily_atr_pct = float(daily_atr) / max(1.0, float(cmp_)) * 100.0
        except Exception:
            daily_atr_pct = None

    # --- intraday ATR% helper (for curiosity / debug)
    atr_intraday_pct = None
    if atr_intraday is not None and cmp_:
        try:
            atr_intraday_pct = float(atr_intraday) / max(1.0, float(cmp_)) * 100.0
        except Exception:
            atr_intraday_pct = None

    # --- classify volatility regime from daily_atr_pct
    vol_state = "Unknown"
    vol_regime = "Unknown"
    vol_score = 0.0

    if isinstance(daily_atr_pct, (int, float)):
        p = float(daily_atr_pct)
        if p < 1.5:
            vol_state = "Quiet"
            vol_regime = "Compressed"
            vol_score = 3.0
        elif p < 3.5:
            vol_state = "Normal"
            vol_regime = "Normal"
            vol_score = 2.0
        else:
            vol_state = "Wild"
            vol_regime = "Expanded"
            vol_score = 1.0

    # --- risk rating from ATR% if not already present
    risk_rating = ind.get("Risk_Rating")
    if not risk_rating and isinstance(daily_atr_pct, (int, float)):
        p = float(daily_atr_pct)
        if p < 1.5:
            risk_rating = "Low"
        elif p < 3.5:
            risk_rating = "Medium"
        else:
            risk_rating = "High"

    # --- SL_Zone helper if not present
    sl_zone = ind.get("SL_Zone")
    if not sl_zone and risk_rating:
        if risk_rating == "Low":
            sl_zone = "Tight"
        elif risk_rating == "Medium":
            sl_zone = "Normal"
        else:
            sl_zone = "Loose"

    out: Dict[str, Any] = {
        "Daily_ATR": daily_atr,
        "Daily_ATR_Pct": daily_atr_pct,
        "ATR_Intraday": atr_intraday,
        "ATR_Intraday_Pct": atr_intraday_pct,
        "Vol_State": vol_state,
        "Vol_Regime": vol_regime,
        "Vol_Score": round(vol_score, 2),
    }

    if risk_rating:
        out["Risk_Rating"] = risk_rating
    if sl_zone:
        out["SL_Zone"] = sl_zone

    return out


# ============================================================
# RISK BLOCK — structure-aware risk view
# ============================================================

def compute_risk_block(
    structure: Dict[str, Any],
    trend: Dict[str, Any],
    vol: Dict[str, Any],
    indicators: Optional[Dict[str, Any]] = None,
    pos: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Structure-aware risk view on top of VOL."""
    ind = indicators or {}

    struct_type = structure.get("Structure_Type")
    struct_conf = float(structure.get("Structure_Confidence") or 0.0)

    trend_bias = trend.get("Trend_Bias", "Range")
    trend_score = float(trend.get("Trend_Score") or 0.0)

    vol_state = vol.get("Vol_State") or vol.get("Vol_Regime") or "Unknown"
    vol_score = float(vol.get("Vol_Score") or 0.0)

    # prefer Bible/vol rating, fall back to indicators if missing
    risk_rating = vol.get("Risk_Rating") or ind.get("Risk_Rating") or "Medium"

    # --- Base risk around 5 = neutral ---
    risk = 5.0

    # 1) Volatility impact (more wild → more risk)
    if vol_state in ("Quiet", "Compressed"):
        risk -= 0.5
    elif vol_state in ("Wild", "Expanded"):
        risk += 0.8

    # 2) Structure type
    if struct_type == "SPS":
        risk -= 0.4 * max(0.5, struct_conf)
    elif struct_type == "RPS":
        risk += 0.4 * max(0.5, struct_conf)
    elif struct_type == "MCS":
        risk += 0.2  # range = chop risk

    # 3) Trend bias
    if trend_bias == "Bullish":
        risk -= 0.3 * min(3.0, trend_score / 3.0)
    elif trend_bias == "Bearish":
        risk += 0.3 * min(3.0, trend_score / 3.0)

    # 4) ATR-based rating
    if isinstance(risk_rating, str):
        rr = risk_rating.lower()
        if rr == "low":
            risk -= 0.5
        elif rr == "high":
            risk += 0.5

    # clamp to 0–10
    risk_score = max(0.0, min(10.0, risk))

    # --- Profile labels ---
    if risk_score <= 3:
        profile = "Low-Risk / Smooth Trend"
    elif risk_score <= 6:
        profile = "Balanced / Normal Risk"
    else:
        profile = "High-Risk / Volatile"

    # --- Position sizing hint ---
    if risk_score <= 3 and (str(risk_rating).lower() in {"low", "medium"}):
        size_suggestion = "Normal–Aggressive"
    elif risk_score <= 6:
        size_suggestion = "Normal"
    else:
        size_suggestion = "Light"

    out: Dict[str, Any] = {
        "Risk_Score": round(risk_score, 2),
        "Risk_Profile": profile,
        "Risk_Rating": risk_rating,
        "Position_Size_Suggestion": size_suggestion,
    }

    if pos and pos.get("qty"):
        out["Has_Position"] = True
    else:
        out["Has_Position"] = False

    return out


# ============================================================
# ALIGNMENT BLOCK — EMA stack + VWAP + CPR
# ============================================================

def compute_alignment_block(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """Alignment of price with EMA stack + VWAP + CPR."""
    ind = indicators or {}

    cmp_ = ind.get("CMP") or ind.get("cmp")
    ema20 = ind.get("EMA20")
    ema50 = ind.get("EMA50")
    ema200 = ind.get("EMA200")
    ema_bias = (ind.get("EMA_BIAS") or ind.get("ema_bias") or "").title()

    vwap = ind.get("VWAP")
    cpr = ind.get("CPR")  # may be a level or central pivot, depends on your impl

    vwap_zone = (
        ind.get("vwap_zone")
        or ind.get("VWAP_Zone")
        or ind.get("VWAP_Context")
    )
    cpr_ctx = (
        ind.get("cpr_ctx")
        or ind.get("CPR_Ctx")
        or ind.get("CPR_Context")
    )

    # ---------- EMA stack state ----------
    ema_state = "Mixed"
    ema_score = 1.5

    if ema20 is not None and ema50 is not None and ema200 is not None:
        if ema20 > ema50 > ema200:
            ema_state = "Strong Bullish"
            ema_score = 4.0
        elif ema20 > ema50 and ema50 >= ema200:
            ema_state = "Bullish"
            ema_score = 3.0
        elif ema20 < ema50 < ema200:
            ema_state = "Strong Bearish"
            ema_score = 4.0
        elif ema20 < ema50 and ema50 <= ema200:
            ema_state = "Bearish"
            ema_score = 3.0
        else:
            ema_state = "Mixed"
            ema_score = 1.5
    else:
        # ✅ fallback so label never goes "Unknown"
        if ema_bias in ("Bullish", "Strong Bullish"):
            ema_state = "Bullish"
            ema_score = 2.5
        elif ema_bias in ("Bearish", "Strong Bearish"):
            ema_state = "Bearish"
            ema_score = 2.5
        else:
            ema_state = "Mixed"
            ema_score = 1.5

    # ---------- VWAP context ----------
    def _vwap_ctx_from_raw(cmp_val, vwap_val) -> str:
        if cmp_val is None or vwap_val is None:
            return "Unknown"
        diff = _safe_pct_diff(cmp_val, vwap_val)
        if abs(diff) <= 0.3:
            return "Near/Choppy"
        return "Above" if diff > 0 else "Below"

    if vwap_zone:
        vz = str(vwap_zone)
        if "Above" in vz:
            vwap_ctx = "Above"
            vwap_score = 2.0
        elif "Below" in vz:
            vwap_ctx = "Below"
            vwap_score = 2.0
        elif "Near" in vz or "Inside" in vz or "Choppy" in vz:
            vwap_ctx = "Near/Choppy"
            vwap_score = 1.0
        else:
            vwap_ctx = vz
            vwap_score = 0.5
    else:
        vwap_ctx = _vwap_ctx_from_raw(cmp_, vwap)
        if vwap_ctx in {"Above", "Below"}:
            vwap_score = 2.0
        elif vwap_ctx == "Near/Choppy":
            vwap_score = 1.0
        else:
            vwap_score = 0.0

    # ---------- CPR context ----------
    if cpr_ctx:
        cc = str(cpr_ctx)
        if "Above" in cc or "Bullish" in cc:
            cpr_context = "Above"
            cpr_score = 2.0
        elif "Below" in cc or "Bearish" in cc:
            cpr_context = "Below"
            cpr_score = 2.0
        elif "Inside" in cc:
            cpr_context = "Inside"
            cpr_score = 1.5
        elif "At" in cc or "Unknown" in cc:
            cpr_context = "At/Unknown"
            cpr_score = 0.5
        else:
            cpr_context = cc
            cpr_score = 0.5
    else:
        cpr_context = "Unknown"
        cpr_score = 0.0

    # ---------- Composite alignment score ----------
    raw_align = ema_score + vwap_score + cpr_score
    align_score = max(0.0, min(raw_align, 10.0))

    label_parts = [ema_state, f"VWAP {vwap_ctx}", f"CPR {cpr_context}"]
    align_label = " · ".join(label_parts)

    return {
        "Alignment_Score": round(align_score, 2),
        "Alignment_Label": align_label,
        "EMA_Stack_State": ema_state,
        "VWAP_Context": vwap_ctx,
        "CPR_Context": cpr_context,
    }


# ============================================================
# TRADE VALIDITY BLOCK — Intraday BUY / WATCH / AVOID
# ============================================================

def trade_validity_block(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intraday classification of a symbol:
        • BUY   — executable long
        • WATCH — constructive, setup forming, not clean yet
        • AVOID — unfavourable structure / risk

    Purely intraday. Uses:
      • CMP → Entry → SL geometry
      • VWAP / CPR context
      • Trend_Bias / Structure_Type / Structure_Confidence
      • Risk_Rating
      • Reversal_Score
      • Tactical_Index (quality, if present)
      • UC/LC zones
    """

    ind = metrics or {}

    # ---------- Extract geometry ----------
    cmp_ = ind.get("CMP") or ind.get("cmp")
    entry = ind.get("entry") or ind.get("entry_price")
    sl = ind.get("SL") or ind.get("sl") or ind.get("stop_loss")
    vwap = ind.get("VWAP")
    cpr = ind.get("CPR")

    trend_bias = ind.get("Trend_Bias", "Range")
    struct_type = ind.get("Structure_Type") or "None"
    struct_conf = float(ind.get("Structure_Confidence") or 0.0)
    reversal_score = float(ind.get("Reversal_Score") or 0.0)
    risk_rating = str(ind.get("Risk_Rating") or "Medium").title()
    tactical_index = float(ind.get("Tactical_Index") or 0.0)
    align_score = float(ind.get("Alignment_Score") or 0.0)

    upper_circuit = ind.get("upper_circuit")
    lower_circuit = ind.get("lower_circuit")

    # Missing CMP or entry → no trade
    if cmp_ is None or entry is None:
        return {
            "Trade_Status": "WATCH",
            "Trade_Status_Label": "WATCH — Insufficient data",
            "Trade_Reason": "CMP or Entry missing",
            "Trade_Score": None,
            "Trade_Flags": ["missing_price"],
        }

    try:
        cmp_ = float(cmp_)
        entry = float(entry)
        if sl is not None:
            sl = float(sl)
    except Exception:
        return {
            "Trade_Status": "WATCH",
            "Trade_Status_Label": "WATCH — Data parsing error",
            "Trade_Reason": "Cannot parse CMP/Entry/SL",
            "Trade_Score": None,
            "Trade_Flags": ["parse_error"],
        }

    def _pct(a, b):  # reuse safe % diff
        return _safe_pct_diff(a, b)

    # ---------- Geometry Flags ----------
    above_entry = cmp_ >= entry * 1.0005
    below_entry = cmp_ <= entry * 0.9995
    near_entry = abs(_pct(cmp_, entry)) <= 0.2

    above_vwap = vwap is not None and cmp_ >= float(vwap) * 1.0005
    below_vwap = vwap is not None and cmp_ <= float(vwap) * 0.9995

    above_cpr = cpr is not None and cmp_ >= float(cpr) * 1.0005
    below_cpr = cpr is not None and cmp_ <= float(cpr) * 0.9995

    below_sl = sl is not None and cmp_ < sl * 0.999

    # UC/LC filters (very important for intraday)
    near_uc = False
    near_lc = False
    if upper_circuit:
        near_uc = abs(_pct(cmp_, upper_circuit)) <= 1.0
    if lower_circuit:
        near_lc = abs(_pct(cmp_, lower_circuit)) <= 1.0

    # ============================================================
    # 1) Hard AVOID conditions
    # ============================================================
    if below_sl:
        return {
            "Trade_Status": "AVOID",
            "Trade_Status_Label": "AVOID — CMP below SL",
            "Trade_Reason": "CMP < SL",
            "Trade_Score": 1.0,
            "Trade_Flags": ["below_sl"],
        }

    if near_uc:
        return {
            "Trade_Status": "AVOID",
            "Trade_Status_Label": "AVOID — Near Upper Circuit",
            "Trade_Reason": "CMP too close to UC",
            "Trade_Score": 1.0,
            "Trade_Flags": ["uc_zone"],
        }

    if near_lc:
        return {
            "Trade_Status": "AVOID",
            "Trade_Status_Label": "AVOID — Near Lower Circuit",
            "Trade_Reason": "CMP too close to LC",
            "Trade_Score": 1.0,
            "Trade_Flags": ["lc_zone"],
        }

    if below_vwap and below_cpr:
        return {
            "Trade_Status": "AVOID",
            "Trade_Status_Label": "AVOID — Below CPR & VWAP",
            "Trade_Reason": "Lost structure",
            "Trade_Score": min(tactical_index, 3.0),
            "Trade_Flags": ["below_cpr_vwap"],
        }

    if trend_bias == "Bearish" and tactical_index < 5:
        return {
            "Trade_Status": "AVOID",
            "Trade_Status_Label": "AVOID — Bearish trend",
            "Trade_Reason": "Trend_Bias = Bearish",
            "Trade_Score": tactical_index,
            "Trade_Flags": ["bearish_trend"],
        }

    # ============================================================
    # 2) BUY conditions — clean intraday LONG
    # ============================================================
    good_trend = trend_bias == "Bullish"
    good_structure = struct_type in {"SPS", "CPS"} and struct_conf >= 0.6
    good_risk = risk_rating in {"Low", "Medium"}
    low_reversal = reversal_score <= 1.5
    good_align = align_score == 0.0 or align_score >= 5.0

    if all([good_trend, good_structure, good_risk, low_reversal, (not below_vwap)]):

        # Must not be a bad entry geometry
        if below_entry:
            return {
                "Trade_Status": "WATCH",
                "Trade_Status_Label": "WATCH — Price below entry",
                "Trade_Reason": "CMP < Entry",
                "Trade_Score": tactical_index,
                "Trade_Flags": ["below_entry"],
            }

        if not above_cpr:
            return {
                "Trade_Status": "WATCH",
                "Trade_Status_Label": "WATCH — Needs CPR reclaim",
                "Trade_Reason": "CMP not above CPR",
                "Trade_Score": tactical_index,
                "Trade_Flags": ["cpr_reclaim_needed"],
            }

        # Clean BUY
        return {
            "Trade_Status": "BUY",
            "Trade_Status_Label": "BUY — Clean intraday setup",
            "Trade_Reason": "Trend+Structure+Risk aligned",
            "Trade_Score": round(tactical_index, 2),
            "Trade_Flags": ["clean"],
        }

    # ============================================================
    # 3) Otherwise WATCH
    # ============================================================
    return {
        "Trade_Status": "WATCH",
        "Trade_Status_Label": "WATCH — Constructive but unready",
        "Trade_Reason": "Needs alignment / reclaim / better geometry",
        "Trade_Score": round(tactical_index, 2),
        "Trade_Flags": ["constructive"],
    }


# ============================================================
# UNIFIED: compute_indicators_plus_bible
# (pure — no imports from tactical_pipeline)
# ============================================================

def compute_indicators_plus_bible(
    df: pl.DataFrame,
    base_indicators: Optional[Dict[str, Any]] = None,
    *,
    symbol: Optional[str] = None,
    interval: str = "15m",
    pos: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    One-stop factory:

      base_indicators (from compute_indicators / scoring) +
      Bible blocks (structure / trend / vol / risk / alignment) +
      Trade validity (BUY / WATCH / AVOID)

    Returns a single `metrics` dict.
    This function is PURE with respect to tactical_pipeline
    (no imports from services.tactical_pipeline to avoid circulars).
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return base_indicators or {}

    df = ensure_sorted(df)

    # Start from caller snapshot (compute_indicators / other source)
    ind: Dict[str, Any] = dict(base_indicators or {})

    # ---------- Ensure CMP if missing ----------
    if "CMP" not in ind and "cmp" not in ind:
        try:
            ind["CMP"] = float(last_close(df))
        except Exception:
            pass

    # ---------- UC / LC injection (for Trade Validity block) ----------
    # Only touch these if we have a symbol and they are not already present.
    if symbol and ("upper_circuit" not in ind or "lower_circuit" not in ind):
        try:
            bands = fetch_nse_bands(symbol)
        except Exception:
            bands = None

        if bands:
            ind.setdefault("upper_circuit", bands.get("upper_circuit"))
            ind.setdefault("lower_circuit", bands.get("lower_circuit"))

    # ---------- Expose context to downstream blocks ----------
    ind["_df"] = df
    ind["_interval"] = interval
    if symbol:
        ind["_symbol"] = symbol
    if pos:
        ind["_pos"] = pos
        ind.setdefault("position", pos)

    # ---------- 1) Core Bible blocks ----------
    struct = compute_structure_block(df, ind)
    vol = compute_vol_block(df, ind)
    trend = compute_trend_block({**ind, **vol, **struct})
    risk = compute_risk_block(struct, trend, vol, indicators=ind, pos=pos)
    align = compute_alignment_block({**ind, **vol, **trend})

    # Merge all metrics in order (later blocks can override earlier keys if needed)
    metrics: Dict[str, Any] = {}
    for blk in (ind, struct, vol, trend, risk, align):
        if blk:
            metrics.update(blk)

    # ---------- 2) Trade validity on top (BUY / WATCH / AVOID) ----------
    validity = trade_validity_block(metrics)
    if validity:
        metrics.update(validity)

    # Convenience defaults
    if symbol:
        metrics.setdefault("symbol", symbol.upper())
    metrics.setdefault("interval", interval)

    return metrics

if __name__ == "__main__":
    print("bible_engine — structure / trend / vol / risk / alignment / trade blocks loaded.")
