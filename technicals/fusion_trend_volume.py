#!/usr/bin/env python3
# ============================================================
# queen/technicals/fusion_trend_volume.py — v1.2
# ------------------------------------------------------------
# Trend + Volume Fusion Override (Targeted, Non-breaking)
#
# Patch v1.2:
#   • Keep daily trend as primary guardrail.
#   • Add intraday breakout fallback when:
#       - day_ret% is strong,
#       - CMP > VWAP,
#       - EMAs are bullish stacked,
#       - intraday volume is strong.
#   • This lets genuine breakouts (like VOLTAMP’s spike day)
#     upgrade AVOID/EXIT/HOLD-weak into HOLD/BUY *while* the
#     breakout is alive, without changing EOD behaviour.
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import polars as pl

from queen.helpers.diagnostic_override_logger import log_trend_volume_override
from queen.technicals.trend_strength_daily import compute_daily_trend_strength
from queen.technicals.volume_strength_intraday import (
    compute_intraday_volume_strength,
)

BEARISH_DECISIONS = {"AVOID", "EXIT"}
WEAK_BIASES = {"Weak", "Neutral"}


def _safe_pct(a: Optional[float], b: Optional[float]) -> float:
    """Safe percentage change helper: (a-b)/b * 100."""
    try:
        if a is None or b is None:
            return 0.0
        b_f = float(b)
        if b_f == 0:
            return 0.0
        return (float(a) - b_f) / b_f * 100.0
    except Exception:
        return 0.0


def _is_candidate_for_override(decision: str, bias: str) -> bool:
    """Return True if this (decision, bias) is a bearish/weak candidate."""
    d = (decision or "").upper()
    b = (bias or "").capitalize()

    if d in BEARISH_DECISIONS:
        return True
    if d == "HOLD" and b in WEAK_BIASES:
        return True
    return False


def _is_strong_up_trend(trend_ctx: Dict[str, Any]) -> bool:
    """Primary: daily trend model says 'strong up'.

    Expects keys from compute_daily_trend_strength():
      - Trend_Strength_Label_D
      - Trend_Strength_Score_D
      - Trend_HHHL_Confirm_D
      - Trend_Ema_Stack_D  (e.g. 'bull', 'bear', 'flat', 'unknown')
    """
    label = (trend_ctx.get("Trend_Strength_Label_D") or "").lower()
    score = float(trend_ctx.get("Trend_Strength_Score_D") or 0.0)
    hhhl = bool(trend_ctx.get("Trend_HHHL_Confirm_D") or False)
    stack = (trend_ctx.get("Trend_Ema_Stack_D") or "").lower()

    return (
        stack == "bull"
        and "up" in label
        and score >= 6.0
        and hhhl
    )


def _is_strong_volume(vol_ctx: Dict[str, Any]) -> bool:
    """Strong intraday volume cluster from volume_strength_intraday."""
    label = (vol_ctx.get("Vol_Strength_Label_I") or "").lower()
    score = float(vol_ctx.get("Vol_Strength_Score_I") or 0.0)

    if score < 5.0:
        return False

    return any(
        key in label
        for key in ("strong", "very strong", "extreme")
    )


def _is_intraday_breakout_trend(
    indd: Dict[str, Any],
    df_ctx: pl.DataFrame,
    vol_ctx: Dict[str, Any],
) -> bool:
    """Fallback: intraday breakout definition for 'strong trend day'
    when daily trend context is not yet convinced.

    Conditions (Hybrid Trend-First philosophy):
      • day_ret% >= 2.5% vs first intraday open
      • CMP > VWAP
      • EMA20 > EMA50 > EMA200
      • volume strong:
          - Vol_Strength_Ratio_I >= 1.5 OR
          - Vol_PctRank_I >= 80 OR
          - volume label already 'strong/very strong'
    """
    if df_ctx.is_empty():
        return False

    cmp_ = indd.get("CMP") or indd.get("cmp")
    try:
        if cmp_ is None:
            return False
        cmp_f = float(cmp_)
    except Exception:
        return False

    # Day return vs first bar open of the session
    try:
        first_open_ser = df_ctx["open"].drop_nulls()
        if first_open_ser.is_empty():
            return False
        first_open = float(first_open_ser.head(1).item())
    except Exception:
        return False

    day_ret_pct = _safe_pct(cmp_f, first_open)

    vwap = indd.get("VWAP")
    ema20 = indd.get("EMA20")
    ema50 = indd.get("EMA50")
    ema200 = indd.get("EMA200")

    try:
        above_vwap = vwap is not None and cmp_f > float(vwap)
    except Exception:
        above_vwap = False

    emastack_bull = (
        isinstance(ema20, (int, float))
        and isinstance(ema50, (int, float))
        and isinstance(ema200, (int, float))
        and ema20 > ema50 > ema200
    )

    # Volume intensity from vol_ctx
    vol_ratio = float(vol_ctx.get("Vol_Strength_Ratio_I") or 0.0)
    vol_pct_rank = float(vol_ctx.get("Vol_PctRank_I") or 0.0)
    vol_strong_label = _is_strong_volume(vol_ctx)

    strong_vol = (
        vol_ratio >= 1.5
        or vol_pct_rank >= 80.0
        or vol_strong_label
    )

    # Thresholds chosen to capture genuine breakout days,
    # not tiny noise spikes.
    return (
        day_ret_pct >= 2.5
        and above_vwap
        and emastack_bull
        and strong_vol
    )


def maybe_apply_trend_volume_override(
    indd: Dict[str, Any],
    decision: str,
    bias: str,
    *,
    interval: str = "15m",
    mode: str = "intraday",
) -> Tuple[str, str, Dict[str, Any]]:
    """Return possibly overridden (decision, bias) + context dict.

    Args:
        indd:    Indicators dict; expected to contain '_df' as Polars DF.
        decision:
            Current action decision (e.g., "BUY", "HOLD", "AVOID", "EXIT").
        bias:
            Current bias label (e.g., "Long", "Neutral", "Weak").
        interval:
            Intraday interval string (for logging, cockpit).
        mode:
            Logical mode ("intraday"/"btst"/"swing"/"daily").

    Returns:
        (new_decision, new_bias, tv_ctx)

    Logic:
      • Only consider weak/bearish decisions.
      • Require BOTH:
          - Strong *trend* (daily OR intraday-breakout fallback)
          - Strong intraday *volume*
      • Then:
          AVOID  → HOLD (Long bias)
          HOLD   → BUY  (Long bias)   [when bias is Weak/Neutral]
          EXIT   → HOLD (Neutral bias)

    """
    tv_ctx: Dict[str, Any] = {
        "TV_Override_Applied": False,
        "TV_Override_Reason": None,
        "TV_Override_Interval": interval,
        "TV_Trend_Mode": None,  # "daily_trend" / "intraday_breakout" / None
    }

    if not _is_candidate_for_override(decision, bias):
        return decision, bias, tv_ctx

    df_ctx: Optional[pl.DataFrame] = (
        indd.get("_df") if isinstance(indd.get("_df"), pl.DataFrame) else None
    )
    if df_ctx is None or df_ctx.is_empty():
        return decision, bias, tv_ctx

    try:
        trend_ctx = compute_daily_trend_strength(df_ctx) or {}
    except Exception:
        trend_ctx = {}

    try:
        vol_ctx = compute_intraday_volume_strength(df_ctx) or {}
    except Exception:
        vol_ctx = {}

    tv_ctx.update(trend_ctx)
    tv_ctx.update(vol_ctx)

    # 1) Primary: daily trend + volume
    strong_trend = _is_strong_up_trend(trend_ctx)
    strong_vol = _is_strong_volume(vol_ctx)

    # 2) Fallback: intraday breakout trend when daily model is unconvinced
    if not strong_trend and strong_vol:
        if _is_intraday_breakout_trend(indd, df_ctx, vol_ctx):
            strong_trend = True
            tv_ctx["TV_Trend_Mode"] = "intraday_breakout"
        else:
            tv_ctx["TV_Trend_Mode"] = None
    else:
        tv_ctx["TV_Trend_Mode"] = "daily_trend" if strong_trend else None

    # If either piece is missing, no override.
    if not strong_trend or not strong_vol:
        return decision, bias, tv_ctx

    old_decision = decision
    old_bias = bias

    d_up = (decision or "").upper()
    b_cap = bias.capitalize() if bias else "Neutral"

    if d_up == "AVOID":
        new_decision = "HOLD"
        new_bias = "Long"
        reason = (
            "TV-OVERRIDE: Strong uptrend (daily/intraday) + strong intraday "
            "volume — AVOID→HOLD (long bias)."
        )
    elif d_up == "HOLD" and b_cap in WEAK_BIASES:
        new_decision = "BUY"
        new_bias = "Long"
        reason = (
            "TV-OVERRIDE: Strong uptrend (daily/intraday) + strong intraday "
            "volume — HOLD(weak)→BUY (long bias)."
        )
    elif d_up == "EXIT":
        new_decision = "HOLD"
        new_bias = "Neutral"
        reason = (
            "TV-OVERRIDE: Strong uptrend (daily/intraday) + strong intraday "
            "volume — EXIT→HOLD (re-evaluate)."
        )
    else:
        # No supported mapping from this state
        return decision, bias, tv_ctx

    tv_ctx["TV_Override_Applied"] = True
    tv_ctx["TV_Override_Reason"] = reason
    tv_ctx["TV_Override_From"] = {"decision": old_decision, "bias": old_bias}
    tv_ctx["TV_Override_To"] = {"decision": new_decision, "bias": new_bias}

    try:
        log_trend_volume_override(
            symbol=indd.get("symbol"),
            interval=interval,
            mode=mode,
            original_decision=old_decision,
            original_bias=old_bias,
            new_decision=new_decision,
            new_bias=new_bias,
            trend_ctx=trend_ctx,
            vol_ctx=vol_ctx,
            reason=reason,
        )
    except Exception:
        # Override logging is best-effort; never break flow.
        pass

    return new_decision, new_bias, tv_ctx
