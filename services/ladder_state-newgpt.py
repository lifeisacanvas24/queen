#!/usr/bin/env python3
# ============================================================
# queen/services/ladder_state.py — v1.4
# Hybrid risk ladder + WRB memory + Option-B Reversible Runner
# ------------------------------------------------------------
# Core Philosophy:
#   • Runner mode (stage≥3) is a PRIVILEGE of holding T3 structure.
#   • If structure is lost (cmp < T3), runner must immediately deactivate.
#   • WRB memory is preserved across activation/deactivation cycles.
#   • Capital Protection > Trend Ego.
#
# Key Features:
#   • STATIC ladder T1–T6
#   • GLOBAL L2 lock with tf-priority
#   • Reversible runner mode (Option-B)
#   • WRB base memory (never reset intraday)
#   • Stage≥3 trailing SL only when T3 holds
#   • Cleaned SL logic + rescue fallback
#   • Correct TF arbitration
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Tuple, Optional


# Global in-memory ladder-by-symbol
_LADDER: Dict[str, "LadderState"] = {}

# TF priority ordering for tie-breaker
_TF_ORDER = ["5m", "10m", "15m", "30m", "60m", "1h", "75m", "90m", "120m", "1d"]


def _tf_priority(tf: str) -> int:
    tf = (tf or "").lower()
    try:
        return _TF_ORDER.index(tf)
    except ValueError:
        return -1


def _today_trading_date() -> date:
    return date.today()


# ---------------------------------------------------------
# State Object
# ---------------------------------------------------------
@dataclass
class LadderState:
    symbol: str
    trading_date: date
    stage: int = 0
    ref_interval: str = ""
    t1: float | None = None
    t2: float | None = None
    t3: float | None = None
    t4: float | None = None
    t5: float | None = None
    t6: float | None = None
    last_price: float | None = None

    # WRB memory (never reset intraday)
    wrb_base: float | None = None

    # Trailing SL active only in runner
    trail_sl: float | None = None

    # Label for UI
    def label(self, side: str = "LONG") -> str:
        long_side = side.upper() != "SHORT"
        if long_side:
            return [
                "Below T1",
                "Between T1–T2",
                "Between T2–T3",
                "Between T3–T4",
                "Between T4–T5",
                "Between T5–T6",
                "Above T6 (Exhaust/Runner)",
            ][self.stage]
        else:
            return [
                "Above T1",
                "Between T1–T2",
                "Between T2–T3",
                "Between T3–T4",
                "Between T4–T5",
                "Between T5–T6",
                "Below T6 (Exhaust/Runner)",
            ][self.stage]


# ---------------------------------------------------------
# Reset when date changes
# ---------------------------------------------------------
def _reset_if_new_day(state: LadderState, trading_date: date) -> LadderState:
    if state.trading_date != trading_date:
        state.trading_date = trading_date
        state.stage = 0
        state.ref_interval = ""
        state.t1 = state.t2 = state.t3 = None
        state.t4 = state.t5 = state.t6 = None
        state.last_price = None
        # WRB base is kept RESET per day (fresh day → new structure)
        state.wrb_base = None
        state.trail_sl = None
    return state


# ---------------------------------------------------------
# Extract t1,t2,t3 from row or target text
# ---------------------------------------------------------
def _extract_targets_t1_t3(row: Dict[str, Any]) -> Tuple[float, float, float] | None:
    if all(k in row for k in ("t1", "t2", "t3")):
        try:
            return float(row["t1"]), float(row["t2"]), float(row["t3"])
        except Exception:
            pass

    targets_list = row.get("targets") or []
    levels = {}

    for t in targets_list:
        try:
            parts = str(t).split()
            if len(parts) >= 2:
                label = parts[0].upper()
                level = float(parts[1])
                levels[label.lower()] = level
        except Exception:
            continue

    t1, t2, t3 = levels.get("t1"), levels.get("t2"), levels.get("t3")
    return (t1, t2, t3) if (t1 and t2 and t3) else None


# ---------------------------------------------------------
# Extend to T4–T6
# ---------------------------------------------------------
def _extend_static_to_t6(t1: float, t2: float, t3: float, side: str) -> List[float]:
    step = abs(t2 - t1)
    if step <= 0:
        step = abs(t3 - t2) or max(1.0, abs(t1) * 0.005)

    long_side = side.upper() != "SHORT"
    if long_side:
        t4, t5, t6 = t3 + step, t3 + 2*step, t3 + 3*step
    else:
        t4, t5, t6 = t3 - step, t3 - 2*step, t3 - 3*step

    return [t1, t2, t3, t4, t5, t6]


# ---------------------------------------------------------
# Stage calculation
# ---------------------------------------------------------
def _stage_from_price_ext(price: float, levels: List[float], side: str):
    long_side = side.upper() != "SHORT"
    lvls = [float(x) for x in levels]

    def _hit(lvl): return price >= lvl if long_side else price <= lvl

    hits = {f"T{i+1}": _hit(lvls[i]) for i in range(6)}

    if long_side:
        if price < lvls[0]: return 0, hits
        if price < lvls[1]: return 1, hits
        if price < lvls[2]: return 2, hits
        if price < lvls[3]: return 3, hits
        if price < lvls[4]: return 4, hits
        if price < lvls[5]: return 5, hits
        return 6, hits
    else:
        if price > lvls[0]: return 0, hits
        if price > lvls[1]: return 1, hits
        if price > lvls[2]: return 2, hits
        if price > lvls[3]: return 3, hits
        if price > lvls[4]: return 4, hits
        if price > lvls[5]: return 5, hits
        return 6, hits


# ---------------------------------------------------------
# TrueRange + WRB detection
# ---------------------------------------------------------
def _true_range(h: float, l: float, pc: float | None) -> float:
    tr1 = h - l
    if pc is None:
        return tr1
    return max(tr1, abs(h - pc), abs(l - pc))


def _is_directional_wrb(
    *, last_open, last_high, last_low, last_close,
    prev_close, atr, side, wrb_mult=1.5, body_ratio_min=0.55
) -> Tuple[bool, float | None]:

    if not atr or atr <= 0:
        return False, None

    tr = _true_range(last_high, last_low, prev_close)
    if tr <= wrb_mult * atr:
        return False, None

    rng = max(1e-9, last_high - last_low)
    body = abs(last_close - last_open)
    body_ratio = body / rng

    # Direction check
    long_side = side.upper() != "SHORT"
    directional = (last_close > last_open) if long_side else (last_close < last_open)
    if not directional or body_ratio < body_ratio_min:
        return False, None

    wrb_base = last_low if long_side else last_high
    return True, float(wrb_base)


# ---------------------------------------------------------
# Main augmentor
# ---------------------------------------------------------
def augment_targets_state(row: Dict[str, Any], interval: str) -> Dict[str, Any]:

    symbol = str(row.get("symbol") or row.get("SYMBOL") or "").upper()
    if not symbol:
        return row

    # CMP
    cmp_val = row.get("cmp") or row.get("CMP")
    if cmp_val is None:
        return row
    cmp_val = float(cmp_val)

    # Side
    side = "LONG"
    dec = str(row.get("decision") or "").upper()
    if dec in ("SELL", "SHORT", "EXIT-SELL"):
        side = "SHORT"

    # Extract static T1–T3
    t123 = _extract_targets_t1_t3(row)
    if not t123:
        return row
    t1, t2, t3 = t123
    static_lvls = _extend_static_to_t6(t1, t2, t3, side)
    t1, t2, t3, t4, t5, t6 = static_lvls

    row.update({"t1": t1, "t2": t2, "t3": t3,
                "t4": t4, "t5": t5, "t6": t6})

    # Local stage
    local_stage, _local_hits = _stage_from_price_ext(cmp_val, static_lvls, side)

    # Global state access
    trading_date = _today_trading_date()
    state = _LADDER.get(symbol) or LadderState(symbol, trading_date)
    state = _reset_if_new_day(state, trading_date)

    # Global L2 promotion
    should_promote = False
    if local_stage > state.stage:
        should_promote = True
    elif local_stage == state.stage:
        if _tf_priority(interval) > _tf_priority(state.ref_interval):
            should_promote = True

    if should_promote:
        state.stage = local_stage
        state.ref_interval = interval
        state.t1, state.t2, state.t3 = t1, t2, t3
        state.t4, state.t5, state.t6 = t4, t5, t6
        state.last_price = cmp_val
        _LADDER[symbol] = state

    # Global levels for hit-marking
    global_lvls = [
        state.t1 or t1, state.t2 or t2, state.t3 or t3,
        state.t4 or t4, state.t5 or t5, state.t6 or t6,
    ]
    _, global_hits = _stage_from_price_ext(cmp_val, global_lvls, side)

    # ATR (any TF)
    atr = (
        row.get("atr_intraday") or row.get("atr_intra") or row.get("atr_15m")
        or row.get("atr") or row.get("ATR")
    )
    atr = float(atr) if atr else None

    # Dynamic ladder for display
    dyn = None
    if atr:
        base_px = cmp_val
        mults = [0.35, 0.85, 1.35, 1.85, 2.35, 2.85]
        if side.upper() != "SHORT":
            d_targets = [base_px + m*atr for m in mults]
            d_sl = base_px - 0.70*atr
        else:
            d_targets = [base_px - m*atr for m in mults]
            d_sl = base_px + 0.70*atr
        dyn = {f"t{i+1}": d_targets[i] for i in range(6)}
        dyn["sl"] = d_sl

    # WRB detection
    wrb_flag = False
    wrb_base = None
    try:
        lo = row.get("last_tf_open")
        lh = row.get("last_tf_high")
        ll = row.get("last_tf_low")
        lc = row.get("last_tf_close")
        pc = row.get("prev_tf_close")

        if atr and all(x is not None for x in (lo, lh, ll, lc)):
            wrb_flag, wrb_base = _is_directional_wrb(
                last_open=float(lo),
                last_high=float(lh),
                last_low=float(ll),
                last_close=float(lc),
                prev_close=float(pc) if pc is not None else None,
                atr=float(atr),
                side=side,
            )
    except Exception:
        wrb_flag, wrb_base = False, None

    # WRB memory (never reset intraday)
    if wrb_flag and wrb_base is not None:
        if state.wrb_base is None:
            state.wrb_base = wrb_base
        else:
            if side.upper() != "SHORT":
                if wrb_base > state.wrb_base:
                    state.wrb_base = wrb_base
            else:
                if wrb_base < state.wrb_base:
                    state.wrb_base = wrb_base
        _LADDER[symbol] = state

    # -----------------------------------------------------
    # Option-B Reversible Runner Logic
    # -----------------------------------------------------

    current_stage, _ = _stage_from_price_ext(cmp_val, global_lvls, side)
    in_runner_now = current_stage >= 3
    was_in_runner = state.stage >= 3  # From global lock

    # If structure breaks (cmp < T3), runner MUST deactivate
    if not in_runner_now:
        state.trail_sl = None
    else:
        # Only compute trailing SL if runner active
        last_low = row.get("last_tf_low")
        last_high = row.get("last_tf_high")

        candidates = []
        if side.upper() != "SHORT":
            if last_low is not None:
                candidates.append(float(last_low))
            if state.wrb_base is not None:
                candidates.append(float(state.wrb_base))
            if candidates:
                state.trail_sl = max(candidates)
        else:
            if last_high is not None:
                candidates.append(float(last_high))
            if state.wrb_base is not None:
                candidates.append(float(state.wrb_base))
            if candidates:
                state.trail_sl = min(candidates)

    _LADDER[symbol] = state

    # Override dyn SL only visually
    if dyn and state.trail_sl is not None and in_runner_now:
        dyn["sl"] = state.trail_sl

    # -----------------------------------------------------
    # R-levels
    # -----------------------------------------------------
    r_levels = None
    try:
        entry_px = row.get("entry") or cmp_val
        entry_px = float(entry_px)

        # SL Priority:
        # 1) Runner SL when runner active
        # 2) Static SL (cockpit)
        # 3) Dyn SL fallback
        if in_runner_now and state.trail_sl is not None:
            sl_px = state.trail_sl
        else:
            sl_px = row.get("sl")

        if sl_px is None and dyn:
            sl_px = dyn.get("sl")

        if sl_px is not None:
            sl_px = float(sl_px)

            # Guard: SL must be on correct side
            if side.upper() != "SHORT" and sl_px >= entry_px:
                sl_px = float(row.get("sl") or sl_px)
            if side.upper() == "SHORT" and sl_px <= entry_px:
                sl_px = float(row.get("sl") or sl_px)

            r = abs(entry_px - sl_px)
            if r > 0:
                if side.upper() != "SHORT":
                    r1, r2, r3 = entry_px + r, entry_px + 2*r, entry_px + 3*r
                else:
                    r1, r2, r3 = entry_px - r, entry_px - 2*r, entry_px - 3*r

                r_levels = {"r1": r1, "r2": r2, "r3": r3}
                row.update(r_levels)
    except Exception:
        r_levels = None

    # Final state packaging
    static_dict = {"t1": t1, "t2": t2, "t3": t3,
                   "t4": t4, "t5": t5, "t6": t6}

    row["targets_state"] = {
        "stage": current_stage,
        "label": state.label(side),
        "ref_interval": state.ref_interval,
        "static": static_dict,
        "hits": global_hits,
        "dynamic": dyn,
        "wrb": {
            "flag": bool(wrb_flag),
            "base": state.wrb_base,
            "trail_sl": state.trail_sl,
        },
        "risk_levels": r_levels,
    }

    row["targets_label"] = state.label(side)
    return row
