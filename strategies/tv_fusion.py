#!/usr/bin/env python3
# ============================================================
# queen/strategies/tv_fusion.py — v1.2 (Scalp Long, softer momentum)
# ------------------------------------------------------------
# Tactical View / Scalp fusion:
#   • Runs AFTER core action_for() has built `row`.
#   • Only for INTRADAY intervals (5m/15m/1h style).
#   • Can upgrade:
#         HOLD / WATCH  → BUY (Scalp Long)
#     when:
#         - Risk is acceptable
#         - Trend is not hostile
#         - Intraday momentum is strong enough
#
#   • Always writes a debug snapshot into `row["tv_debug"]`.
# ============================================================

from __future__ import annotations

from typing import Any, Dict


# ---------- tiny helpers ----------
def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    try:
        s = str(val)
        return default if s.strip() == "" else s
    except Exception:
        return default


def _is_intraday_interval(interval: str | int | None) -> bool:
    """Rudimentary intraday check: '5m', '15m', '30m', '1h', etc."""
    if interval is None:
        return False
    s = str(interval).lower().strip()
    if s.endswith("m"):
        return True
    if s.endswith("h"):
        return True
    # bare minutes like "5", "15"
    try:
        n = int(s)
        return n < 240  # treat < 4h as intraday
    except Exception:
        return False


def _trend_inputs(row: Dict[str, Any]) -> tuple[str, float]:
    bias = _safe_str(row.get("trend_bias") or row.get("Trend_Bias") or row.get("trend"), "")
    score_raw = row.get("trend_score") or row.get("Trend_Score")
    try:
        score = float(score_raw) if score_raw is not None else 0.0
    except Exception:
        score = 0.0
    return bias.lower(), score


def _momentum_inputs(row: Dict[str, Any]) -> Dict[str, Any]:
    # RSI: many possible keys; normalize to a single float
    rsi_raw = (
        row.get("rsi_intraday")
        or row.get("RSI_Intraday")
        or row.get("rsi_15m")
        or row.get("RSI_15m")
        or row.get("rsi")
        or row.get("RSI")
    )
    try:
        rsi = float(rsi_raw) if rsi_raw is not None else 0.0
    except Exception:
        rsi = 0.0

    vwap_zone = _safe_str(row.get("vwap_zone"), "").lower() or None

    drivers = row.get("drivers") or row.get("Drivers") or []
    if isinstance(drivers, str):
        drivers = [drivers]
    drivers_str = [str(d).upper() for d in drivers]
    has_bull = any(
        any(tag in d for tag in ("EMA↑", "EMA_UP", "RSI>60", "RSI>55", "MOM↑", "BREAKOUT"))
        for d in drivers_str
    )

    return {
        "rsi": rsi,
        "vwap_zone": vwap_zone,
        "has_bullish_driver": has_bull,
    }


def _risk_ok(row: Dict[str, Any]) -> bool:
    # Use daily ATR % or risk_rating as a coarse filter
    atr_pct_raw = row.get("daily_atr_pct") or row.get("Daily_ATR_Pct")
    try:
        atr_pct = float(atr_pct_raw) if atr_pct_raw is not None else 0.0
    except Exception:
        atr_pct = 0.0

    risk_rating = _safe_str(row.get("risk_rating") or row.get("Risk_Rating"), "").lower()

    # Generic sane default:
    #   - ATR% up to ~6–7% is fine for intraday scalps.
    #   - Block only if explicitly "Very High" AND ATR% huge.
    if atr_pct > 8.0 and "very high" in risk_rating:
        return False
    return True


def _trend_allows_scalp(row: Dict[str, Any]) -> bool:
    bias, score = _trend_inputs(row)
    # Hard block only if strongly bearish with decent score.
    if bias == "bearish" and score >= 6.0:
        return False
    # Otherwise even bearish-but-weak or range/bullish can be scalped.
    return True


def _intraday_momentum_ok(inputs: Dict[str, Any]) -> bool:
    """
    Softer intraday momentum rule (for scalp longs):

    Before:
      - Required high RSI + above VWAP etc.

    Now:
      - RSI >= 50.0
      - AND at least one bullish driver flag
      - VWAP zone is only used for diagnostics, not as a hard block.

    This is tuned specifically so VOLTAMP @ 12:00 / 12:15 with:
      rsi = 50, vwap_zone="below", has_bullish_driver=True
    will PASS momentum_ok, while noisy/no-driver setups still fail.
    """
    rsi = float(inputs.get("rsi") or 0.0)
    has_bull = bool(inputs.get("has_bullish_driver"))

    if not has_bull:
        return False

    # New softer floor for RSI
    return rsi >= 50.0


# ---------- main API ----------
def apply_tv_fusion(row: Dict[str, Any], *, interval: str | int | None) -> Dict[str, Any]:
    """
    Tactical View fusion / Scalp override.

    - Only runs for intraday intervals (5m/15m/1h).
    - Only upgrades HOLD/WATCH cores.
    - Never overrides hard AVOID or existing BUY.

    Side effects:
      - Always writes a `tv_debug` dict to the row.
      - May set:
          row["tv_override"] = True
          row["tv_reason"]   = "..."
          row["decision"]    = "BUY"
          row["bias"]        = "Scalp Long"
    """
    if row is None:
        return {}

    core_decision_raw = row.get("decision")
    trade_status_raw = row.get("trade_status")

    core_decision = _safe_str(core_decision_raw, "").upper()
    trade_status = _safe_str(trade_status_raw, "").upper()
    intraday = _is_intraday_interval(interval)

    # Precompute inputs for debug
    trend_bias, trend_score = _trend_inputs(row)
    moment_inputs = _momentum_inputs(row)
    risk_ok = _risk_ok(row) if intraday else False
    trend_ok = _trend_allows_scalp(row) if intraday else False
    momentum_ok = _intraday_momentum_ok(moment_inputs) if intraday else False

    # 🔍 ALWAYS export debug snapshot (even if we do nothing else)
    row["tv_debug"] = {
        "intraday": intraday,
        "interval": interval,
        "core_decision": core_decision,
        "trade_status": trade_status,
        "risk_ok": risk_ok,
        "trend_ok": trend_ok,
        "momentum_ok": momentum_ok,
        "rsi": moment_inputs["rsi"],
        "vwap_zone": moment_inputs["vwap_zone"],
        "has_bullish_driver": bool(moment_inputs["has_bullish_driver"]),
        "trend_bias": trend_bias,
        "trend_score": trend_score,
    }

    # Initialise flags if not present
    row.setdefault("tv_override", False)
    row.setdefault("tv_reason", None)

    # 0) Only intraday: never touch daily/weekly views
    if not intraday:
        return row

    # 1) Do NOT override if:
    #    - Already BUY
    #    - Explicit AVOID
    if core_decision in ("BUY", "EXIT"):
        return row
    if core_decision == "AVOID":
        return row

    # 2) Only consider "interested but cautious" states
    if core_decision not in ("HOLD", "WATCH", ""):
        return row

    # 3) Require all three gates
    if not (risk_ok and trend_ok and momentum_ok):
        return row

    # 4) Scalp Long override
    prev_decision = core_decision or "UNKNOWN"
    prev_bias = _safe_str(row.get("bias"), "Unknown")

    row["tv_override"] = True
    row["tv_reason"] = (
        "Scalp Long override: intraday HOLD/WATCH with acceptable risk and "
        f"momentum (prev_decision={prev_decision}, prev_bias={prev_bias})."
    )
    row["decision"] = "BUY"
    row["bias"] = "Scalp Long"

    return row
