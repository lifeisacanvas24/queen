#!/usr/bin/env python3
# ============================================================
# queen/strategies/fusion.py — v2.1 (patched)
# ------------------------------------------------------------
# Added:
#   • Guaranteed interval + time_bucket defaults
#   • Guaranteed action_tag + risk_mode defaults
#   • Safer fallbacks for overlays
#   • Fully DRY forward-compatible row enrichment
# ============================================================
from __future__ import annotations

from typing import Any, Dict, Optional

import polars as pl
from queen.helpers.logger import log  # make sure this import exists at top


# Optional: fusion weights / thresholds from settings
try:  # pragma: no cover - defensive import
    from queen.settings import weights as W
except Exception:  # pragma: no cover
    W = None

# Optional: playbook tagging
try:  # pragma: no cover
    from queen.strategies.playbook import assign_playbook
except Exception:  # pragma: no cover
    assign_playbook = None

# Optional: trend+volume override layer
try:  # pragma: no cover
    from queen.strategies.tv_fusion import apply_tv_fusion
except Exception:  # pragma: no cover
    apply_tv_fusion = None

# Optional: high-level decision overlay (action_tag / reason / risk_mode)
try:  # pragma: no cover
    from queen.strategies.decision_engine import apply_decision_overlays
except Exception:  # pragma: no cover
    apply_decision_overlays = None

# ------------------------------------------------------------
# Late-session soft exit configuration (risk-aware)
# ------------------------------------------------------------

LATE_EXIT_CONFIG = {
    # Very conservative: small pullback or VWAP slip → exit
    "LOW": {
        "pullback_pct": 0.50,                   # 0.50% from high
        "bad_vwap_zones": {"BELOW", "NEAR_BELOW"},
    },
    # Default behaviour
    "MEDIUM": {
        "pullback_pct": 0.80,                   # 0.80% from high
        "bad_vwap_zones": {"BELOW", "NEAR_BELOW"},
    },
    # Aggressive / risk-taker: allow deeper pullback
    "HIGH": {
        "pullback_pct": 1.20,                   # 1.20% from high
        "bad_vwap_zones": {"BELOW"},            # need clean break below VWAP
    },
}

_LATE_EXIT_DEFAULT = LATE_EXIT_CONFIG["MEDIUM"]

# ============================================================
# Section 1 — Multi-timeframe strategy fusion
# ============================================================
def _f_to_float(val):
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def _last_str(df: pl.DataFrame, col: str, default: str = "") -> str:
    if col not in df.columns or df.is_empty():
        return default
    try:
        v = df.get_column(col).cast(pl.Utf8).tail(1).item()
        return "" if v is None else str(v)
    except Exception:
        return default


def _regime_to_unit(reg: str) -> float:
    r = (reg or "").upper()
    if r == "TREND":
        return 1.0
    if r == "RANGE":
        return 0.55
    if r == "VOLATILE":
        return 0.45
    if r == "NEUTRAL":
        return 0.50
    return 0.50


def _risk_band(atr_ratio: float) -> str:
    if atr_ratio >= 1.40:
        return "high"
    if atr_ratio >= 1.15:
        return "medium"
    return "low"


def run_strategy(symbol: str, frames: Dict[str, pl.DataFrame], *, tf_weights=None) -> Dict[str, Any]:
    if not frames:
        return {
            "symbol": symbol,
            "per_tf": {},
            "fused": {
                "score": 0.0,
                "bias": "neutral",
                "entry_ok": False,
                "exit_ok": False,
                "risk_band": "low",
            },
        }

    per_tf: Dict[str, Dict[str, Any]] = {}
    for tf, df in frames.items():
        sps = max(0.0, min(1.0, _last_float(df, "SPS", 0.50)))
        regime_unit = _regime_to_unit(_last_str(df, "Regime_State", "NEUTRAL"))
        atr_r = _last_float(df, "ATR_Ratio", 1.00)
        atr_unit = max(0.0, min(1.0, atr_r / 1.25))

        score = max(
            0.0,
            min(1.0, round(0.55 * sps + 0.30 * regime_unit + 0.15 * atr_unit, 3)),
        )

        if W is not None and hasattr(W, "get_thresholds"):
            th = W.get_thresholds(tf)
            entry_thr = float(th.get("ENTRY", 0.70))
            exit_thr = float(th.get("EXIT", 0.30))
        else:
            entry_thr, exit_thr = 0.70, 0.30

        entry_ok = score >= entry_thr
        exit_ok = score <= exit_thr
        bias = (
            "bullish"
            if score >= (entry_thr - 0.04)
            else ("bearish" if score <= (exit_thr + 0.04) else "neutral")
        )

        per_tf[tf] = {
            "strategy_score": score,
            "bias": bias,
            "entry_ok": entry_ok,
            "exit_ok": exit_ok,
            "hold_reason": "regime carry" if (not entry_ok and not exit_ok) else "",
            "risk_band": _risk_band(atr_r),
        }

    if tf_weights is not None:
        weights = {tf: float(tf_weights.get(tf, 0.0)) for tf in frames}
    elif W is not None and hasattr(W, "fusion_weights_for"):
        weights = W.fusion_weights_for(list(frames.keys()))
    else:
        eq = 1.0 / max(1, len(frames))
        weights = {tf: eq for tf in frames}

    if W is not None and hasattr(W, "get_thresholds"):
        thr_list = [W.get_thresholds(tf) for tf in frames]
        entry_thr = max((float(t.get("ENTRY", 0.70)) for t in thr_list), default=0.70)
        exit_thr = min((float(t.get("EXIT", 0.30)) for t in thr_list), default=0.30)
    else:
        entry_thr, exit_thr = 0.70, 0.30

    fused_score = round(
        sum(per_tf[tf]["strategy_score"] * float(weights.get(tf, 0.0)) for tf in frames),
        3,
    )

    fused_bias = (
        "bullish"
        if fused_score >= (entry_thr - 0.04)
        else ("bearish" if fused_score <= (exit_thr + 0.04) else "neutral")
    )

    fused_entry = fused_score >= entry_thr
    fused_exit = fused_score <= exit_thr

    band_rank = {"low": 0, "medium": 1, "high": 2}
    fused_band = max((band_rank.get(per_tf[tf]["risk_band"], 0) for tf in frames), default=0)
    inv_rank = {v: k for k, v in band_rank.items()}

    return {
        "symbol": symbol,
        "per_tf": per_tf,
        "fused": {
            "score": fused_score,
            "bias": fused_bias,
            "entry_ok": fused_entry,
            "exit_ok": fused_exit,
            "risk_band": inv_rank.get(fused_band, "low"),
        },
    }

def _apply_late_session_soft_exit(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Late-session soft exit heuristic.

    Idea:
      • Only operate in LATE_SESSION.
      • Only on intraday playbooks (TREND / SCALP).
      • Use risk_mode to choose:
          - pullback threshold from session high
          - how strict VWAP zone needs to be
      • If conditions hit:
          -> decision = EXIT
          -> action_tag = EXIT
          -> action_reason explains why.
    """
    if not isinstance(row, dict):
        return row

    time_bucket = (row.get("time_bucket") or "UNKNOWN").upper()
    if time_bucket != "LATE_SESSION":
        return row

    playbook = (row.get("playbook") or "UNKNOWN").upper()
    if playbook not in {"INTRADAY_TREND", "INTRADAY_SCALP"}:
        return row

    # Existing exit should not be overridden
    decision = (row.get("decision") or "").upper()
    if decision in {"EXIT", "AVOID"}:
        return row

    risk_mode = (row.get("risk_mode") or "MEDIUM").upper()
    cfg = LATE_EXIT_CONFIG.get(risk_mode, _LATE_EXIT_DEFAULT)

    cmp_px = _f_to_float(row.get("cmp"))
    # Try a few likely high fields, fall back gracefully
    high_px = (
        _f_to_float(row.get("day_high"))
        or _f_to_float(row.get("session_high"))
        or _f_to_float(row.get("hh"))
    )
    vwap_zone = (row.get("vwap_zone") or "UNKNOWN").upper()

    pullback_pct = None
    if cmp_px is not None and high_px is not None and high_px > 0:
        try:
            pullback_pct = (high_px - cmp_px) / high_px * 100.0
        except Exception:
            pullback_pct = None

    # For introspection / cockpit debug if you want later
    if pullback_pct is not None:
        row["late_pullback_pct"] = pullback_pct

    vwap_bad = vwap_zone in cfg["bad_vwap_zones"]
    pullback_bad = (
        pullback_pct is not None and pullback_pct >= cfg["pullback_pct"]
    )

    # If neither condition is bad enough, leave row unchanged
    if not (vwap_bad or pullback_bad):
        return row

    # Mark EXIT
    row["decision"] = "EXIT"
    row["action_tag"] = "EXIT"

    reason_bits = []
    if vwap_bad:
        reason_bits.append(f"VWAP zone={vwap_zone}")
    if pullback_pct is not None:
        reason_bits.append(f"{pullback_pct:.2f}% from session high")

    base_reason = "Late-session soft exit: " + ", ".join(reason_bits)
    row["action_reason"] = base_reason

    return row
# ============================================================
# Section 2 — Unified row-level strategy hook
# ============================================================
from queen.helpers.logger import log  # make sure this import exists at top


def apply_strategies(
    row: Dict[str, Any],
    *,
    interval: str | None = None,
    phase: str | None = None,
    risk: str | None = None,
) -> Dict[str, Any]:
    """Unified row-level strategy hook.

    Order:
      1) Ensure basic context (interval, time_bucket).
      2) Playbook tagging.
      3) Trend+Volume fusion.
      4) High-level decision overlays.
      5) Fallback defaults (action_tag, risk_mode, reason).
      6) Late-session soft exit (final override).
      7) Normalise decision from action_tag.
    """
    if not isinstance(row, dict):
        return row

    # 1) Guarantee interval + time bucket exist
    row.setdefault("interval", interval or row.get("interval") or "UNKNOWN")
    row.setdefault("time_bucket", row.get("time_bucket") or phase or "UNKNOWN")

    # 2) Playbook tagging
    if assign_playbook is not None:
        try:
            row = assign_playbook(row)
        except Exception:
            row.setdefault("playbook", "UNKNOWN")
    else:
        row.setdefault("playbook", "UNKNOWN")

    # 3) Trend + Volume fusion (TV override)
    row.setdefault("tv_override", False)
    row.setdefault("tv_reason", None)

    if apply_tv_fusion is not None:
        try:
            row = apply_tv_fusion(row, interval=interval)
        except Exception:
            # if TV fusion fails, just ensure override flag is false
            row["tv_override"] = False

    # 4) High-level decision overlays (bias / regime / risk tweaks)
    if apply_decision_overlays is not None:
        try:
            row = apply_decision_overlays(
                row,
                phase=row.get("time_bucket") or phase,
                risk=risk,
                interval=interval,
            )
        except Exception:
            # if overlays fail, we fall back below
            pass

    # 5) Stronger fallbacks (ensure these keys always exist)
    row.setdefault("action_tag", row.get("decision") or "NO_ACTION")
    row.setdefault(
        "action_reason",
        row.get("action_reason") or "Strategy overlays unavailable.",
    )
    row.setdefault("risk_mode", row.get("risk_mode") or (risk or "MEDIUM"))

    # 6) Late-session soft exit as final override
    try:
        row = _apply_late_session_soft_exit(row)
    except Exception as e:
        log.exception(
            f"[fusion] late-session soft exit failed → {row.get('symbol')}: {e}"
        )

    # 7) FINAL NORMALISATION — align decision with action_tag
    decision = (row.get("decision") or "").upper()
    action_tag = (row.get("action_tag") or "").upper()

    # 7a) If strategy gave a BUY/ADD tag but left decision empty → promote it
    if not decision and action_tag in {"BUY", "ADD"}:
        row["decision"] = action_tag
        decision = action_tag

    # 7b) If strategy gave EXIT/FLATTEN but no decision → mark EXIT
    if not decision and action_tag in {"EXIT", "FLATTEN"}:
        row["decision"] = "EXIT"
        decision = "EXIT"

    # 7c) (Optional) WATCH → AVOID, if you ever want it
    # if not decision and action_tag == "WATCH":
    #     row["decision"] = "AVOID"
    #     decision = "AVOID"

    return row

# ============================================================
if __name__ == "__main__":
    sample = {
        "timestamp": "2025-11-28 09:45:00+05:30",
        "symbol": "VOLTAMP",
        "decision": "BUY",
        "bias": "Long",
        "trade_status": "WATCH",
        "notes": "Drivers: EMA↑ RSI≥55 OBV↑",
    }
    enriched = apply_strategies(sample.copy(), interval="15m")
    print("Sample enriched row:")
    for k in sorted(enriched.keys()):
        print(f"  {k}: {enriched[k]}")
