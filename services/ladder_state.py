#!/usr/bin/env python3
# ============================================================
# queen/services/ladder_state.py — v1.0
# Hybrid risk ladder (local TF + global symbol-level controller)
# ------------------------------------------------------------
#  • Each timeframe computes its own local stage.
#  • A per-symbol global LadderState tracks the "authoritative" stage.
#  • Higher stage always wins; on ties, higher timeframe wins.
#  • UI gets:
#       - targets_state.stage / label / ref_interval
#       - static ladder levels (T1/T2/T3)
#       - dynamic ATR ladder for this TF
#       - hits map for global T1/T2/T3
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Tuple

# in-process per-symbol state for the current process
_LADDER: Dict[str, LadderState] = {}

# simple priority ordering for timeframes
_TF_ORDER = ["5m", "10m", "15m", "30m", "60m", "1h", "75m", "90m", "120m", "1d"]


def _tf_priority(tf: str) -> int:
    tf = (tf or "").lower()
    try:
        return _TF_ORDER.index(tf)
    except ValueError:
        return -1


def _today_trading_date() -> date:
    # For now, just calendar date. You can later plug in an exchange calendar.
    return date.today()


@dataclass
class LadderState:
    symbol: str
    trading_date: date
    stage: int = 0          # 0=below T1, 1=between T1–T2, 2=between T2–T3, 3=above T3
    ref_interval: str = ""
    t1: float | None = None
    t2: float | None = None
    t3: float | None = None
    last_price: float | None = None

    def label(self, side: str = "LONG") -> str:
        """Human label for the current stage, preserving old Bible wording."""
        long_side = side.upper() != "SHORT"
        if long_side:
            match self.stage:
                case 0:
                    return "Below T1"
                case 1:
                    return "Between T1–T2"
                case 2:
                    return "Between T2–T3"
                case _:
                    return "Above T3 (Extended)"
        else:
            match self.stage:
                case 0:
                    return "Above T1"
                case 1:
                    return "Between T1–T2"
                case 2:
                    return "Between T2–T3"
                case _:
                    return "Below T3 (Extended)"


def _reset_if_new_day(state: LadderState, trading_date: date) -> LadderState:
    if state.trading_date != trading_date:
        state.trading_date = trading_date
        state.stage = 0
        state.ref_interval = ""
        state.t1 = state.t2 = state.t3 = None
        state.last_price = None
    return state


def _extract_targets(row: Dict[str, Any]) -> Tuple[float, float, float] | None:
    """Read T1/T2/T3 from explicit keys or row['targets'] like ['T1 179.5', ...]."""
    # explicit keys win if present
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
            label = parts[0].upper()   # "T1"
            level = float(parts[1])
            key = label.lower()        # "t1"
            levels[key] = level
        except Exception:
            continue

    t1 = levels.get("t1")
    t2 = levels.get("t2")
    t3 = levels.get("t3")
    if t1 is None or t2 is None or t3 is None:
        return None
    return t1, t2, t3


def _stage_from_price(
    price: float,
    t1: float,
    t2: float,
    t3: float,
    side: str,
) -> Tuple[int, Dict[str, bool]]:
    """Return (stage, hits) for a given price and ladder."""
    side_long = side.upper() != "SHORT"

    def _hit(level: float | None) -> bool:
        if level is None:
            return False
        return price >= level if side_long else price <= level

    hits = {
        "T1": _hit(t1),
        "T2": _hit(t2),
        "T3": _hit(t3),
    }

    if side_long:
        if price < t1:
            stage = 0
        elif price < t2:
            stage = 1
        elif price < t3:
            stage = 2
        else:
            stage = 3
    else:
        if price > t1:
            stage = 0
        elif price > t2:
            stage = 1
        elif price > t3:
            stage = 2
        else:
            stage = 3

    return stage, hits


def augment_targets_state(row: Dict[str, Any], interval: str) -> Dict[str, Any]:
    """Hybrid ladder controller (GLOBAL brain for all TFs).

    • Uses this timeframe's CMP + T1/T2/T3 to compute *local* stage.
    • Updates per-symbol *global* LadderState with priority rules.
    • Writes a unified targets_state + label + dynamic ladder into row.
    """
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

    targets = _extract_targets(row)
    if not targets:
        # Nothing we can do without T1/T2/T3
        return row

    t1, t2, t3 = targets
    row["t1"], row["t2"], row["t3"] = t1, t2, t3  # explicit for UI/exports

    # 1) Local stage based on this interval
    local_stage, _local_hits = _stage_from_price(cmp_val, t1, t2, t3, side)

    # 2) Global ladder lookup / reset (per trading day)
    trading_date = _today_trading_date()
    state = _LADDER.get(symbol) or LadderState(symbol=symbol, trading_date=trading_date)
    state = _reset_if_new_day(state, trading_date)

    # 3) Promotion rules
    global_stage = state.stage
    global_interval = state.ref_interval

    should_promote = False
    if local_stage > global_stage:
        should_promote = True
    elif local_stage == global_stage:
        if _tf_priority(interval) > _tf_priority(global_interval):
            should_promote = True

    if should_promote:
        state.stage = local_stage
        state.ref_interval = interval
        state.t1, state.t2, state.t3 = t1, t2, t3
        state.last_price = cmp_val
        _LADDER[symbol] = state

    # 4) Unified view for this row (based on GLOBAL state)
    label = state.label(side=side)
    _, global_hits = _stage_from_price(
        cmp_val,
        state.t1 or t1,
        state.t2 or t2,
        state.t3 or t3,
        side,
    )

    # 5) Dynamic ladder for THIS timeframe (entry + ATR of this TF)
    atr = (
        row.get("atr_intraday")
        or row.get("atr_intra")
        or row.get("atr_15m")
        or row.get("atr")
        or row.get("ATR")
    )
    entry = row.get("entry") or row.get("entry_price") or cmp_val

    dyn = None
    try:
        if atr is not None and entry is not None:
            atr = float(atr)
            entry = float(entry)
            if side.upper() != "SHORT":
                d_t1 = entry + 0.5 * atr
                d_t2 = entry + 1.0 * atr
                d_t3 = entry + 1.5 * atr
                d_sl = entry - 1.0 * atr
            else:
                d_t1 = entry - 0.5 * atr
                d_t2 = entry - 1.0 * atr
                d_t3 = entry - 1.5 * atr
                d_sl = entry + 1.0 * atr
            dyn = {"t1": d_t1, "t2": d_t2, "t3": d_t3, "sl": d_sl}
    except Exception:
        dyn = None

    # 6) Attach to row
    row["targets_state"] = {
        "stage": state.stage,
        "label": label,
        "ref_interval": state.ref_interval,
        "static": {"t1": t1, "t2": t2, "t3": t3},
        "hits": global_hits,  # {"T1": bool, "T2": bool, "T3": bool}
        "dynamic": dyn,
    }

    # Convenience strings for UI
    row["targets_static_text"] = f"T1 {t1:.1f} · T2 {t2:.1f} · T3 {t3:.1f}"
    if dyn:
        row["targets_dynamic_text"] = (
            f"T1 {dyn['t1']:.1f}{' ✓' if global_hits.get('T1') else ''} · "
            f"T2 {dyn['t2']:.1f}{' ✓' if global_hits.get('T2') else ''} · "
            f"T3 {dyn['t3']:.1f}{' ✓' if global_hits.get('T3') else ''}"
        )
    else:
        row["targets_dynamic_text"] = ""

    # High-level label the card already shows
    row["targets_label"] = label
    return row
