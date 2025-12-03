#!/usr/bin/env python3
# ============================================================
# queen/strategies/playbook.py — v2.0
# ------------------------------------------------------------
# Purpose:
#   • Attach a *playbook* label to a cockpit row.
#   • Playbook expresses the *style* and *timeframe* of trade:
#       - INTRADAY_TREND
#       - INTRADAY_SCALP
#       - CT_LONG (counter-trend long)
#       - BTST_LONG / SWING_LONG (skeletons for future)
#       - UNKNOWN (fallback)
#
#   • Uses:
#       - Core row fields: decision, bias, drivers, notes, timestamp.
#       - (Optional) PhaseState / RiskState from microstructure layer.
#
# Contract:
#   • assign_playbook(row, ...) → row (dict)  [non-breaking]
#   • Sets:
#       row["playbook"] : str
#       row["playbook_tags"] : List[str]   (optional semantic tags)
#       row["time_bucket"]   : str         (optional, for debugging)
#
# This file does NOT change scores or ladders.
# It only *describes* what type of trade the row represents.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------
# Dataclasses (internal usage)
# ------------------------------------------------------------
@dataclass
class PlaybookContext:
    """Internal classification result for a single cockpit row."""
    label: str = "UNKNOWN"          # e.g. "INTRADAY_TREND"
    timeframe: str = "INTRADAY"     # INTRADAY / SCALP / BTST / SWING / INVESTMENT
    style: str = "UNKNOWN"          # TREND / SCALP / CT / RANGE / REVERSAL / UNKNOWN
    confidence: float = 0.5         # 0.0–1.0 (rough heuristic)
    tags: List[str] = field(default_factory=list)
    time_bucket: str = "UNKNOWN"    # e.g. OPENING_DRIVE / MID_SESSION / LATE_SESSION


# ------------------------------------------------------------
# Time + interval helpers
# ------------------------------------------------------------
def _parse_timestamp(ts: Any) -> Optional[datetime]:
    """Best-effort conversion of timestamp into datetime.

    Accepts:
      • datetime objects (returned unchanged)
      • ISO-like strings (with or without timezone offset)
    Fails silently and returns None if parsing is impossible.
    """
    if isinstance(ts, datetime):
        return ts

    if ts is None:
        return None

    s = str(ts).strip()
    if not s:
        return None

    # Try basic fromisoformat; handle "+05:30" style offsets.
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass

    # Fallback: try trimming timezone portion if present.
    for sep in ["+", "Z"]:
        if sep in s:
            try:
                return datetime.fromisoformat(s.split(sep)[0])
            except Exception:
                continue

    return None


def _time_bucket_from_ts(ts: Any) -> str:
    """Rough time-of-day segmentation for intraday logic.

    Buckets:
      • OPENING_DRIVE : 09:15–10:30
      • MID_SESSION   : 10:30–13:30
      • LATE_SESSION  : 13:30–15:30
      • UNKNOWN       : anything else / parse error
    """
    dt = _parse_timestamp(ts)
    if dt is None:
        return "UNKNOWN"

    t = dt.time()
    if time(9, 15) <= t < time(10, 30):
        return "OPENING_DRIVE"
    if time(10, 30) <= t < time(13, 30):
        return "MID_SESSION"
    if time(13, 30) <= t <= time(15, 30):
        return "LATE_SESSION"
    return "UNKNOWN"


def _normalize_interval(interval: Optional[str]) -> str:
    """Normalize interval string into something like '15m', '5m', etc."""
    if interval is None:
        return "15m"

    s = str(interval).lower().strip()

    if s.endswith("m") or s.endswith("h") or s.endswith("d"):
        return s

    # If it's just a number, assume minutes.
    if s.isdigit():
        return f"{s}m"

    return s


def _timeframe_from_interval(interval: str) -> str:
    """Map raw interval to broader timeframe bucket."""
    if interval.endswith("m"):
        try:
            mins = int(interval[:-1])
        except Exception:
            mins = 15

        if mins <= 10:
            return "SCALP"
        if mins <= 30:
            return "INTRADAY"
        return "INTRADAY"

    if interval.endswith("h"):
        return "INTRADAY"

    # Future: daily/weekly mapping → SWING / POSITIONAL
    return "INTRADAY"


# ------------------------------------------------------------
# Driver helpers (read from row["drivers"] / row["notes"])
# ------------------------------------------------------------
def _get_drivers(row: Dict[str, Any]) -> List[str]:
    drivers = row.get("drivers") or []
    if isinstance(drivers, list):
        return [str(d) for d in drivers]
    # Some older rows may store as comma-separated string.
    if isinstance(drivers, str):
        return [d.strip() for d in drivers.split(",") if d.strip()]
    return []


def _has_driver(drivers: List[str], prefix: str) -> bool:
    """Case-insensitive prefix search in drivers."""
    p = prefix.lower()
    return any(str(d).lower().startswith(p) for d in drivers)


def _has_text(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()


# ------------------------------------------------------------
# Core classification logic
# ------------------------------------------------------------
def _classify_intraday_playbook(
    row: Dict[str, Any],
    *,
    interval: str,
) -> PlaybookContext:
    """Main rule set for INTRADAY / SCALP intraday trades.

    Uses:
      • decision, bias
      • drivers: EMA↑, EMA↓, RSI≥60, RSI≤45, VWAP>, VWAP<, OBV↑
      • timestamp (for time bucket)
    """
    ctx = PlaybookContext()
    ctx.timeframe = _timeframe_from_interval(interval)

    decision = (row.get("decision") or "").upper()
    bias = (row.get("bias") or "").lower()
    notes = str(row.get("notes") or "")
    drivers = _get_drivers(row)
    ts = row.get("timestamp")

    ctx.time_bucket = _time_bucket_from_ts(ts)

    is_buy = decision in {"BUY", "ADD", "BUY / ADD", "STRONG_BUY"}
    is_hold = decision == "HOLD"
    is_avoid = decision == "AVOID"

    has_ema_up = _has_driver(drivers, "EMA↑") or _has_text(notes, "EMA↑")
    has_ema_down = _has_driver(drivers, "EMA↓") or _has_text(notes, "EMA↓")
    has_rsi_ge_60 = _has_driver(drivers, "RSI≥6") or _has_text(notes, "RSI≥60")
    has_rsi_ge_55 = (
        _has_driver(drivers, "RSI≥55")
        or _has_text(notes, "RSI≥55")
        or has_rsi_ge_60
    )
    has_rsi_le_45 = _has_driver(drivers, "RSI≤45") or _has_text(notes, "RSI≤45")
    vwap_above = (
        _has_driver(drivers, "VWAP>")
        or _has_text(notes, "VWAP>")
        or _has_text(notes, "VWAP above")
    )
    vwap_below = (
        _has_driver(drivers, "VWAP<")
        or _has_text(notes, "VWAP<")
        or _has_text(notes, "VWAP below")
    )
    obv_up = _has_driver(drivers, "OBV↑") or _has_text(notes, "OBV↑")

    # --- Rule 0: No trade / neutral rows ---
    if decision in {None, "", "NULL"} or decision == "WATCH":
        ctx.label = "UNKNOWN"
        ctx.style = "UNKNOWN"
        ctx.confidence = 0.3
        return ctx

    # --- Rule 1: Clear intraday trend long (your base religion) ---
    # Conditions:
    #   • BUY decision
    #   • EMA↑
    #   • RSI≥60 (or equivalent strong)
    #   • price above VWAP (context: strength)
    if is_buy and has_ema_up and has_rsi_ge_60 and vwap_above:
        ctx.label = "INTRADAY_TREND"
        ctx.style = "TREND"
        ctx.confidence = 0.9
        ctx.tags.extend(
            [
                "INTRADAY",
                "TREND_FOLLOW",
                "MOMENTUM_LONG",
                "ABOVE_VWAP",
                "STRONG_MOMENTUM",
            ]
        )
        if ctx.time_bucket == "OPENING_DRIVE":
            ctx.tags.append("OPENING_DRIVE_TREND")
        return ctx

    # --- Rule 2: Intraday scalp breakout / continuation ---
    # VOLTAMP-type scenario, but when the engine *does* give you a BUY:
    #   • BUY decision
    #   • EMA↑
    #   • RSI in 55–60 zone (strong but not extended)
    #   • above VWAP OR OBV↑ (volume confirmation)
    if is_buy and has_ema_up and has_rsi_ge_55 and (vwap_above or obv_up):
        ctx.label = "INTRADAY_SCALP"
        ctx.style = "SCALP"
        ctx.confidence = 0.8
        ctx.tags.extend(
            [
                "INTRADAY",
                "SCALP",
                "SCALP_BREAKOUT",
                "MOMENTUM_LONG",
            ]
        )
        if ctx.time_bucket == "OPENING_DRIVE":
            ctx.tags.append("OPENING_SCALP")
        return ctx

    # --- Rule 3: Counter-trend long (buying into weakness) ---
    # E.g.:
    #   • BUY decision
    #   • RSI≤45 (pullback / weakness)
    #   • EMA↑ or neutral (higher timeframe still supportive)
    if is_buy and has_rsi_le_45 and not has_ema_down:
        ctx.label = "CT_LONG"
        ctx.style = "CT"
        ctx.confidence = 0.7
        ctx.tags.extend(
            [
                "INTRADAY",
                "COUNTER_TREND",
                "DIP_BUY",
            ]
        )
        return ctx

    # --- Rule 4: Range / mean-reversion trades (future expansion) ---
    # For now, we just tag as RANGE if:
    #   • HOLD or AVOID
    #   • RSI in middle band (45–55)
    if (is_hold or is_avoid) and not (has_rsi_ge_60 or has_rsi_le_45):
        ctx.label = "INTRADAY_RANGE"
        ctx.style = "RANGE"
        ctx.confidence = 0.6
        ctx.tags.extend(
            [
                "INTRADAY",
                "RANGE_TRADE",
            ]
        )
        return ctx

    # --- Fallbacks ---
    # If BUY but not matching any strong pattern, keep it intraday_misc.
    if is_buy:
        ctx.label = "INTRADAY_MISC"
        ctx.style = "TREND" if has_ema_up else "UNKNOWN"
        ctx.confidence = 0.6
        ctx.tags.append("INTRADAY")
        return ctx

    # For everything else, mark unknown but tagged as intraday.
    ctx.label = "UNKNOWN"
    ctx.style = "UNKNOWN"
    ctx.confidence = 0.4
    ctx.tags.append("INTRADAY")
    return ctx


def _classify_btst_swing_playbook(
    row: Dict[str, Any],
    *,
    horizon: Optional[str] = None,
) -> PlaybookContext:
    """Skeleton for BTST / SWING classification (future extension).

    Right now, we mostly operate on intraday, so this returns UNKNOWN
    but keeps the structure ready.
    """
    ctx = PlaybookContext()
    decision = (row.get("decision") or "").upper()
    bias = (row.get("bias") or "").lower()

    # Try to infer horizon from row if present
    h = (horizon or row.get("horizon") or "").upper()

    if "BTST" in h:
        ctx.timeframe = "BTST"
    elif "SWING" in h:
        ctx.timeframe = "SWING"
    else:
        ctx.timeframe = "SWING"

    # Simple placeholders:
    if decision in {"BUY", "ADD"} and "long" in bias:
        ctx.label = f"{ctx.timeframe}_LONG"
        ctx.style = "TREND"
        ctx.confidence = 0.6
        ctx.tags.extend([ctx.timeframe, "TREND_FOLLOW"])
        return ctx

    ctx.label = "UNKNOWN"
    ctx.style = "UNKNOWN"
    ctx.confidence = 0.4
    ctx.tags.append(ctx.timeframe)
    return ctx


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------
def assign_playbook(
    row: Dict[str, Any],
    *,
    phase: Any = None,         # reserved for PhaseState (future wiring)
    risk: Any = None,          # reserved for RiskState
    interval: Optional[str] = None,
    horizon: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach a playbook label + tags to a cockpit row.

    Parameters
    ----------
    row : dict
        Cockpit row from scoring engine / actionable replay.
        Expected keys (best-effort usage):
          • "decision"      : BUY / ADD / HOLD / AVOID / EXIT / ...
          • "bias"          : Long / Weak / Counter-trend Long / ...
          • "drivers"       : List[str] — e.g. ["EMA↑", "RSI≥60", "VWAP>"]
          • "notes"         : str
          • "timestamp"     : str or datetime (for time bucket)

    phase : PhaseState (optional, currently unused)
        Reserved for when fusion layer passes microstructure PhaseState.
        In future we may refine playbook using phase.label such as:
          • "BREAKOUT_BASE"
          • "BREAKOUT_CONFIRMED"
          • "POST_BREAKOUT_FADE"
          • "RANGE_COMPRESSION"
          etc.

    risk : RiskState (optional, currently unused)
        Reserved for risk-aware playbook decisions (high-vol regime etc.).

    interval : str (optional)
        Intraday interval like "5m", "15m", or 15. If omitted, defaults to "15m".

    horizon : str (optional)
        High-level horizon hint like "INTRADAY", "BTST", "SWING".
        If omitted, inferred from interval.

    Returns
    -------
    row : dict
        Same dict with:
          • row["playbook"]       : str
          • row["playbook_tags"]  : List[str]
          • row["time_bucket"]    : str (for intraday rows)
    """
    if not isinstance(row, dict):
        # Be defensive: if something strange comes in, don't blow up.
        return row

    interval_norm = _normalize_interval(interval)
    timeframe = _timeframe_from_interval(interval_norm)

    # Decide which classifier to use based on timeframe/horizon.
    if horizon:
        horizon_upper = horizon.upper()
        if "BTST" in horizon_upper or "SWING" in horizon_upper:
            ctx = _classify_btst_swing_playbook(row, horizon=horizon)
        else:
            ctx = _classify_intraday_playbook(row, interval=interval_norm)
    else:
        # Default path: intraday-centric system.
        if timeframe in {"SCALP", "INTRADAY"}:
            ctx = _classify_intraday_playbook(row, interval=interval_norm)
        else:
            ctx = _classify_btst_swing_playbook(row, horizon=horizon)

    # Merge into row
    row["playbook"] = ctx.label
    row["playbook_tags"] = sorted(set((row.get("playbook_tags") or []) + ctx.tags))
    row["time_bucket"] = ctx.time_bucket

    return row


# ------------------------------------------------------------
# Example usage (for your reference only)
# ------------------------------------------------------------
if __name__ == "__main__":
    # 360ONE / HAL-type strong intraday trend BUY
    example_row_trend = {
        "timestamp": "2025-11-28 13:00:00+05:30",
        "symbol": "360ONE",
        "decision": "BUY",
        "bias": "Long",
        "drivers": ["EMA↑", "RSI≥60", "VWAP> EMA50>", "OBV↑"],
        "notes": "Drivers: EMA↑ RSI≥60 VWAP> EMA50>",
        "cmp": 100.0,
    }
    print("TREND EXAMPLE →", assign_playbook(example_row_trend, interval="15m"))

    # Hypothetical scalp-style BUY (RSI 55–60, good volume)
    example_row_scalp = {
        "timestamp": "2025-11-28 09:45:00+05:30",
        "symbol": "VOLTAMP",
        "decision": "BUY",
        "bias": "Long",
        "drivers": ["EMA↑", "RSI≥55", "VWAP>", "OBV↑"],
        "notes": "Drivers: EMA↑ RSI≥55 OBV↑ VWAP>",
        "cmp": 8250.0,
    }
    print("SCALP EXAMPLE →", assign_playbook(example_row_scalp, interval="5m"))
