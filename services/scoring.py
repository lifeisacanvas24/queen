#!/usr/bin/env python3
# ============================================================
# queen/services/scoring.py — v2.0
# Actionable scoring + early-signal fusion (registry-first, fallback-safe)
# ============================================================
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import polars as pl

from queen.fetchers.nse_fetcher import fetch_nse_bands, get_cached_nse_bands
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


def _ema_last(df: pl.DataFrame, period: int, column: str = "close") -> Optional[float]:
    try:
        return _last(ind.ema(df, period, column))
    except Exception:
        return None


# --------------- indicators snapshot -----------------
def compute_indicators(df: pl.DataFrame) -> Optional[Dict[str, float | str]]:
    if df.is_empty() or df.height < 12:
        return None

    rsi_val = ind.rsi_last(df["close"].cast(pl.Float64, strict=False), 14)
    atr_val = ind.atr_last(df, 14)
    vwap_val = ind.vwap_last(df)
    cpr_val = ind.cpr_from_prev_day(df)
    obv_tr = ind.obv_trend(df)
    ema20 = _ema_last(df, 20)
    ema50 = _ema_last(df, 50)
    ema200 = _ema_last(df, 200)
    close_last = float(df["close"].tail(1).item())

    ema_bias = "Neutral"
    if all(x is not None for x in (ema20, ema50, ema200)):
        if ema20 > ema50 > ema200:
            ema_bias = "Bullish"
        elif ema20 < ema50 < ema200:
            ema_bias = "Bearish"

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

try:
    from queen.technicals.signals.tactical.reversal_stack import (
        evaluate as _reversal_stack_eval,
    )
except Exception:
    _reversal_stack_eval = None  # type: ignore


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


def _fallback_early(df: pl.DataFrame, cmp_: float, vwap_: Optional[float]) -> Tuple[int, List[str]]:
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
            if rsi_prev is not None and rsi_now is not None and rsi_prev < 50 <= rsi_now:
                s += 1
                cues.append("RSI→50↑")
    except Exception:
        pass

    # Very near VWAP (potential reclaim)
    if vwap_ is not None and abs(cmp_ - vwap_) / max(1.0, vwap_) <= 0.003:
        s += 1
        cues.append("Near VWAP")

    return min(s, 3), cues


def _early_bundle(df: pl.DataFrame, cmp_: float, vwap_: Optional[float]) -> Tuple[int, List[str]]:
    """Fuse registry signals; fallback if none. Max registry contribution = 6."""
    total = 0
    reasons: List[str] = []

    if _pre_breakout_eval:
        p = _normalize_signal(_pre_breakout_eval(df), "PreBreakout")
        total += p[0]
        reasons += p[1]

    if _squeeze_pulse_eval:
        s = _normalize_signal(_squeeze_pulse_eval(df), "Squeeze")
        total += s[0]
        reasons += s[1]

    if _reversal_stack_eval:
        r = _normalize_signal(_reversal_stack_eval(df), "ReversalStack")
        total += r[0]
        reasons += r[1]

    total = min(total, 6)

    if total == 0:
        fb, fb_r = _fallback_early(df, cmp_, vwap_)
        total += fb
        reasons += fb_r

    return total, reasons


# --------------- base tactical score -----------------
def score_symbol(indd: Dict[str, float | str]) -> Tuple[float, List[str]]:
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
    """Return (SL, [T1, T2, T3]) strings."""
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
    # use a strength trigger (max of supports) plus a small buffer
    base = max(x for x in [cmp_, vwap, ema20, cpr] if x is not None)
    buffer = max((atr or 0) * 0.10, cmp_ * 0.0025)  # 0.1×ATR or 0.25%
    return round(base + buffer, 1)


# --------------- main action function -----------------
def action_for(
    symbol: str,
    indd: Dict[str, float | str],
    book: str = "all",
    use_uc_lc: bool = True,
) -> Dict[str, object]:
    """Expects `indd` to optionally include `_df` (pl.DataFrame) for early signals.
    """
    cmp_ = float(indd["CMP"])
    atr = indd.get("ATR")
    vwap = indd.get("VWAP")
    cpr = indd.get("CPR")
    ema20 = indd.get("EMA20")

    base_score, drivers = score_symbol(indd)

    # Early signals (registry-first) if we have DF
    df_ctx: Optional[pl.DataFrame] = indd.get("_df") if isinstance(indd.get("_df"), pl.DataFrame) else None
    early_score, early_reasons = (0, [])
    if df_ctx is not None and df_ctx.height >= 30:
        early_score, early_reasons = _early_bundle(df_ctx, cmp_, vwap)

    total_score = min(10, int(round(base_score + early_score)))

    # Position-aware logic
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

    # Targets & SL
    if held:
        base = float(pos.get("avg_price") or cmp_)
        entry = round(base, 1)
        sl, targets = _ladder_from_base(base, atr)
    else:
        entry = _non_position_entry(cmp_, vwap, ema20, cpr, atr)
        sl, targets = _ladder_from_base(entry, atr)

    # UCLC notes
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

    # Context labels
    vwap_zone = (
        "Above" if (vwap is not None and cmp_ > vwap) else
        "Below" if (vwap is not None and cmp_ < vwap) else
        "Neutral"
    )
    cpr_ctx = (
        "Above CPR" if (cpr is not None and cmp_ > cpr) else
        "Below CPR" if (cpr is not None and cmp_ < cpr) else
        "At/Unknown"
    )

    if early_reasons:
        notes.insert(0, "EARLY: " + ", ".join(early_reasons))
    if drivers:
        notes.append("Drivers: " + " ".join(drivers))

    row: Dict[str, object] = {
        "symbol": symbol,
        "cmp": round(cmp_, 1),
        "score": int(total_score),
        "early": int(early_score),  # <-- expose early score (0–6)
        "decision": decision,
        "bias": bias,
        "drivers": drivers,
        "entry": round(entry, 1),
        "sl": sl,
        "targets": targets,
        "vwap_zone": vwap_zone,
        "cpr_ctx": cpr_ctx,
        "atr": atr,
        "obv": indd.get("OBV"),
        "ema_bias": indd.get("EMA_BIAS"),
        "ema50": indd.get("EMA50"),
        "cpr": cpr,
        "held": held,
        "advice": (
            "ADD 10–15% on strength; trail to VWAP" if (held and decision == "ADD")
            else "HOLD; trail SL to EMA20/VWAP" if held
            else "Starter on strength; respect SL" if decision == "BUY"
            else "Wait for confirmation; keep on watch" if decision == "HOLD"
            else "Avoid for now"
        ),
        "notes": " | ".join(notes) if notes else "—",
        "position": pos or {},
    }

    pnl = compute_pnl(cmp_, pos) if pos else None
    if pnl:
        row["pnl_abs"] = round(pnl[0], 2)
        row["pnl_pct"] = round(pnl[1], 2)
    return row
