#!/usr/bin/env python3
# ============================================================
# queen/services/scoring.py — v2.2 (Daily-ATR aware, Bible-ready)
# ------------------------------------------------------------
# Actionable scoring + early-signal fusion (cockpit / TUI ready)
#
# Responsibilities:
#   • Quick indicator snapshot from OHLCV (RSI / ATR / VWAP / CPR / OBV / EMAs)
#   • Daily ATR + risk snapshot derived from intraday bars
#   • Early signal fusion (registry signals + price-action fallback)
#   • Position-aware decision ("BUY", "ADD", "HOLD", "EXIT", "AVOID")
#   • Cockpit row builder with optional Pattern / Tactical fields
#
# Forward-only:
#   • No legacy reversal_stack.evaluate
#   • Clean hooks for advanced metrics if caller provides them:
#       - PatternScore / PatternComponent / PatternBias / TopPattern
#       - Reversal_Score / Reversal_Stack_Alert
#       - Tactical_Index / regime
#       - RScore_norm / VolX_norm / LBX_norm
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from queen.fetchers.nse_fetcher import fetch_nse_bands
from queen.helpers.market import MARKET_TZ
from queen.helpers.portfolio import compute_pnl, position_for
from queen.technicals.indicators import core as ind


# --------------- small utils -----------------
def _last(series: pl.Series) -> Optional[float]:
    if series is None or series.len() == 0:
        return None
    try:
        return float(series.drop_nulls().tail(1).item())
    except Exception:
        return None


def _ema_last(
    df: pl.DataFrame,
    period: int,
    column: str = "close",
) -> Optional[float]:
    try:
        return _last(ind.ema(df, period, column))
    except Exception:
        return None


# --------------- daily risk snapshot -----------------
def _daily_ohlc_from_intraday(df: pl.DataFrame) -> pl.DataFrame:
    """Compress intraday bars into 1 bar per session (IST date).

    Expects columns: timestamp, open, high, low, close.
    """
    if df.is_empty() or "timestamp" not in df.columns:
        # empty but well-typed frame to keep callers safe
        return pl.DataFrame(
            {
                "d": pl.Series([], dtype=pl.Date),
                "open": pl.Series([], dtype=pl.Float64),
                "high": pl.Series([], dtype=pl.Float64),
                "low": pl.Series([], dtype=pl.Float64),
                "close": pl.Series([], dtype=pl.Float64),
            }
        )

    dated = df.with_columns(
        pl.col("timestamp")
        .dt.convert_time_zone(MARKET_TZ.key)
        .dt.date()
        .alias("d")
    )

    daily = (
        dated.sort("timestamp")
        .group_by("d")  # 👈 Polars 1.x API (group_by, not groupby)
        .agg(
            pl.col("open").first().alias("open"),
            pl.col("high").max().alias("high"),
            pl.col("low").min().alias("low"),
            pl.col("close").last().alias("close"),
        )
        .sort("d")
    )

    return daily

def _daily_risk_snapshot(
    df: pl.DataFrame,
    period: int = 14,
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """Return (daily_atr, daily_atr_pct, risk_rating, sl_zone)."""
    daily = _daily_ohlc_from_intraday(df)
    if daily.is_empty() or daily.height < period + 1:
        return None, None, None, None

    try:
        atr_val = ind.atr_last(daily, period)
    except Exception:
        atr_val = None

    if atr_val is None:
        return None, None, None, None

    try:
        close_ser = daily["close"].drop_nulls()
        if close_ser.is_empty():
            return None, None, None, None
        ref_close = float(close_ser.tail(1).item())
    except Exception:
        return None, None, None, None

    if ref_close <= 0:
        return None, None, None, None

    atr_pct = float(atr_val) / ref_close * 100.0

    # Simple, explainable buckets — this is your "Bible risk scale"
    if atr_pct < 1.0:
        risk = "Low"
        sl_zone = "Tight"
    elif atr_pct <= 2.5:
        risk = "Medium"
        sl_zone = "Normal"
    else:
        risk = "High"
        sl_zone = "Wide"

    return float(atr_val), float(atr_pct), risk, sl_zone


# --------------- indicators snapshot -----------------
def compute_indicators(df: pl.DataFrame) -> Optional[Dict[str, Any]]:
    """Lightweight indicator snapshot for a single timeframe.

    Returns a dict that can be fed into `action_for()`.

    Keys:
      CMP, RSI, ATR, VWAP, CPR, OBV,
      EMA20, EMA50, EMA200, EMA_BIAS,
      Daily_ATR, Daily_ATR_Pct, Risk_Rating, SL_Zone,
      _df  (the raw DataFrame, for early-signal engines / Bible)
    """
    if df.is_empty() or df.height < 12:
        return None

    close = df["close"].cast(pl.Float64, strict=False)

    rsi_val = ind.rsi_last(close, 14)
    atr_val = ind.atr_last(df, 14)
    vwap_val = ind.vwap_last(df)
    cpr_val = ind.cpr_from_prev_day(df)
    obv_tr = ind.obv_trend(df)
    ema20 = _ema_last(df, 20)
    ema50 = _ema_last(df, 50)
    ema200 = _ema_last(df, 200)
    close_last = float(close.tail(1).item())

    ema_bias = "Neutral"
    if all(x is not None for x in (ema20, ema50, ema200)):
        if ema20 > ema50 > ema200:
            ema_bias = "Bullish"
        elif ema20 < ema50 < ema200:
            ema_bias = "Bearish"

    # ---- Daily ATR / risk, derived from intraday bars ----
    daily_atr, daily_atr_pct, risk_rating, sl_zone = _daily_risk_snapshot(df)

    return {
        "CMP": close_last,
        "RSI": rsi_val,
        "ATR": atr_val,
        "VWAP": vwap_val,
        "CPR": cpr_val,
        "OBV": obv_tr,
        "EMA20": ema20,
        "EMA50": ema50,
        "EMA200": ema200,
        "EMA_BIAS": ema_bias,
        # Daily risk lens (used by Bible / ladders)
        "Daily_ATR": daily_atr,
        "Daily_ATR_Pct": daily_atr_pct,
        "Risk_Rating": risk_rating,
        "SL_Zone": sl_zone,
        # Let early-signal engines + Bible see full context
        "_df": df,
    }


# --------------- registry signals (optional) -----------------
try:
    # expected to return dicts like {"score": float, "reasons":[...]} or similar
    from queen.technicals.signals.pre_breakout import evaluate as _pre_breakout_eval
except Exception:
    _pre_breakout_eval = None  # type: ignore

try:
    from queen.technicals.signals.tactical.squeeze_pulse import (
        evaluate as _squeeze_pulse_eval,
    )
except Exception:
    _squeeze_pulse_eval = None  # type: ignore


def _normalize_signal(payload: Dict | None, name: str) -> Tuple[int, List[str]]:
    """Turn a registry signal payload into (score, reasons). Clamp to [0..5]."""
    if not isinstance(payload, dict):
        return 0, []
    try:
        score = int(round(float(payload.get("score", 0))))
    except Exception:
        score = 0
    reasons = payload.get("reasons") or payload.get("notes") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    score = max(0, min(score, 5))
    return score, [f"{name}: {r}" for r in reasons]


def _fallback_early(
    df: pl.DataFrame,
    cmp_: float,
    vwap_: Optional[float],
) -> Tuple[int, List[str]]:
    """Lightweight early detector when registry signals are absent:
    EMA20 upturn, RSI mid-zone upward cross, VWAP reclaim proximity.
    Max 3 points.
    """
    cues: List[str] = []
    s = 0

    # EMA20 upturn (last 2)
    try:
        e20 = ind.ema(df, 20).drop_nulls().tail(2).to_list()
        if len(e20) == 2 and e20[1] > e20[0]:
            s += 1
            cues.append("EMA20↑")
    except Exception:
        pass

    # RSI crossing up through 50
    try:
        r = df["close"].cast(pl.Float64).drop_nulls()
        if r.len() > 16:
            rsi_prev = ind.rsi_last(r.head(r.len() - 1), 14)
            rsi_now = ind.rsi_last(r, 14)
            if (
                rsi_prev is not None
                and rsi_now is not None
                and rsi_prev < 50 <= rsi_now
            ):
                s += 1
                cues.append("RSI→50↑")
    except Exception:
        pass

    # Very near VWAP (potential reclaim)
    if vwap_ is not None and abs(cmp_ - vwap_) / max(1.0, vwap_) <= 0.003:
        s += 1
        cues.append("Near VWAP")

    return min(s, 3), cues


def _early_bundle(
    df: pl.DataFrame,
    cmp_: float,
    vwap_: Optional[float],
) -> Tuple[int, List[str]]:
    """Fuse registry signals; fallback if none. Max registry contribution = 6.

    Note:
      • Uses pre_breakout + squeeze_pulse if available.
      • ReversalStack / Tactical stack are handled separately in Bible engine.

    """
    total = 0
    reasons: List[str] = []

    if _pre_breakout_eval:
        p_score, p_reasons = _normalize_signal(_pre_breakout_eval(df), "PreBreakout")
        total += p_score
        reasons += p_reasons

    if _squeeze_pulse_eval:
        s_score, s_reasons = _normalize_signal(_squeeze_pulse_eval(df), "Squeeze")
        total += s_score
        reasons += s_reasons

    total = min(total, 6)

    if total == 0:
        fb_score, fb_reasons = _fallback_early(df, cmp_, vwap_)
        total += fb_score
        reasons += fb_reasons

    return total, reasons


# --------------- base tactical score -----------------
def score_symbol(indd: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Base, indicator-only tactical score (0–10).

    Inputs: EMA_BIAS, RSI, VWAP, CPR, OBV, CMP, EMA50.
    """
    score = 0.0
    tags: List[str] = []

    ema_bias = indd.get("EMA_BIAS")
    rsi = indd.get("RSI") or 0.0
    vwap = indd.get("VWAP")
    cpr = indd.get("CPR")
    obv = (indd.get("OBV") or "").lower()
    cmp_ = indd.get("CMP") or 0.0
    ema50 = indd.get("EMA50")

    if ema_bias == "Bullish":
        score += 3
        tags.append("EMA↑")
    elif ema_bias == "Bearish":
        tags.append("EMA↓")

    if rsi >= 60:
        score += 3
        tags.append("RSI≥60")
    elif rsi >= 55:
        score += 2
        tags.append("RSI≥55")
    elif rsi <= 45:
        tags.append("RSI≤45")

    if vwap is not None and cmp_ > vwap:
        score += 1
        tags.append("VWAP>")

    if ema50 is not None and cmp_ > ema50:
        score += 2
        tags.append("EMA50>")

    if "rising" in obv:
        score += 1
        tags.append("OBV↑")

    if cpr is not None and cmp_ > cpr:
        score += 1
        tags.append("CPR>")

    return min(score, 10.0), tags


# --------------- ladders & entries -----------------
def _ladder_from_base(base: float, atr: Optional[float]) -> Tuple[float, List[str]]:
    """Return (SL, [T1, T2, T3]) strings using ATR for spacing.

    ATR here is *preferably* Daily_ATR (session volatility),
    but will gracefully fall back to intraday ATR.
    """
    atr_val = atr or max(1.0, base * 0.01)
    t1 = round(base + 0.5 * atr_val, 1)
    t2 = round(base + 1.0 * atr_val, 1)
    t3 = round(base + 1.5 * atr_val, 1)
    sl = round(base - 1.0 * atr_val, 1)
    return sl, [f"T1 {t1}", f"T2 {t2}", f"T3 {t3}"]


def _non_position_entry(
    cmp_: float,
    vwap: Optional[float],
    ema20: Optional[float],
    cpr: Optional[float],
    atr: Optional[float],
) -> float:
    """Entry for fresh positions – above strongest support with a small buffer."""
    base = max(x for x in [cmp_, vwap, ema20, cpr] if x is not None)
    buffer = max((atr or 0) * 0.10, cmp_ * 0.0025)  # 0.1×ATR or 0.25%
    return round(base + buffer, 1)


# --------------- main action function -----------------
def action_for(
    symbol: str,
    indd: Dict[str, Any],
    book: str = "all",
    use_uc_lc: bool = True,
) -> Dict[str, Any]:
    """Build a cockpit row for a symbol.

    `indd` may contain:
      • Base indicators (CMP / RSI / ATR / VWAP / CPR / OBV / EMA*)
      • Daily risk snapshot (Daily_ATR / Daily_ATR_Pct / Risk_Rating / SL_Zone)
      • _df              → for early-signal fusion
      • Optional advanced metrics:
          - PatternScore / PatternComponent / PatternBias / TopPattern
          - Reversal_Score / Reversal_Stack_Alert
          - Tactical_Index / regime
          - RScore_norm / VolX_norm / LBX_norm
    """
    cmp_ = float(indd["CMP"])
    atr_intraday = indd.get("ATR")
    daily_atr = indd.get("Daily_ATR")
    # Prefer daily ATR for ladders; fall back to intraday ATR
    atr_for_ladder = daily_atr or atr_intraday

    vwap = indd.get("VWAP")
    cpr = indd.get("CPR")
    ema20 = indd.get("EMA20")

    # --- Base indicator-driven score
    base_score, drivers = score_symbol(indd)

    # --- Early signals (registry-first) if we have DF
    df_ctx: Optional[pl.DataFrame] = (
        indd.get("_df") if isinstance(indd.get("_df"), pl.DataFrame) else None
    )
    early_score, early_reasons = (0, [])
    if df_ctx is not None and df_ctx.height >= 30:
        early_score, early_reasons = _early_bundle(df_ctx, cmp_, vwap)

    total_score = min(10, int(round(base_score + early_score)))

    # --- Position-aware decision
    pos = position_for(symbol, book=book)
    held = bool(pos)

    if held:
        if total_score >= 8 or early_score >= 3:
            decision = "ADD"
            bias = "Long"
        elif total_score <= 3:
            decision = "EXIT"
            bias = "Weak"
        else:
            decision = "HOLD"
            bias = "Neutral"
    else:
        if total_score >= 8:
            decision = "BUY"
            bias = "Long"
        elif total_score >= 5 or early_score >= 2:
            decision = "HOLD"
            bias = "Neutral"
        else:
            decision = "AVOID"
            bias = "Weak"

    # --- Targets & SL
    if held:
        base_px = float(pos.get("avg_price") or cmp_)
        entry = round(base_px, 1)
        sl, targets = _ladder_from_base(base_px, atr_for_ladder)
    else:
        entry = _non_position_entry(cmp_, vwap, ema20, cpr, atr_for_ladder)
        sl, targets = _ladder_from_base(entry, atr_for_ladder)

    # --- UC/LC notes
    notes: List[str] = []
    if use_uc_lc:
        bands = fetch_nse_bands(symbol)
        if bands:
            uc, lc = bands.get("upper_circuit", 0.0), bands.get("lower_circuit", 0.0)
            if uc > 0:
                gap_uc = (uc - cmp_) / uc * 100.0
                if 0 <= gap_uc <= 1.5:
                    notes.append("Near UC")
            if lc > 0:
                gap_lc = (cmp_ - lc) / lc * 100.0
                if 0 <= gap_lc <= 1.5:
                    notes.append("Near LC")

    # --- Context labels
    vwap_zone = (
        "Above"
        if (vwap is not None and cmp_ > vwap)
        else "Below"
        if (vwap is not None and cmp_ < vwap)
        else "Neutral"
    )
    cpr_ctx = (
        "Above CPR"
        if (cpr is not None and cmp_ > cpr)
        else "Below CPR"
        if (cpr is not None and cmp_ < cpr)
        else "At/Unknown"
    )

    if early_reasons:
        notes.insert(0, "EARLY: " + ", ".join(early_reasons))
    if drivers:
        notes.append("Drivers: " + " ".join(drivers))

    # --- Optional advanced metrics (Pattern / Tactical / Volatility)
    pattern_score = (
        indd.get("PatternScore")
        if indd.get("PatternScore") is not None
        else indd.get("PatternComponent")
    )
    pattern_bias = (
        indd.get("PatternBias")
        or indd.get("pattern_bias")
        or indd.get("PatternDirection")
    )
    top_pattern = indd.get("TopPattern") or indd.get("pattern_name")

    reversal_score = indd.get("Reversal_Score")
    reversal_alert = indd.get("Reversal_Stack_Alert")

    # Tactical core outputs (if caller ran TacticalCore)
    tactical_index = indd.get("Tactical_Index")
    regime = indd.get("regime")  # may be dict or simple label
    if isinstance(regime, dict):
        regime_name = regime.get("name")
        regime_label = regime.get("label")
        regime_color = regime.get("color")
    else:
        regime_name = regime
        regime_label = None
        regime_color = None

    rscore_norm = indd.get("RScore_norm")
    volx_norm = indd.get("VolX_norm")
    lbx_norm = indd.get("LBX_norm")

    # --- Bible Trend fields (from tactical_pipeline / bible_engine)
    trend_score = indd.get("Trend_Score")
    trend_bias = indd.get("Trend_Bias")
    trend_label = indd.get("Trend_Label")

    trend_bias_d = indd.get("Trend_Bias_D")
    trend_bias_w = indd.get("Trend_Bias_W")
    trend_bias_m = indd.get("Trend_Bias_M")

    # Preformat a compact trend line for UI (cards, TUI)
    trend_line = None
    try:
        if trend_score is not None and trend_bias:
            # safe float
            ts = float(trend_score)
                        # small shorthand for D/W/M parts
            d = (trend_bias_d or "Range")[0].upper()
            w = (trend_bias_w or "Range")[0].upper()
            m = (trend_bias_m or "Range")[0].upper()
            trend_line = f"Trend: {ts:.1f}/10 ({trend_bias} D:{d} W:{w} M:{m})"
        elif trend_label:
                trend_line = f"Trend: {trend_label}"
    except Exception:
            # keep it optional; don't break the row
            trend_line = None

    # --- Base cockpit row
    row: Dict[str, Any] = {
        "symbol": symbol,
        "cmp": round(cmp_, 1),
        "score": int(total_score),
        "early": int(early_score),  # 0–6
        "decision": decision,
        "bias": bias,
        "drivers": drivers,
        "entry": round(entry, 1),
        "sl": sl,
        "targets": targets,
        "vwap_zone": vwap_zone,
        "cpr_ctx": cpr_ctx,
        "atr": atr_intraday,
        "daily_atr": daily_atr,
        "daily_atr_pct": indd.get("Daily_ATR_Pct"),
        "risk_rating": indd.get("Risk_Rating"),
        "sl_zone": indd.get("SL_Zone"),
        "obv": indd.get("OBV"),
        "ema_bias": indd.get("EMA_BIAS"),
        "ema50": indd.get("EMA50"),
        "cpr": cpr,
        "held": held,
        "advice": (
            "ADD 10–15% on strength; trail to VWAP"
            if (held and decision == "ADD")
            else "HOLD; trail SL to EMA20/VWAP"
            if held
            else "Starter on strength; respect SL"
            if decision == "BUY"
            else "Wait for confirmation; keep on watch"
            if decision == "HOLD"
            else "Avoid for now"
        ),
        "notes": " | ".join(notes) if notes else "—",
        "position": pos or {},
    }

    # --- Attach optional advanced fields (only if present)
    if pattern_score is not None:
        row["pattern_score"] = float(pattern_score)
    if pattern_bias is not None:
        row["pattern_bias"] = pattern_bias
    if top_pattern is not None:
        row["top_pattern"] = top_pattern

    if reversal_score is not None:
        row["reversal_score"] = float(reversal_score)
    if reversal_alert is not None:
        row["reversal_alert"] = reversal_alert

    if tactical_index is not None:
        row["tactical_index"] = float(tactical_index)
    if regime_name is not None:
        row["tactical_regime"] = regime_name
    if regime_label is not None:
        row["tactical_regime_label"] = regime_label
    if regime_color is not None:
        row["tactical_regime_color"] = regime_color

    if rscore_norm is not None:
        row["rscore_norm"] = float(rscore_norm)
    if volx_norm is not None:
        row["volx_norm"] = float(volx_norm)
    if lbx_norm is not None:
        row["lbx_norm"] = float(lbx_norm)

    # --- Attach Trend fields so UI can show them
    if trend_score is not None:
        row["trend_score"] = float(trend_score)
    if trend_bias is not None:
        row["trend_bias"] = trend_bias
    if trend_label is not None:
        row["trend_label"] = trend_label
    if trend_bias_d is not None:
        row["trend_bias_d"] = trend_bias_d
    if trend_bias_w is not None:
        row["trend_bias_w"] = trend_bias_w
    if trend_bias_m is not None:
        row["trend_bias_m"] = trend_bias_m
    if trend_line is not None:
        row["trend_line"] = trend_line

    # --- PnL (if position exists)
    pnl = compute_pnl(cmp_, pos) if pos else None
    if pnl:
        row["pnl_abs"] = round(pnl[0], 2)
        row["pnl_pct"] = round(pnl[1], 2)

    return row
