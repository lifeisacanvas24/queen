# queen/services/actionable_row.py
# Single-file actionable-row engine with price-based sizing, capped pyramids,
# add-only-when-green and trailing-stop protection. Generates trade ids per
# entry→exit (Option 1).

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import polars as pl

from queen.helpers.logger import log
from queen.services.cockpit_row import build_cockpit_row

# Optional: strategy overlays (playbook, tv, action_tag, risk_mode)
try:
    from queen.strategies.fusion import apply_strategies as _apply_strategies
except Exception:  # pragma: no cover
    _apply_strategies = None

# Tunables from settings
try:
    from queen.settings.sim_settings import (
        ADD_MIN_UNREAL_PCT,
        ADD_ONLY_WHEN_GREEN,
        MAX_PYRAMID_UNITS,
        MAX_UNITS,
        MIN_UNITS,
        NOTIONAL_PER_UNIT_DEFAULT,
        TRAIL_PCT,
    )
except Exception:  # pragma: no cover
    # sane defaults if settings import fails
    MAX_PYRAMID_UNITS = 3.0
    NOTIONAL_PER_UNIT_DEFAULT = 3_000.0
    TRAIL_PCT = 0.04
    ADD_ONLY_WHEN_GREEN = True
    ADD_MIN_UNREAL_PCT = 0.0
    MIN_UNITS = 1.0
    MAX_UNITS = 50.0


def _to_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def _init_sim_state(sim_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalise / seed the simulation state dict.

    Fields:
      • side          → "FLAT" | "LONG"
      • qty           → synthetic size (can be fractional)
      • avg           → synthetic average entry
      • realized_pnl  → cumulative booked PnL
      • unit_size     → synthetic 'one unit' size for this symbol
      • sim_peak      → peak CMP observed while LONG (for trailing stop)
      • trade_counter → integer used to create trade ids
      • current_trade_id
      • current_trade_skipped_adds
    """
    base = {
        "side": "FLAT",
        "qty": 0.0,
        "avg": None,
        "realized_pnl": 0.0,
        "unit_size": 1.0,
        "sim_peak": None,
        "trade_counter": 0,  # counts trades for this symbol/session
        "current_trade_id": None,
        "current_trade_skipped_adds": 0,
    }
    if not sim_state:
        return base

    out = dict(base)
    out.update({k: v for k, v in sim_state.items() if k in base})
    out["side"] = (out.get("side") or "FLAT").upper()
    out["qty"] = float(out.get("qty") or 0.0)
    out["realized_pnl"] = float(out.get("realized_pnl") or 0.0)
    try:
        out["unit_size"] = float(out.get("unit_size") or 1.0)
    except Exception:
        out["unit_size"] = 1.0

    try:
        out["trade_counter"] = int(out.get("trade_counter") or 0)
    except Exception:
        out["trade_counter"] = 0

    try:
        out["current_trade_skipped_adds"] = int(
            out.get("current_trade_skipped_adds") or 0
        )
    except Exception:
        out["current_trade_skipped_adds"] = 0

    if out.get("sim_peak") is not None:
        try:
            out["sim_peak"] = float(out["sim_peak"])
        except Exception:
            out["sim_peak"] = None
    return out


def _compute_unit_size(
    row: Dict[str, Any],
    *,
    notional_per_unit: float = NOTIONAL_PER_UNIT_DEFAULT,
    min_units: float = MIN_UNITS,
    max_units: float = MAX_UNITS,
) -> float:
    """Price-based synthetic unit sizing.

    Aim: each unit ≈ notional_per_unit rupees of exposure.
    """
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
    """Auto-position simulation — long-only:

    - price-based unit sizing (_compute_unit_size)
    - capped pyramiding (MAX_PYRAMID_UNITS)
    - ADD only when position is profitable (ADD-Only-When-Green)
    - Trailing stop (TRAIL_PCT)
    - Trade bookkeeping: trade_id per entry→exit (Option 1)
    """
    # Defensive keys (diagnostics)
    row.setdefault("sim_forced_eod", False)
    row.setdefault("sim_exit_reason", None)
    row.setdefault("sim_ignored_signal", False)
    row.setdefault("sim_effective_decision", None)
    row.setdefault("sim_skipped_add", 0)
    row.setdefault("sim_trade_id", None)
    row.setdefault("sim_trade_open", False)
    row.setdefault("sim_trade_close", False)

    state = _init_sim_state(sim_state)

    side = state["side"]
    qty = state["qty"]
    avg = state["avg"]
    realized = state["realized_pnl"]
    unit_size = state.get("unit_size", 1.0)
    sim_peak = state.get("sim_peak")
    trade_counter = state.get("trade_counter", 0)
    current_trade_id = state.get("current_trade_id")
    current_trade_skipped_adds = state.get("current_trade_skipped_adds", 0)

    decision = (row.get("decision") or "").upper()
    trade_status = (row.get("trade_status") or "").upper()

    cmp_px = _to_float(row.get("cmp"))
    entry_px = _to_float(row.get("entry")) or cmp_px

    # By default, assume simulator follows original decision; write sim_effective_decision later
    sim_effective_decision = decision
    sim_ignored_signal = False

    # --------------------------------------------------------
    # FLAT -> open
    # --------------------------------------------------------
    if side == "FLAT":
        if decision in {"BUY", "ADD"} and entry_px is not None:
            # New trade: increment counter, create trade id
            trade_counter += 1
            current_trade_id = f"T{trade_counter}"
            current_trade_skipped_adds = 0

            unit_size = _compute_unit_size(row)
            side = "LONG"
            qty = float(unit_size)
            avg = entry_px
            sim_peak = float(cmp_px if cmp_px is not None else entry_px)
            row["sim_exit_reason"] = None

            # mark trade open on this row
            row["sim_trade_id"] = current_trade_id
            row["sim_trade_open"] = True
            row["sim_trade_close"] = False
            row["sim_trade_skipped_adds"] = 0

            sim_effective_decision = decision
            sim_ignored_signal = False

    # --------------------------------------------------------
    # LONG -> possible trail/add/exit
    # --------------------------------------------------------
    elif side == "LONG":
        # update peak
        try:
            if cmp_px is not None:
                if sim_peak is None or cmp_px > sim_peak:
                    sim_peak = float(cmp_px)
        except Exception:
            pass

        # compute current unreal (for ADD-only-when-green)
        current_unreal = None
        current_unreal_pct = None
        try:
            if avg is not None and cmp_px is not None and qty > 0:
                current_unreal = (cmp_px - avg) * qty
                current_unreal_pct = ((cmp_px - avg) / avg * 100.0) if avg else None
        except Exception:
            current_unreal = None
            current_unreal_pct = None

        # Trailing stop evaluation (highest priority)
        if sim_peak is not None and cmp_px is not None:
            try:
                sim_trail_stop = sim_peak * (1.0 - float(TRAIL_PCT))
                row["sim_trail_stop"] = sim_trail_stop
                row["sim_peak"] = sim_peak
                if cmp_px <= sim_trail_stop:
                    # book realized pnl and flatten
                    try:
                        realized += (cmp_px - avg) * qty
                    except Exception:
                        pass
                    row["sim_exit_reason"] = "TRAILING_STOP"
                    row["sim_forced_eod"] = False

                    # mark trade close
                    row["sim_trade_id"] = current_trade_id
                    row["sim_trade_close"] = True
                    row["sim_trade_open"] = False
                    row["sim_trade_skipped_adds"] = current_trade_skipped_adds

                    side = "FLAT"
                    qty = 0.0
                    avg = None
                    sim_peak = None

                    sim_effective_decision = "EXIT"
                    sim_ignored_signal = False
            except Exception:
                pass
        else:
            row.setdefault("sim_trail_stop", None)
            row.setdefault("sim_peak", sim_peak)

        # If still LONG (no trailing-stop exit), consider ADD/HARD_EXIT
        if side == "LONG":
            if decision in {"BUY", "ADD"} and entry_px is not None:
                if unit_size <= 0:
                    unit_size = _compute_unit_size(row)

                # ADD-only-when-green guard
                allow_add = True
                if (
                    ADD_ONLY_WHEN_GREEN
                    and decision == "ADD"
                ):
                    # require current_unreal_pct > ADD_MIN_UNREAL_PCT
                    if current_unreal_pct is None or current_unreal_pct <= float(ADD_MIN_UNREAL_PCT):
                        allow_add = False

                if decision == "ADD" and not allow_add:
                    # Skip averaging down — do not increase qty.
                    current_trade_skipped_adds += 1
                    row["sim_skipped_add"] = int(row.get("sim_skipped_add", 0)) + 1
                    # don't mutate external decision — write sim_ignored_signal
                    sim_ignored_signal = True
                    sim_effective_decision = "NO_ACTION"
                    # annotate trade-level in row (open trade)
                    row["sim_trade_id"] = current_trade_id
                    row["sim_trade_open"] = True
                    row["sim_trade_close"] = False
                    row["sim_trade_skipped_adds"] = current_trade_skipped_adds
                else:
                    # proceed with pyramid (cap to MAX_PYRAMID_UNITS)
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

                    # annotate row trade id/open
                    row["sim_trade_id"] = current_trade_id
                    row["sim_trade_open"] = True
                    row["sim_trade_close"] = False
                    row["sim_trade_skipped_adds"] = current_trade_skipped_adds

                    sim_effective_decision = decision
                    sim_ignored_signal = False

            # Hard exit conditions: explicit EXIT/AVOID or broker trade_status == EXIT
            hard_exit = (decision in {"EXIT", "AVOID"}) or (trade_status == "EXIT")
            exit_signal = hard_exit or eod_force

            if exit_signal and cmp_px is not None and avg is not None and qty > 0:
                try:
                    realized += (cmp_px - avg) * qty
                except Exception:
                    pass

                # mark trade close
                row["sim_trade_id"] = current_trade_id
                row["sim_trade_close"] = True
                row["sim_trade_open"] = False
                row["sim_trade_skipped_adds"] = current_trade_skipped_adds

                if eod_force:
                    row["sim_forced_eod"] = True
                    row["sim_exit_reason"] = "EOD_FORCED"
                else:
                    row["sim_forced_eod"] = False
                    row["sim_exit_reason"] = "HARD_EXIT"

                # reset state trade info
                current_trade_id = None
                current_trade_skipped_adds = 0

                side = "FLAT"
                qty = 0.0
                avg = None
                sim_peak = None

                sim_effective_decision = "EXIT"
                sim_ignored_signal = False

    # --------------------------------------------------------
    # Post-transition: compute unreal + totals
    # --------------------------------------------------------
    unreal = None
    unreal_pct = None
    if side == "LONG" and cmp_px is not None and avg is not None and qty > 0:
        try:
            unreal = (cmp_px - avg) * qty
            unreal_pct = (cmp_px - avg) / avg * 100.0
        except Exception:
            pass

    total_pnl = None
    try:
        total_pnl = (unreal or 0.0) + (realized or 0.0)
    except Exception:
        total_pnl = unreal or realized

    # --------------------------------------------------------
    # Write synthetic fields (diagnostics & persistence)
    # --------------------------------------------------------
    row["sim_side"] = side
    row["sim_qty"] = float(qty)
    row["sim_avg"] = avg
    row["sim_pnl"] = unreal
    row["sim_pnl_pct"] = unreal_pct
    row["sim_realized_pnl"] = realized
    row["sim_total_pnl"] = total_pnl

    row["sim_unit_size"] = float(unit_size)
    row["sim_peak"] = sim_peak
    row.setdefault("sim_trail_stop", row.get("sim_trail_stop"))

    # trade bookkeeping fields
    row["sim_trade_id"] = row.get("sim_trade_id") or current_trade_id
    row["sim_trade_open"] = bool(row.get("sim_trade_open", False))
    row["sim_trade_close"] = bool(row.get("sim_trade_close", False))
    row["sim_trade_skipped_adds"] = int(row.get("sim_trade_skipped_adds", 0))

    # sim effect / ignored signal (do NOT mutate original 'decision')
    row["sim_effective_decision"] = sim_effective_decision or None
    row["sim_ignored_signal"] = bool(sim_ignored_signal)

    # expose how many adds skipped on this row (helpful)
    row.setdefault("sim_skipped_add", row.get("sim_skipped_add", 0))

    # Persist next_state (important: keep trade_counter & current trade info)
    next_state: Dict[str, Any] = {
        "side": side,
        "qty": float(qty),
        "avg": avg,
        "realized_pnl": realized,
        "unit_size": float(unit_size),
        "sim_peak": sim_peak,
        "trade_counter": int(trade_counter),
        "current_trade_id": current_trade_id,
        "current_trade_skipped_adds": int(current_trade_skipped_adds),
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
    """Build a unified actionable row. Sim runs only when pos_mode == 'auto'."""
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
            log.exception(
                f"[build_actionable_row] strategy overlay failed → {symbol}: {e}"
            )

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
