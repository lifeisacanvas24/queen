# queen/services/actionable_row.py
#!/usr/bin/env python3
"""Unified actionable-row engine with integrated synthetic simulator (long-only).
Features:
 - price-based unit sizing (_compute_unit_size)
 - capped pyramiding (MAX_PYRAMID_UNITS)
 - ADD-only-when-green (ADD_ONLY_WHEN_GREEN + ADD_MIN_UNREAL_PCT)
 - trailing stop protection (TRAIL_PCT)
 - trade_id generation and per-row sim fields:
     sim_trade_id, sim_effective_decision, sim_ignored_signal,
     sim_skipped_add (per-row), sim_skip_reason, sim_trail_stop, sim_peak
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import polars as pl  # used by other parts; keep import for consistency

from queen.helpers.logger import log
from queen.services.cockpit_row import build_cockpit_row

# optional: apply strategy overlays (playbook / tv / action_tag / risk_mode)
try:
    from queen.strategies.fusion import apply_strategies as _apply_strategies
except Exception:  # pragma: no cover
    _apply_strategies = None

# sim tunables (centralized)
from queen.settings.sim_settings import (
    ADD_MIN_UNREAL_PCT,
    ADD_ONLY_WHEN_GREEN,
    MAX_PYRAMID_UNITS,
    NOTIONAL_PER_UNIT_DEFAULT,
    SIM_MAX_UNITS,
    SIM_MIN_UNITS,
    TRAIL_PCT,
)


def _to_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def _init_sim_state(sim_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalise / seed simulation state that persists between bars."""
    base = {
        "side": "FLAT",              # current synthetic side
        "qty": 0.0,
        "avg": None,
        "realized_pnl": 0.0,
        "unit_size": 1.0,
        "sim_peak": None,
        # trade id management
        "next_trade_id": 1,         # integer trade id generator
        "current_trade_id": None,   # active trade id while LONG
    }
    if not sim_state:
        return base
    out = dict(base)
    out.update({k: v for k, v in sim_state.items() if k in base})
    out["side"] = (out.get("side") or "FLAT").upper()
    out["qty"] = float(out.get("qty") or 0.0)
    try:
        out["unit_size"] = float(out.get("unit_size") or 1.0)
    except Exception:
        out["unit_size"] = 1.0
    if out.get("sim_peak") is not None:
        try:
            out["sim_peak"] = float(out["sim_peak"])
        except Exception:
            out["sim_peak"] = None
    try:
        out["next_trade_id"] = int(out.get("next_trade_id") or 1)
    except Exception:
        out["next_trade_id"] = 1
    # current_trade_id may be None or int
    if out.get("current_trade_id") is not None:
        try:
            out["current_trade_id"] = int(out["current_trade_id"])
        except Exception:
            out["current_trade_id"] = None
    return out


def _compute_unit_size(
    row: Dict[str, Any],
    *,
    notional_per_unit: float = NOTIONAL_PER_UNIT_DEFAULT,
    min_units: float = SIM_MIN_UNITS,
    max_units: float = SIM_MAX_UNITS,
) -> float:
    """Price-based synthetic unit sizing: aim for notional exposure per unit."""
    cmp_px = _to_float(row.get("cmp") or row.get("entry"))
    if cmp_px is None or cmp_px <= 0:
        return float(min_units)
    raw = notional_per_unit / cmp_px
    try:
        units = float(max(1, int(raw)))
    except Exception:
        units = raw
    if units < min_units:
        units = min_units
    if units > max_units:
        units = max_units
    return float(units)


def _step_auto_long_sim(
    row: Dict[str, Any],
    sim_state: Optional[Dict[str, Any]],
    *,
    eod_force: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Auto-position long-only simulator with trade_id + diagnostics."""
    # Ensure diagnostic keys exist
    row.setdefault("sim_forced_eod", False)
    row.setdefault("sim_exit_reason", None)
    row.setdefault("sim_skipped_add", 0)
    row.setdefault("sim_skip_reason", None)
    row.setdefault("sim_ignored_signal", False)

    state = _init_sim_state(sim_state)

    side = state["side"]
    qty = state["qty"]
    avg = state["avg"]
    realized = state["realized_pnl"]
    unit_size = state.get("unit_size", 1.0)
    sim_peak = state.get("sim_peak")
    next_trade_id = state.get("next_trade_id", 1)
    current_trade_id = state.get("current_trade_id")

    decision_in = (row.get("decision") or "").upper()
    trade_status = (row.get("trade_status") or "").upper()

    cmp_px = _to_float(row.get("cmp"))
    entry_px = _to_float(row.get("entry")) or cmp_px

    # default effective decision mirrors incoming one; we'll set sim_effective_decision
    sim_effective_decision = decision_in
    sim_ignored_signal = False
    sim_skipped_add = 0

    # ---------- FLAT => open ----------
    if side == "FLAT":
        if decision_in in {"BUY", "ADD"} and entry_px is not None:
            unit_size = _compute_unit_size(row)
            side = "LONG"
            qty = float(unit_size)
            avg = entry_px
            sim_peak = float(cmp_px if cmp_px is not None else entry_px)
            # new trade id assigned on entry
            current_trade_id = int(next_trade_id)
            next_trade_id += 1
            sim_effective_decision = "BUY"
            row["sim_exit_reason"] = None

    # ---------- LONG ----------
    elif side == "LONG":
        # update peak
        try:
            if cmp_px is not None:
                if sim_peak is None or cmp_px > sim_peak:
                    sim_peak = float(cmp_px)
        except Exception:
            pass

        # compute current unreal (absolute and percent)
        current_unreal = None
        current_unreal_pct = None
        try:
            if avg is not None and cmp_px is not None and qty > 0:
                current_unreal = (cmp_px - avg) * qty
                current_unreal_pct = (cmp_px - avg) / avg * 100.0
        except Exception:
            current_unreal = None
            current_unreal_pct = None

        # trailing stop (highest priority)
        if sim_peak is not None and cmp_px is not None:
            try:
                sim_trail_stop = sim_peak * (1.0 - float(TRAIL_PCT))
                row["sim_trail_stop"] = sim_trail_stop
                row["sim_peak"] = sim_peak
                if cmp_px <= sim_trail_stop:
                    # book realized pnl and flatten trade
                    try:
                        realized += (cmp_px - avg) * qty
                    except Exception:
                        pass
                    row["sim_exit_reason"] = "TRAILING_STOP"
                    row["sim_forced_eod"] = False
                    sim_effective_decision = "EXIT"
                    side = "FLAT"
                    # stamp trade_id on exit row before clearing
                    row["sim_trade_id"] = current_trade_id
                    current_trade_id = None
                    qty = 0.0
                    avg = None
                    sim_peak = None
                    # done with this bar
            except Exception:
                pass
        else:
            row.setdefault("sim_trail_stop", None)
            row.setdefault("sim_peak", sim_peak)

        # Still LONG? consider ADD/BUY or hard exit
        if side == "LONG":
            if decision_in in {"BUY", "ADD"} and entry_px is not None:
                # refresh unit size if invalid
                if unit_size <= 0:
                    unit_size = _compute_unit_size(row)

                # ADD-only-when-green checks
                allow_add = True
                if decision_in == "ADD" and ADD_ONLY_WHEN_GREEN:
                    # require positive unreal AND at least ADD_MIN_UNREAL_PCT (percentage)
                    if current_unreal is None or current_unreal <= 0.0:
                        allow_add = False
                    else:
                        if ADD_MIN_UNREAL_PCT and current_unreal_pct is not None:
                            if current_unreal_pct < float(ADD_MIN_UNREAL_PCT):
                                allow_add = False

                if decision_in == "ADD" and not allow_add:
                    # mark as ignored for sim
                    sim_ignored_signal = True
                    sim_skipped_add = 1
                    sim_effective_decision = "NO_ACTION"
                    row["sim_skip_reason"] = "ADD_SKIPPED_NOT_IN_PROFIT"
                    # don't mutate incoming decision; create sim_effective_decision instead
                else:
                    # perform pyramid (cap by MAX_PYRAMID_UNITS * unit_size)
                    prev_qty = qty
                    desired_new_qty = qty + float(unit_size)
                    max_qty_allowed = float(unit_size) * float(MAX_PYRAMID_UNITS)
                    if prev_qty >= max_qty_allowed:
                        new_qty = prev_qty
                    else:
                        new_qty = min(desired_new_qty, max_qty_allowed)
                    added_qty = new_qty - prev_qty
                    if new_qty > 0 and added_qty > 0:
                        try:
                            prev_avg = avg if (avg is not None) else entry_px
                            avg = ((prev_avg * prev_qty) + (entry_px * added_qty)) / new_qty
                        except Exception:
                            avg = entry_px
                        qty = new_qty
                    sim_effective_decision = decision_in

            # hard exits (explicit EXIT/AVOID or trade_status == 'EXIT')
            hard_exit = (decision_in in {"EXIT", "AVOID"}) or (trade_status == "EXIT")
            exit_signal = hard_exit or eod_force
            if exit_signal and cmp_px is not None and avg is not None and qty > 0:
                try:
                    realized += (cmp_px - avg) * qty
                except Exception:
                    pass
                if eod_force:
                    row["sim_forced_eod"] = True
                    row["sim_exit_reason"] = "EOD_FORCED"
                else:
                    row["sim_forced_eod"] = False
                    row["sim_exit_reason"] = "HARD_EXIT"
                sim_effective_decision = "EXIT"
                # stamp trade id on exit
                row["sim_trade_id"] = current_trade_id
                current_trade_id = None
                side = "FLAT"
                qty = 0.0
                avg = None
                sim_peak = None

    # write per-row sim fields (after processing)
    row["sim_side"] = side
    row["sim_qty"] = float(qty)
    row["sim_avg"] = avg
    # unrealised p&l
    unreal = None
    unreal_pct = None
    if side == "LONG" and cmp_px is not None and avg is not None and qty > 0:
        try:
            unreal = (cmp_px - avg) * qty
            unreal_pct = (cmp_px - avg) / avg * 100.0
        except Exception:
            pass
    row["sim_pnl"] = unreal
    row["sim_pnl_pct"] = unreal_pct
    row["sim_realized_pnl"] = realized
    try:
        row["sim_total_pnl"] = (unreal or 0.0) + (realized or 0.0)
    except Exception:
        row["sim_total_pnl"] = unreal or realized

    # sim_trade_id: if currently in trade, set it for the row (entry/holds)
    if current_trade_id is not None:
        row["sim_trade_id"] = int(current_trade_id)
    else:
        # if not set by exit logic, ensure key present (None)
        row.setdefault("sim_trade_id", None)

    # sim_effective_decision / ignored flag / skipped_add tally (per-row)
    row["sim_effective_decision"] = sim_effective_decision or None
    row["sim_ignored_signal"] = bool(sim_ignored_signal)
    row["sim_skipped_add"] = int(sim_skipped_add or 0)

    # expose unit size / peak / trail stop for observability
    row["sim_unit_size"] = float(unit_size)
    row["sim_peak"] = sim_peak
    row.setdefault("sim_trail_stop", row.get("sim_trail_stop"))

    # prepare next_state
    next_state: Dict[str, Any] = {
        "side": side,
        "qty": float(qty),
        "avg": avg,
        "realized_pnl": realized,
        "unit_size": float(unit_size),
        "sim_peak": sim_peak,
        "next_trade_id": int(next_trade_id),
        "current_trade_id": int(current_trade_id) if current_trade_id is not None else None,
    }
    return row, next_state


def build_actionable_row(
    symbol: str,
    df: pl.DataFrame,
    *,
    interval: str,
    book: str,
    pos_mode: str = "flat",
    auto_side: str = "long",
    positions_map: Dict[str, Any] | None = None,
    cmp_anchor: float | None = None,
    pos: Optional[Dict[str, Any]] = None,
    sim_state: Dict[str, Any] | None = None,
    eod_force: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    """Build actionable row and optionally run the synthetic sim when pos_mode == 'auto'."""
    if df is None or getattr(df, "is_empty", lambda: True)():
        return {}, sim_state

    eff_pos = None
    if pos_mode == "live" and positions_map:
        eff_pos = positions_map.get(symbol)

    try:
        row = build_cockpit_row(
            symbol,
            df,
            interval=interval,
            book=book,
            tactical=None,
            pattern=None,
            reversal=None,
            volatility=None,
            pos=eff_pos or pos,
        ) or {}
    except Exception as e:
        log.exception(f"[build_actionable_row] cockpit_row failed → {symbol}: {e}")
        return {}, sim_state

    if not row:
        return {}, sim_state

    if cmp_anchor is not None:
        try:
            row["cmp"] = float(cmp_anchor)
        except Exception:
            pass

    if _apply_strategies is not None:
        try:
            row = _apply_strategies(
                row,
                interval=interval,
                phase=row.get("time_bucket"),
                risk=row.get("risk_mode"),
            )
        except Exception as e:
            log.exception(f"[build_actionable_row] strategy overlay failed → {symbol}: {e}")

    row["held"] = bool(eff_pos)

    next_sim_state = sim_state
    if pos_mode == "auto" and auto_side == "long":
        try:
            row, next_sim_state = _step_auto_long_sim(
                row,
                sim_state,
                eod_force=eod_force,
            )
        except Exception as e:
            log.exception(f"[build_actionable_row] auto-sim failed → {symbol}: {e}")

    return row, next_sim_state
