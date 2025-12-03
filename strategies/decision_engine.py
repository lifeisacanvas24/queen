#!/usr/bin/env python3
# ============================================================
# queen/strategies/decision_engine.py — v1.2
# ------------------------------------------------------------
# Purpose:
#   • Take a *base* cockpit row (from scoring/action_for) and
#     enrich it with a higher-level "action intent":
#
#       - action_tag:
#           STRONG_BUY / BUY / HOLD / AVOID / EXIT / BOOK_PARTIAL /
#           TRAIL_STOP / WATCH / SCALP_CANDIDATE_LONG / ...
#
#       - action_reason:
#           Short human-readable explanation.
#
#       - risk_mode:
#           LOW / MEDIUM / HIGH (if RiskState is available).
#
#   • This layer DOES NOT:
#       - change your underlying scores,
#       - modify ladders,
#       - disturb your existing decision logic.
#
#   • It only *interprets*:
#       decision + playbook + phase + pnl + time-of-day + risk
#     into something closer to the "trader language" you use.
#
# Integration:
#   • Called AFTER:
#       - scoring.action_for()
#       - microstructure phases/risk (optional)
#       - playbook.assign_playbook()
#
#   • Contract:
#       apply_decision_overlays(row, phase=..., risk=..., interval=...) → row
#
#   • Safe to skip:
#       If you never call this, nothing breaks.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, Optional, Tuple


# ------------------------------------------------------------
# Helpers to read PhaseState / RiskState in a tolerant way
# ------------------------------------------------------------
@dataclass
class PhaseView:
    """Lightweight view over PhaseState (or dict-like) to avoid tight coupling."""
    label: str = "UNKNOWN"       # e.g. "BREAKOUT_SETUP", "BREAKOUT_CONFIRMED"
    stage: str = ""              # optional finer-grain descriptor
    bias: str = ""               # "bullish" / "bearish" / "range" / ...
    risk_hint: str = ""          # "low" / "medium" / "high" / ""
    notes: str = ""              # free-form text


@dataclass
class RiskView:
    """Lightweight view over RiskState (or dict-like)."""
    mode: str = "MEDIUM"         # LOW / MEDIUM / HIGH
    reason: str = ""             # optional explanation


def _parse_timestamp(ts: Any) -> Optional[datetime]:
    """Best-effort conversion of timestamp into datetime."""
    if isinstance(ts, datetime):
        return ts

    if ts is None:
        return None

    s = str(ts).strip()
    if not s:
        return None

    # Try ISO format with offset.
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass

    # Fallback: trim common timezone suffixes.
    for sep in ["+", "Z"]:
        if sep in s:
            try:
                return datetime.fromisoformat(s.split(sep)[0])
            except Exception:
                continue

    return None


def _time_bucket_from_ts(ts: Any) -> str:
    """Rough time-of-day segmentation.

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


def _view_phase(phase: Any) -> PhaseView:
    """Convert PhaseState or dict-like to PhaseView safely."""
    if phase is None:
        return PhaseView()

    # dataclass / object with attributes
    for attr in ("label", "stage", "bias", "risk_hint", "notes"):
        if not hasattr(phase, attr):
            break
    else:
        # All attributes exist → assume compatible dataclass
        return PhaseView(
            label=getattr(phase, "label", "UNKNOWN") or "UNKNOWN",
            stage=getattr(phase, "stage", "") or "",
            bias=getattr(phase, "bias", "") or "",
            risk_hint=getattr(phase, "risk_hint", "") or "",
            notes=getattr(phase, "notes", "") or "",
        )

    # dict-like
    if isinstance(phase, dict):
        return PhaseView(
            label=str(phase.get("label", "UNKNOWN") or "UNKNOWN"),
            stage=str(phase.get("stage", "") or ""),
            bias=str(phase.get("bias", "") or ""),
            risk_hint=str(phase.get("risk_hint", "") or ""),
            notes=str(phase.get("notes", "") or ""),
        )

    # Fallback
    return PhaseView(label=str(phase))


def _view_risk(risk: Any) -> RiskView:
    """Convert RiskState or dict-like to RiskView safely."""
    if risk is None:
        return RiskView()

    # object with attributes
    if hasattr(risk, "mode") or hasattr(risk, "regime"):
        mode = getattr(risk, "mode", None) or getattr(risk, "regime", "MEDIUM")
        reason = getattr(risk, "reason", "") or getattr(risk, "notes", "") or ""
        return RiskView(mode=str(mode).upper(), reason=str(reason))

    # dict-like
    if isinstance(risk, dict):
        mode = risk.get("mode") or risk.get("regime") or "MEDIUM"
        reason = risk.get("reason") or risk.get("notes") or ""
        return RiskView(mode=str(mode).upper(), reason=str(reason))

    return RiskView(mode=str(risk).upper())


def _normalize_decision(row: Dict[str, Any]) -> str:
    d = (row.get("decision") or "").strip().upper()
    # Normalise a few variants.
    if d in {"BUY / ADD", "ADD_MORE"}:
        return "ADD"
    if d in {"EXIT_ALL", "CLOSE"}:
        return "EXIT"
    return d


def _pnl_pct_from_row(row: Dict[str, Any]) -> Optional[float]:
    """Best-effort extraction of position PnL% from row."""
    pos = row.get("position") or {}
    if isinstance(pos, dict) and "pnl_pct" in pos:
        try:
            return float(pos["pnl_pct"])
        except Exception:
            return None
    return None


# ------------------------------------------------------------
# Core decision overlay logic (base layer)
# ------------------------------------------------------------
def _choose_action_tag(
    row: Dict[str, Any],
    *,
    phase_view: PhaseView,
    risk_view: RiskView,
) -> Tuple[str, str]:
    """Map base decision + playbook + pnl + phase/risk → (action_tag, reason)."""

    decision = _normalize_decision(row)
    bias = (row.get("bias") or "").lower()
    playbook = (row.get("playbook") or "UNKNOWN").upper()
    trade_status = (row.get("trade_status") or "").upper()

    time_bucket = row.get("time_bucket") or _time_bucket_from_ts(row.get("timestamp"))
    pnl_pct = _pnl_pct_from_row(row)
    has_position = pnl_pct is not None

    # Default fallback
    action_tag = "NO_ACTION"
    reason = "No specific action derived; base decision only."

    # ------------------------------
    # 1) Hard exits / strong avoid
    # ------------------------------
    if decision in {"EXIT", "SELL"} or trade_status in {"EXIT", "CLOSED"}:
        return "EXIT", "Base engine indicates exit."

    if decision == "AVOID":
        # If phase explicitly says breakdown / failed breakout, emphasize risk-off.
        if "BREAKDOWN" in phase_view.label.upper() or "FAIL" in phase_view.label.upper():
            return "STRONG_AVOID", "Phase indicates breakdown / failure; stand aside."
        return "AVOID", "Setup not qualified; risk > reward."

    # ------------------------------
    # 2) Strong buys (your base religion, time-weighted)
    # ------------------------------
    # Intraday trend buys with aligned phase and not-high risk.
    if decision in {"BUY", "ADD"} and playbook == "INTRADAY_TREND":
        if risk_view.mode == "HIGH":
            return (
                "BUY",
                "Trend-long setup, but high-risk regime; position sizing should be conservative.",
            )

        # Opening drive trend → strongest conviction (both fresh entry & adds).
        if time_bucket == "OPENING_DRIVE":
            return (
                "STRONG_BUY",
                "Opening-drive intraday trend long with aligned structure; highest conviction window.",
            )

        # Mid-session → normal BUY, but still trend-aligned.
        if time_bucket == "MID_SESSION":
            if has_position:
                return (
                    "BUY",
                    "Intraday trend-long continuation during mid-session; maintain or add with measured size.",
                )
            else:
                return (
                    "BUY",
                    "Intraday trend-long entry during mid-session; conviction is moderate, manage risk tightly.",
                )

        # Late session → cautious on *fresh* entries, okay for adds/holds.
        if time_bucket == "LATE_SESSION":
            if has_position:
                return (
                    "BUY",
                    "Late-session trend-long continuation; acceptable for managing existing position, avoid aggressive fresh entries.",
                )
            else:
                return (
                    "WATCH",
                    "Late-session trend-long signal; better treated as watch/scalp than fresh core entry.",
                )

        # Fallback (UNKNOWN or odd buckets)
        return "BUY", "Intraday trend-following long setup (time-of-day neutral)."

    # ------------------------------
    # 3) Scalp & counter-trend longs (time-weighted)
    # ------------------------------
    if decision in {"BUY", "ADD"} and playbook in {"INTRADAY_SCALP", "CT_LONG"}:
        if risk_view.mode == "HIGH":
            return (
                "SCALP_LIGHT",
                "Scalp / counter-trend buy in high-risk regime; keep size light and stops tight.",
            )

        # Opening drive → this is where scalp breakouts shine.
        if time_bucket == "OPENING_DRIVE":
            return (
                "SCALP_BREAKOUT",
                "Opening-drive scalp breakout; fast move expected with tight risk and quick management.",
            )

        # Mid-session → tactical-only, clearly labelled.
        if time_bucket == "MID_SESSION":
            if has_position:
                return (
                    "BUY",
                    "Mid-session scalp / counter-trend management; treat as tactical continuation, not core trend.",
                )
            else:
                return (
                    "BUY",
                    "Mid-session scalp / counter-trend entry; tactical only, keep risk & size controlled.",
                )

        # Late session → avoid fresh counter-trend scalps.
        if time_bucket == "LATE_SESSION":
            if has_position:
                return (
                    "TRAIL_STOP",
                    "Late-session scalp / counter-trend position; focus on protecting gains with tight trailing stops.",
                )
            else:
                return (
                    "WATCH",
                    "Late-session scalp / counter-trend signal; avoid initiating fresh trades this late.",
                )

        # Fallback
        return "BUY", "Scalp / counter-trend long; treat as tactical trade, not core trend."

    # ------------------------------
    # 4) Holding / trailing logic
    # ------------------------------
    if decision == "HOLD":
        # If position PnL is healthy, suggest trailing rather than flat HOLD.
        if pnl_pct is not None and pnl_pct >= 1.0:
            # Mid / late session + good PnL → trail or partial book
            if time_bucket in {"MID_SESSION", "LATE_SESSION"}:
                # If phase is post-breakout / exhaustion, book partial.
                if "POST" in phase_view.label.upper() or "EXHAUST" in phase_view.label.upper():
                    return (
                        "BOOK_PARTIAL",
                        f"Decent profit ({pnl_pct:.1f}%) in post-breakout phase; book partial and trail rest.",
                    )
                return (
                    "TRAIL_STOP",
                    f"Decent profit ({pnl_pct:.1f}%) with continuing structure; trail stop to protect gains.",
                )

            # Early profits in opening drive
            if time_bucket == "OPENING_DRIVE":
                return (
                    "HOLD",
                    f"Opening-drive winner ({pnl_pct:.1f}%), structure still valid; continue to hold with vigilance.",
                )

        # No position or flat PnL → true neutral hold.
        if pnl_pct is None or abs(pnl_pct) < 0.5:
            return "HOLD", "Neutral hold; no strong directional pressures."

        # Slight loss but hold decision → tolerance zone.
        if pnl_pct < -1.0:
            return (
                "WATCH",
                f"Underwater (~{pnl_pct:.1f}%) but engine suggests hold; monitor closely for breakdown.",
            )

        return "HOLD", "Default hold; no override."

    # ------------------------------
    # 5) Watch / neutral situations
    # ------------------------------
    if decision in {"WATCH", "WAIT", ""}:
        if risk_view.mode == "HIGH":
            return "RISK_OFF", "High-risk regime; safer to stay out."
        if "BREAKOUT_SETUP" in phase_view.label.upper():
            return "WATCH", "Potential breakout setup; watch for confirmation, avoid pre-emptive entries."
        return "WATCH", "No actionable edge yet; stay patient."

    # ------------------------------
    # 6) Fallbacks
    # ------------------------------
    # Any BUY-like decision we didn't classify above.
    if decision in {"BUY", "ADD"}:
        if risk_view.mode == "HIGH":
            return "BUY", "Buy signal in high-risk regime; confirm with intraday tape before acting."
        return "BUY", "Buy decision from engine; no additional overlays applied."

    # Everything else: shadow base decision.
    if decision:
        return decision, f"Base decision={decision}; overlays neutral."

    return action_tag, reason

def _phase_override_action(
    row: Dict[str, Any],
    phase_view: PhaseView,
    risk_view: RiskView,
    base_action_tag: str,
    base_action_reason: str,
) -> Tuple[str, str]:
    """
    Phase-driven refinement layer.

    It does NOT fight:
      • Hard exits (EXIT / SELL / STOP_LOSS_HIT)
      • TV overrides (handled earlier in fusion layer)
      • Explicit STRONG_AVOID / RISK_OFF decisions

    It only nudges the action_tag when phase structure is very clear:
      • BREAKOUT_SETUP       → stronger WATCH (pre-emptive but flat)
      • BREAKOUT_CONFIRMED   → upgrade BUY to BREAKOUT_BUY (trend / btst)
      • POST_BREAKOUT_FADE   → encourage BOOK_PARTIAL / TRAIL_STOP
      • BREAKDOWN_CONFIRMED  → STRONG_AVOID / RISK_OFF style
    """
    if not isinstance(row, dict):
        return base_action_tag, base_action_reason

    label = (phase_view.label or "").upper()
    if not label or label == "UNKNOWN":
        return base_action_tag, base_action_reason

    decision = _normalize_decision(row)
    playbook = (row.get("playbook") or "UNKNOWN").upper()
    time_bucket = row.get("time_bucket") or _time_bucket_from_ts(row.get("timestamp"))
    pnl_pct = _pnl_pct_from_row(row)
    has_position = pnl_pct is not None
    risk_mode = (risk_view.mode or "MEDIUM").upper()

    # 0) Never fight hard exits / risk-off style actions
    hard_out_tags = {
        "EXIT",
        "STOP_LOSS_HIT",
        "RISK_OFF",
        "STRONG_AVOID",
    }
    if base_action_tag in hard_out_tags:
        return base_action_tag, base_action_reason

    # 1) Clear breakdown → STRONG_AVOID / RISK_OFF flavour
    if "BREAKDOWN" in label or "FAIL" in label:
        # If engine was still mild (HOLD/WATCH/BUY), lean risk-off.
        if risk_mode == "HIGH":
            return "RISK_OFF", "Phase shows breakdown in high-risk regime; safest is to stay flat."
        return "STRONG_AVOID", "Phase shows breakdown / failure; stand aside and avoid fresh longs."

    # 2) Pre-breakout setup → stronger WATCH (not pre-emptive BUY)
    if "BREAKOUT_SETUP" in label:
        # Only upgrade if engine was indecisive.
        if base_action_tag in {"NO_ACTION", "HOLD", "WATCH", "WAIT"}:
            return "WATCH", "Phase indicates breakout setup; watch closely for confirmation, avoid pre-emptive entry."
        return base_action_tag, base_action_reason

    # 3) Breakout confirmed → upgrade intraday/swing BUY → BREAKOUT_BUY
    if "BREAKOUT_CONFIRMED" in label:
        if decision in {"BUY", "ADD"} and base_action_tag in {"BUY", "STRONG_BUY"}:
            # Only for trend / momentum style playbooks
            if any(key in playbook for key in ("INTRADAY_TREND", "BTST", "SWING")):
                # Opening drive or mid-session → high conviction breakout buy
                if time_bucket in {"OPENING_DRIVE", "MID_SESSION"}:
                    return "BREAKOUT_BUY", "Breakout confirmed with trend-aligned structure; treat as breakout buy."
        return base_action_tag, base_action_reason

    # 4) Post-breakout fade / exhaustion → BOOK_PARTIAL / TRAIL_STOP
    if "POST" in label or "EXHAUST" in label or "FADE" in label:
        if has_position and pnl_pct is not None and pnl_pct >= 1.0:
            # Protect gains depending on risk + time bucket
            if time_bucket in {"MID_SESSION", "LATE_SESSION"}:
                return (
                    "BOOK_PARTIAL",
                    f"Phase indicates post-breakout fade / exhaustion with profit (~{pnl_pct:.1f}%); book partial and tighten stops.",
                )
            else:
                return (
                    "TRAIL_STOP",
                    f"Phase indicates post-breakout behaviour with profit (~{pnl_pct:.1f}%); trail stop to lock in gains.",
                )
        return base_action_tag, base_action_reason

    # 5) Range / basing / pullback hints → keep base tag, no aggression
    if any(k in label for k in ("RANGE", "CONSOLIDATION", "PULLBACK", "BASING")):
        # Here we mainly avoid up-scaling aggression; base tag is fine.
        return base_action_tag, base_action_reason

    # Default: no override
    return base_action_tag, base_action_reason

# ------------------------------------------------------------
# Scalp candidate overlay (non-intrusive tier)
# ------------------------------------------------------------
def maybe_tag_scalp_candidate(
    row: Dict[str, Any],
    *,
    phase_view: PhaseView,
    risk_view: RiskView,
    base_action_tag: str,
    base_action_reason: str,
) -> Tuple[str, str]:
    """
    Light-weight, non-intrusive scalp layer.

    Goals:
      • NEVER override core religion (trend BUY / EXIT / TV overrides).
      • NEVER fight tv_override (those are your strongest convictions).
      • ONLY tag "SCALP_CANDIDATE_LONG" when:
          - decision is mild (HOLD / WATCH / NO decision),
          - structure is supportive (pullback / basing, not breakdown),
          - EMAs are turning up,
          - RSI / momentum isn't dead or overcooked,
          - volume / OBV / VWAP give some tailwind,
          - risk is not HIGH,
          - time-of-day is in a safe intraday window.

    Behaviour:
      • Does NOT change row["decision"].
      • Only refines the (action_tag, action_reason) pair.
    """
    # Basic sanity
    if not isinstance(row, dict):
        return base_action_tag, base_action_reason

    # Respect TV overrides & hard risk exits
    if row.get("tv_override"):
        return base_action_tag, base_action_reason

    decision = _normalize_decision(row)
    playbook = (row.get("playbook") or "UNKNOWN").upper()
    risk_mode = (risk_view.mode or "MEDIUM").upper()
    drivers_raw = row.get("drivers") or []
    drivers = {str(d) for d in drivers_raw if d is not None}

    # 0) Hard outs: don't scalp against explicit exits or strong avoid.
    if decision in {"EXIT", "SELL", "STOP_LOSS_HIT", "STRONG_AVOID", "AVOID"}:
        return base_action_tag, base_action_reason
    if risk_mode == "HIGH":
        return base_action_tag, base_action_reason

    # 1) Only consider "meh but not trash" situations:
    #    decision is HOLD / WATCH / empty, and base action isn't already strong.
    if decision not in {"HOLD", "WATCH", ""}:
        return base_action_tag, base_action_reason

    strong_tags = {
        "STRONG_BUY",
        "BREAKOUT_BUY",
        "BTST_LONG",
        "SWING_LONG",
        "EXIT",
        "BOOK_PARTIAL",
        "TRAIL_STOP",
        "RISK_OFF",
    }
    if base_action_tag in strong_tags:
        return base_action_tag, base_action_reason

    # 2) Playbook & structure gating
    #    Allow: UNKNOWN / INTRADAY_RANGE / INTRADAY_SCALP for v1.
    if playbook not in {"UNKNOWN", "INTRADAY_RANGE", "INTRADAY_SCALP"}:
        return base_action_tag, base_action_reason

    label_u = phase_view.label.upper()
    # Very permissive v1 structure list – tuned later via parquet audits.
    allowed_struct_keywords = {
        "PULLBACK",
        "RANGE_BOTTOMING",
        "POST_SHAKEOUT",
        "CONSOLIDATION",
        "BASING",
    }
    blocked_struct_keywords = {
        "BREAKDOWN",
        "FAILED",
        "DISTRIBUTION",
        "EXHAUSTION",
    }

    # If label contains any explicit "bad" keyword, bail.
    if any(k in label_u for k in blocked_struct_keywords):
        return base_action_tag, base_action_reason

    # If there is a label, but it's not any of our allowed structure hints,
    # we simply stay neutral (no scalp tag). This keeps it conservative.
    if label_u not in {"", "UNKNOWN"}:
        if not any(k in label_u for k in allowed_struct_keywords):
            return base_action_tag, base_action_reason

    # 3) EMAs must be turning up or supportive for a long scalp.
    if "EMA↑" not in drivers and "EMA_TURN_UP" not in drivers:
        return base_action_tag, base_action_reason

    # 4) RSI / momentum sanity via driver tags
    rsi_too_low = any(tag in drivers for tag in ("RSI≤30", "RSI≤25"))
    rsi_too_high = any(tag in drivers for tag in ("RSI≥70", "RSI≥75"))
    if rsi_too_low or rsi_too_high:
        # Panic / exhaustion; not a "calm scalp" zone.
        return base_action_tag, base_action_reason

    # 5) Volume / OBV / VWAP tailwind
    has_vol_tailwind = any(
        tag in drivers
        for tag in (
            "OBV↑",
            "Volume>Avg",
            "Volume_Spike",
            "VWAP>",
            "Above_VWAP",
        )
    )
    if not has_vol_tailwind:
        return base_action_tag, base_action_reason

    # 6) Time-of-day window (safe scalp buckets)
    time_bucket = row.get("time_bucket") or _time_bucket_from_ts(row.get("timestamp"))
    # For v1, we allow all three normal buckets; you can tighten this later.
    safe_buckets = {"OPENING_DRIVE", "MID_SESSION", "LATE_SESSION"}
    if time_bucket and (time_bucket not in safe_buckets):
        return base_action_tag, base_action_reason

    # ✅ If we survive all filters, surface as scalp candidate.
    new_tag = "SCALP_CANDIDATE_LONG"
    new_reason = (
        "Scalp candidate long: EMA↑ with non-extreme RSI and volume/VWAP tailwind "
        "in supportive microstructure. Treat as optional, small-size intraday trade; "
        "base decision remains unchanged."
    )
    return new_tag, new_reason


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------
def apply_decision_overlays(
    row: Dict[str, Any],
    *,
    phase: Any = None,
    risk: Any = None,
    interval: Optional[str] = None,  # reserved for future time-of-frame tweaks
) -> Dict[str, Any]:
    """Enrich a cockpit row with action_tag / action_reason / risk_mode.

    Parameters
    ----------
    row : dict
        Cockpit row from scoring / actionable pipeline.
        Expected keys (best-effort):
          • decision      : base decision string
          • bias          : e.g. "Long" / "Weak" / "Counter-trend Long"
          • trade_status  : "WATCH" / "ACTIVE" / "EXIT"
          • playbook      : assigned by queen.strategies.playbook
          • time_bucket   : optional; if missing we infer from timestamp
          • drivers       : list[str] driver tags from scoring layer
          • position      : dict with "pnl_pct", etc. (optional)
          • tv_override   : bool, if TV fusion override is active

    phase : PhaseState or dict (optional)
        Microstructure phase output from queen.technicals.microstructure.phases.
        Used to tune actions like:
          • BREAKOUT_SETUP / BREAKOUT_CONFIRMED / POST_BREAKOUT_FADE / BREAKDOWN

    risk : RiskState or dict (optional)
        Risk output from microstructure/risk layer.
        Used to derive:
          • risk_mode = LOW / MEDIUM / HIGH

    Returns
    -------
    row : dict
        Same dict, with additional keys:
          • action_tag      : primary action suggestion
          • action_reason   : brief why
          • risk_mode       : LOW / MEDIUM / HIGH
    """
    if not isinstance(row, dict):
        return row

    # Ensure we have a coherent time_bucket before choosing tags.
    if not row.get("time_bucket"):
        row["time_bucket"] = _time_bucket_from_ts(row.get("timestamp"))

    phase_view = _view_phase(phase)
    risk_view = _view_risk(risk)

    # 1) Base action from decision + playbook + phase + risk + pnl
    base_action_tag, base_action_reason = _choose_action_tag(
        row,
        phase_view=phase_view,
        risk_view=risk_view,
    )

    # 2) Phase-driven overrides (breakout setup / confirmed / breakdown / fade)
    phased_action_tag, phased_action_reason = _phase_override_action(
        row,
        phase_view=phase_view,
        risk_view=risk_view,
        base_action_tag=base_action_tag,
        base_action_reason=base_action_reason,
    )

    # 3) Optional scalp candidate overlay (non-intrusive, last mile)
    action_tag, action_reason = maybe_tag_scalp_candidate(
        row,
        phase_view=phase_view,
        risk_view=risk_view,
        base_action_tag=phased_action_tag,
        base_action_reason=phased_action_reason,
    )

    row["action_tag"] = action_tag
    row["action_reason"] = action_reason
    row["risk_mode"] = risk_view.mode

    return row


# ------------------------------------------------------------
# Example usage for your local sanity checks
# ------------------------------------------------------------
if __name__ == "__main__":
    # Example 1: 360ONE / HAL-style strong intraday trend BUY
    base_row_trend = {
        "timestamp": "2025-11-28 09:45:00+05:30",
        "symbol": "360ONE",
        "decision": "BUY",
        "bias": "Long",
        "trade_status": "WATCH",
        "playbook": "INTRADAY_TREND",
        "position": {"pnl_pct": 0.8},
        "drivers": ["EMA↑", "RSI≥60", "VWAP>"],
    }
    print("TREND BUY →", apply_decision_overlays(base_row_trend))

    # Example 2: Hypothetical scalp-style mild setup (VOLTAMP-like when engine is cautious)
    base_row_scalp_candidate = {
        "timestamp": "2025-11-28 12:30:00+05:30",
        "symbol": "VOLTAMP",
        "decision": "HOLD",
        "bias": "Neutral",
        "trade_status": "WATCH",
        "playbook": "INTRADAY_RANGE",
        "position": {"pnl_pct": 0.2},
        "drivers": ["EMA↑", "RSI≤55", "OBV↑", "VWAP>"],
        "tv_override": False,
    }
    phase_pullback = {"label": "PULLBACK_IN_UPTREND", "bias": "bullish"}
    print(
        "SCALP CANDIDATE →",
        apply_decision_overlays(base_row_scalp_candidate, phase=phase_pullback),
    )

    # Example 3: HOLD with decent profit, mid-session (BOOK_PARTIAL / TRAIL_STOP logic)
    base_row_hold = {
        "timestamp": "2025-11-28 14:00:00+05:30",
        "symbol": "HAL",
        "decision": "HOLD",
        "bias": "Long",
        "trade_status": "ACTIVE",
        "playbook": "INTRADAY_TREND",
        "position": {"pnl_pct": 2.4},
        "drivers": ["EMA↑", "RSI≥60", "VWAP>"],
    }
    phase_example = {"label": "BREAKOUT_CONFIRMED", "bias": "bullish"}
    print("HOLD WITH PROFIT →", apply_decision_overlays(base_row_hold, phase=phase_example))

    # Example 4: AVOID during breakdown phase
    base_row_avoid = {
        "timestamp": "2025-11-28 11:00:00+05:30",
        "symbol": "VOLTAMP",
        "decision": "AVOID",
        "bias": "Weak",
        "trade_status": "AVOID",
        "playbook": "UNKNOWN",
        "drivers": ["EMA↓", "RSI≤45"],
    }
    phase_breakdown = {"label": "BREAKDOWN_CONFIRMED", "bias": "bearish"}
    risk_high = {"mode": "HIGH", "reason": "index volatility spike"}
    print(
        "AVOID / BREAKDOWN →",
        apply_decision_overlays(base_row_avoid, phase=phase_breakdown, risk=risk_high),
    )
