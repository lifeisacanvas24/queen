#!/usr/bin/env python3
# ============================================================
# queen/services/ladder_state.py — v1.3
# Hybrid risk ladder + WRB runner trailing (Option A)
# ------------------------------------------------------------
# • Each timeframe computes a local stage from STATIC T1–T6.
# • A per-symbol global LadderState only PROMOTES (L2 lock).
# • Higher stage wins; tie → higher timeframe wins.
# • Adds:
#     - WRB detection (True Range > 1.5×ATR14)
#     - Directional WRB filter (avoid doji traps)
#     - Stage≥3 trailing SL to WRB base / last candle low-high
#     - Dynamic R1–R3 from Entry & SL
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Tuple, Optional

_LADDER: Dict[str, "LadderState"] = {}

_TF_ORDER = ["5m", "10m", "15m", "30m", "60m", "1h", "75m", "90m", "120m", "1d"]


def _tf_priority(tf: str) -> int:
    tf = (tf or "").lower()
    try:
        return _TF_ORDER.index(tf)
    except ValueError:
        return -1


def _today_trading_date() -> date:
    return date.today()


@dataclass
class LadderState:
    symbol: str
    trading_date: date
    stage: int = 0             # 0..6
    ref_interval: str = ""
    t1: float | None = None
    t2: float | None = None
    t3: float | None = None
    t4: float | None = None
    t5: float | None = None
    t6: float | None = None
    last_price: float | None = None

    # WRB / runner trailing memory (Option A)
    wrb_base: float | None = None     # low of WRB for long / high of WRB for short
    trail_sl: float | None = None     # active trailing SL once stage>=3

    def label(self, side: str = "LONG") -> str:
        long_side = side.upper() != "SHORT"
        if long_side:
            match self.stage:
                case 0: return "Below T1"
                case 1: return "Between T1–T2"
                case 2: return "Between T2–T3"
                case 3: return "Between T3–T4"
                case 4: return "Between T4–T5"
                case 5: return "Between T5–T6"
                case _: return "Above T6 (Exhaust/Runner)"
        else:
            match self.stage:
                case 0: return "Above T1"
                case 1: return "Between T1–T2"
                case 2: return "Between T2–T3"
                case 3: return "Between T3–T4"
                case 4: return "Between T4–T5"
                case 5: return "Between T5–T6"
                case _: return "Below T6 (Exhaust/Runner)"


def _reset_if_new_day(state: LadderState, trading_date: date) -> LadderState:
    if state.trading_date != trading_date:
        state.trading_date = trading_date
        state.stage = 0
        state.ref_interval = ""
        state.t1 = state.t2 = state.t3 = None
        state.t4 = state.t5 = state.t6 = None
        state.last_price = None
        state.wrb_base = None
        state.trail_sl = None
    return state


# ------------------------------------------------------------------
# Targets extraction + extension
# ------------------------------------------------------------------
def _extract_targets_t1_t3(row: Dict[str, Any]) -> Tuple[float, float, float] | None:
    if all(k in row for k in ("t1", "t2", "t3")):
        try:
            return float(row["t1"]), float(row["t2"]), float(row["t3"])
        except Exception:
            pass

    targets_list = row.get("targets") or []
    levels: Dict[str, float] = {}
    for t in targets_list:
        try:
            parts = str(t).split()
            if len(parts) < 2:
                continue
            label = parts[0].upper()
            level = float(parts[1])
            levels[label.lower()] = level
        except Exception:
            continue

    t1, t2, t3 = levels.get("t1"), levels.get("t2"), levels.get("t3")
    if t1 is None or t2 is None or t3 is None:
        return None
    return t1, t2, t3


def _extend_static_to_t6(t1: float, t2: float, t3: float, side: str) -> List[float]:
    step = abs(float(t2) - float(t1))
    if step <= 0:
        step = abs(float(t3) - float(t2)) or max(1.0, float(t1) * 0.005)

    long_side = side.upper() != "SHORT"
    if long_side:
        t4 = t3 + step
        t5 = t4 + step
        t6 = t5 + step
    else:
        t4 = t3 - step
        t5 = t4 - step
        t6 = t5 - step

    return [t1, t2, t3, t4, t5, t6]


# ------------------------------------------------------------------
# Stage + hits
# ------------------------------------------------------------------
def _stage_from_price_ext(price: float, levels: List[float], side: str) -> Tuple[int, Dict[str, bool]]:
    long_side = side.upper() != "SHORT"
    lvls = [float(x) for x in levels]

    def _hit(level: float) -> bool:
        return price >= level if long_side else price <= level

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


def _format_targets_text(
    tg: Dict[str, Any] | None,
    *,
    hits: Dict[str, bool] | None = None,
    decimals: int = 1,
    prefix: str = "T",
) -> str:
    if not tg:
        return ""

    def _fmt(val: Any) -> str:
        try:
            f = float(val)
        except Exception:
            return "-"
        return f"{f:.{decimals}f}"

    parts = []
    for idx in range(1, 7):
        key = f"t{idx}"
        if key not in tg or tg[key] is None:
            continue
        label = f"{prefix}{idx}"
        part = f"{label} {_fmt(tg[key])}"
        if hits and hits.get(label):
            part += " ✓"
        parts.append(part)

    return " · ".join(parts)


# ------------------------------------------------------------------
# WRB detection (Option A) + directional filter
# ------------------------------------------------------------------
def _true_range(last_high: float, last_low: float, prev_close: float | None) -> float:
    tr1 = last_high - last_low
    if prev_close is None:
        return tr1
    tr2 = abs(last_high - prev_close)
    tr3 = abs(last_low - prev_close)
    return max(tr1, tr2, tr3)


def _is_directional_wrb(
    *,
    last_open: float,
    last_high: float,
    last_low: float,
    last_close: float,
    prev_close: float | None,
    atr: float,
    side: str,
    wrb_mult: float = 1.5,
    body_ratio_min: float = 0.55,  # directional body filter
) -> Tuple[bool, float | None]:
    """
    WRB if TrueRange > wrb_mult * ATR AND body is directional.
    Returns (is_wrb, wrb_base)
      - wrb_base = low for long / high for short
    """
    if atr is None or atr <= 0:
        return False, None

    tr = _true_range(last_high, last_low, prev_close)
    if tr <= wrb_mult * atr:
        return False, None

    rng = max(1e-9, last_high - last_low)
    body = abs(last_close - last_open)
    body_ratio = body / rng

    long_side = side.upper() != "SHORT"
    directional = (last_close > last_open) if long_side else (last_close < last_open)
    if not directional:
        return False, None
    if body_ratio < body_ratio_min:
        return False, None

    wrb_base = last_low if long_side else last_high
    return True, float(wrb_base)


# ------------------------------------------------------------------
# Main augmentor (GLOBAL L2 lock + runner trailing)
# ------------------------------------------------------------------
def augment_targets_state(row: Dict[str, Any], interval: str) -> Dict[str, Any]:
    symbol = str(row.get("symbol") or row.get("SYMBOL") or "").upper()
    if not symbol:
        return row

    cmp_val = row.get("cmp") or row.get("CMP")
    if cmp_val is None:
        return row
    try:
        cmp_val = float(cmp_val)
    except Exception:
        return row

    interval = interval or str(row.get("interval") or "")
    side = "LONG"
    dec = str(row.get("decision") or "").upper()
    if dec in ("SELL", "SHORT", "EXIT-SELL"):
        side = "SHORT"

    t123 = _extract_targets_t1_t3(row)
    if not t123:
        return row

    t1, t2, t3 = t123
    static_lvls = _extend_static_to_t6(t1, t2, t3, side)
    t1, t2, t3, t4, t5, t6 = static_lvls

    row.update({"t1": t1, "t2": t2, "t3": t3, "t4": t4, "t5": t5, "t6": t6})

    # 1) Local stage from STATIC T1–T6
    local_stage, _local_hits = _stage_from_price_ext(cmp_val, static_lvls, side)

    # 2) Global state reset per trading day
    trading_date = _today_trading_date()
    state = _LADDER.get(symbol) or LadderState(symbol=symbol, trading_date=trading_date)
    state = _reset_if_new_day(state, trading_date)

    # 3) Promotion rules (L2 lock)
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

    label = state.label(side=side)

    global_lvls = [
        state.t1 or t1, state.t2 or t2, state.t3 or t3,
        state.t4 or t4, state.t5 or t5, state.t6 or t6,
    ]
    _, global_hits = _stage_from_price_ext(cmp_val, global_lvls, side)

    # 4) Dynamic ATR ladder for THIS TF (Option 1 multipliers)
    atr = (
        row.get("atr_intraday")
        or row.get("atr_intra")
        or row.get("atr_15m")
        or row.get("atr")
        or row.get("ATR")
    )

    dyn = None
    try:
        if atr is not None:
            atr = float(atr)
            base_px = float(cmp_val)
            mults = [0.35, 0.85, 1.35, 1.85, 2.35, 2.85]

            if side.upper() != "SHORT":
                d_targets = [base_px + m * atr for m in mults]
                d_sl = base_px - 0.70 * atr
            else:
                d_targets = [base_px - m * atr for m in mults]
                d_sl = base_px + 0.70 * atr

            dyn = {f"t{i+1}": d_targets[i] for i in range(6)}
            dyn["sl"] = d_sl
    except Exception:
        dyn = None

    # ------------------------------------------------------------------
    # 5) WRB runner trailing (Option A: same TF)
    # Inputs expected from live.py:
    #   last_tf_open/high/low/close, prev_tf_close, last_tf_low/high, ATR
    # ------------------------------------------------------------------
    wrb_flag = False
    wrb_base = None

    try:
        if atr is not None:
            lo = row.get("last_tf_open")
            lh = row.get("last_tf_high")
            ll = row.get("last_tf_low")
            lc = row.get("last_tf_close")
            pc = row.get("prev_tf_close")
            if all(x is not None for x in (lo, lh, ll, lc)):
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

    # Update WRB base memory only when stage >=3 (runner mode)
    if state.stage >= 3 and wrb_base is not None:
        if state.wrb_base is None:
            state.wrb_base = wrb_base
        else:
            # only upgrade base in direction of trend
            if side.upper() != "SHORT":
                if wrb_base > state.wrb_base:
                    state.wrb_base = wrb_base
            else:
                if wrb_base < state.wrb_base:
                    state.wrb_base = wrb_base
        _LADDER[symbol] = state

    # Compute trailing SL once stage>=3
    trail_sl = None
    try:
        if state.stage >= 3:
            if side.upper() != "SHORT":
                last_low = row.get("last_tf_low")
                candidates = []
                if last_low is not None:
                    candidates.append(float(last_low))
                if state.wrb_base is not None:
                    candidates.append(float(state.wrb_base))
                if candidates:
                    trail_sl = max(candidates)
            else:
                last_high = row.get("last_tf_high")
                candidates = []
                if last_high is not None:
                    candidates.append(float(last_high))
                if state.wrb_base is not None:
                    candidates.append(float(state.wrb_base))
                if candidates:
                    trail_sl = min(candidates)

            if trail_sl is not None:
                state.trail_sl = float(trail_sl)
                _LADDER[symbol] = state
    except Exception:
        trail_sl = None

    # If trailing SL active, override dyn SL (tight runner exit)
    # NOTE: This override is primarily for reporting/visualization of dynamic SL,
    # but the primary R1-R3 calculation below uses the proper priority logic.
    if dyn and state.trail_sl is not None and state.stage >= 3:
        dyn["sl"] = float(state.trail_sl)

    # ------------------------------------------------------------------
    # 6) Dynamic R1/R2/R3 from Entry & SL
    # ------------------------------------------------------------------
    r_levels = None
    try:
        entry_px = row.get("entry") or cmp_val

        # --- CORRECTED SL PRIORITY LOGIC ---
        # RUNNER MODE (Stage >= 3): use trailing SL (rule 9+)
        if state.stage >= 3 and state.trail_sl is not None:
            sl_px = state.trail_sl

        # ENTRY MODE (Stage < 3): use static SL from cockpit_row
        else:
            sl_px = row.get("sl")

        # RESCUE fallback: if still None → use dyn SL (ATR-based)
        if sl_px is None and dyn:
            sl_px = dyn.get("sl")
        # -----------------------------------

        if entry_px is not None and sl_px is not None:
            entry_px = float(entry_px)
            sl_px = float(sl_px)

            # If SL accidentally ends up on wrong side, fallback to static risk
            if side.upper() != "SHORT" and sl_px >= entry_px:
                sl_px = float(row.get("sl") or sl_px)
            if side.upper() == "SHORT" and sl_px <= entry_px:
                sl_px = float(row.get("sl") or sl_px)

            r = abs(entry_px - sl_px)
            if r > 0:
                if side.upper() != "SHORT":
                    r1 = entry_px + 1.0 * r
                    r2 = entry_px + 2.0 * r
                    r3 = entry_px + 3.0 * r
                else:
                    r1 = entry_px - 1.0 * r
                    r2 = entry_px - 2.0 * r
                    r3 = entry_px - 3.0 * r

                r_levels = {"r1": r1, "r2": r2, "r3": r3}
                row.update({"r1": r1, "r2": r2, "r3": r3})
    except Exception:
        r_levels = None

    static_dict = {"t1": t1, "t2": t2, "t3": t3, "t4": t4, "t5": t5, "t6": t6}

    row["targets_state"] = {
        "stage": state.stage,
        "label": label,
        "ref_interval": state.ref_interval,
        "static": static_dict,
        "hits": global_hits,
        "dynamic": dyn, 				 # {t1..t6, sl}
        "wrb": {
            "flag": bool(wrb_flag),
            "base": state.wrb_base,
            "trail_sl": state.trail_sl,
        },
        "risk_levels": r_levels, 		# {r1,r2,r3} if computed
    }

    row["targets_static_text"] = _format_targets_text(static_dict, hits=global_hits, decimals=1)
    row["targets_dynamic_text"] = (
        _format_targets_text(dyn, hits=global_hits, decimals=2) if dyn else ""
    )
    row["targets_label"] = label
    return row
