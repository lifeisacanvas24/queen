#!/usr/bin/env python3
# ============================================================
# queen/services/actionable_row.py — v1.5
# ------------------------------------------------------------
# Single entrypoint for building an actionable row + synthetic
# simulator state used by:
#   • monitor/actionable (via API layer)
#   • cli/replay_actionable.py
#   • cli/scan_signals.py
#   • cli/debug_decisions.py
#
# Core ideas:
#   • Engine decides: decision, bias, score, drivers, etc.
#   • This module:
#         - Normalizes decisions (BUY, ADD, EXIT, SELL, ADD_SHORT,
#           EXIT_SHORT, HOLD, AVOID)
#         - Applies agreed sim semantics for pos_mode="auto"
#         - Attaches sim_* fields:
#              sim_side, sim_qty, sim_avg,
#              sim_pnl, sim_pnl_pct,
#              sim_realized_pnl, sim_total_pnl
#         - Applies ladder/heat guardrails in R-space (v1.5)
#!/usr/bin/env python3
# ============================================================
# queen/services/actionable_row.py — v1.2 (excerpt)
# ------------------------------------------------------------
# Wires:
#   • TradeState  → R metrics (open_R, peak_R, max_dd_R)
#   • LadderContext → ladder_guardrails.apply_ladder_guardrails
# ============================================================

from __future__ import annotations


from queen.services.trade_state import TradeState, update_trade_state
from queen.services.ladder_guardrails import LadderContext, apply_ladder_guardrails


from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

import polars as pl

from queen.helpers.logger import log
from queen.services.ladder_guardrails import LadderContext, apply_ladder_guardrails
from queen.services.scoring import (
    action_for as _scoring_action_for,
    compute_indicators_plus_bible,
)
from queen.services.trade_state import TradeState, update_trade_state
from queen.settings.sim_settings import PositionSide

SimSide = Literal["FLAT", "LONG", "SHORT"]


# ----------------- sim state -----------------


@dataclass
class SimState:
    side: SimSide = "FLAT"
    qty: float = 0.0
    avg: float = 0.0
    realized_pnl: float = 0.0


def _state_from_dict(d: Optional[Dict[str, Any]]) -> SimState:
    if not d:
        return SimState()
    return SimState(
        side=d.get("side", "FLAT"),
        qty=float(d.get("qty", 0.0) or 0.0),
        avg=float(d.get("avg", 0.0) or 0.0),
        realized_pnl=float(d.get("realized_pnl", 0.0) or 0.0),
    )


# ----------------- per-symbol trade + ladder meta -----------------

# R-space state: per (symbol, side)
_TRADE_STATE: Dict[Tuple[str, str], TradeState] = {}
# Keyed per synthetic trade, e.g. (symbol, interval, side, sim_trade_id)
_TRADE_STATE_REGISTRY: Dict[Tuple[str, str, str, int], TradeState] = {}

# Ladder meta: per (symbol, side): ladder_adds, last_add_price
_LADDER_META: Dict[Tuple[str, str], Dict[str, Any]] = {}


# ----------------- decision helpers -----------------


_LONG_ENTRIES = {"BUY", "ADD"}
_LONG_EXIT = "EXIT"

_SHORT_ENTRIES = {"SELL", "ADD_SHORT"}
_SHORT_EXIT = "EXIT_SHORT"

_HOLD_TOKENS = {"HOLD"}
_AVOID_TOKENS = {"AVOID"}


def _normalize_dec(dec: Any) -> str:
    if dec is None:
        return ""
    return str(dec).strip().upper()

def _update_r_geometry_for_row(row) -> TradeState:
    """
    Update TradeState for this symbol/interval/side/trade_id using the
    latest cmp/entry/sl and return the state.
    """
    symbol = row["symbol"]
    interval = row["interval"]
    side = row["sim_side"]          # "LONG" / "SHORT" (or PositionSide)
    trade_id = int(row["sim_trade_id"])

    key = (symbol, interval, str(side), trade_id)

    state = _TRADE_STATE_REGISTRY.get(key)
    if state is None:
        state = TradeState(symbol=symbol, side=side)
        _TRADE_STATE_REGISTRY[key] = state

    # Geometry from row (you already have these in the Parquet)
    cmp_ = float(row["cmp"])
    entry_price = float(row["entry"])
    sl_price = float(row["sl"])

    state = update_trade_state(
        state,
        cmp_=cmp_,
        entry_price=entry_price,
        sl_price=sl_price,
    )
    _TRADE_STATE_REGISTRY[key] = state
    return state

def _is_long_entry(dec: str) -> bool:
    return dec in _LONG_ENTRIES


def _is_short_entry(dec: str) -> bool:
    return dec in _SHORT_ENTRIES


def _is_long_exit(dec: str) -> bool:
    return dec == _LONG_EXIT


def _is_short_exit(dec: str) -> bool:
    return dec == _SHORT_EXIT


def _is_hold(dec: str) -> bool:
    return dec in _HOLD_TOKENS


def _is_avoid(dec: str) -> bool:
    return dec in _AVOID_TOKENS


# ----------------- ENGINE ADAPTER (wired to scoring.py) -----------------


def _engine_build_base_row(
    *,
    symbol: str,
    df: pl.DataFrame,
    interval: str,
    book: str,
    cmp_anchor: Optional[float] = None,  # kept for forward-compat; not used yet
) -> Dict[str, Any]:
    """Adapter that calls your existing scoring pipeline:

        1) compute_indicators_plus_bible(df, interval, symbol)  → indd
        2) action_for(symbol, indd, book)                       → cockpit row

    Returns a plain dict containing at least:
        • decision  (BUY / ADD / EXIT / SELL / ADD_SHORT / EXIT_SHORT / HOLD / AVOID)
        • cmp       (last price)
        • any other fields you already expose today:
              bias, score, drivers, cpr_ctx, tv_ctx, regime, etc.
    """
    indd = compute_indicators_plus_bible(
        df,
        interval=interval,
        symbol=symbol,
        pos=None,
    )
    if not isinstance(indd, dict):
        raise TypeError(
            f"[actionable_row] compute_indicators_plus_bible() returned "
            f"unsupported type: {type(indd)!r}"
        )

    ctx = _scoring_action_for(
        symbol=symbol,
        indd=indd,
        book=book,
        use_uc_lc=True,
    )

    if isinstance(ctx, dict):
        base = dict(ctx)
    elif hasattr(ctx, "model_dump"):
        base = ctx.model_dump()
    elif hasattr(ctx, "__dict__"):
        base = dict(ctx.__dict__)
    else:
        raise TypeError(
            f"[actionable_row] action_for() returned unsupported type: {type(ctx)!r}"
        )

    log.debug(
        f"[actionable_row] engine base row for {symbol} @{interval}: "
        f"decision={base.get('decision')} cmp={base.get('cmp')}"
    )
    return base


# ----------------- SIM CORE -----------------
def _apply_guardrails_for_row(row, raw_decision: str) -> str:
    """
    Take the raw engine decision for this row and apply ladder/heat guardrails.
    """
    # 1) Update R metrics for this trade
    ts = _update_r_geometry_for_row(row)

    # 2) Build LadderContext from sim_* + TradeState
    ctx = LadderContext(
        side=str(row["sim_side"]),          # "LONG" / "SHORT"
        sim_qty=float(row["sim_qty"]),      # current synthetic qty
        ladder_adds=int(row["sim_adds"]),   # how many adds so far

        open_R=float(ts.open_R),
        peak_R=float(ts.peak_open_R),
        max_dd_R=float(ts.max_dd_R),

        entry_price=float(ts.entry_price) if ts.entry_price else None,
        last_add_price=float(row["sim_last_add_price"]) if "sim_last_add_price" in row else None,
        cmp=float(row["cmp"]),
    )

    # 3) Apply guardrails
    adj_decision, reasons = apply_ladder_guardrails(raw_decision, ctx)

    # Optional: store reasons into row for debug
    row["guardrail_decision"] = adj_decision
    row["guardrail_reasons"] = "; ".join(reasons) if reasons else ""

    return adj_decision

def _apply_sim_step(
    decision: str,
    cmp_val: float,
    auto_side: str,
    state: SimState,
) -> SimState:
    """Apply one decision to sim state under agreed semantics:

        • AVOID = entry filter (never exits, never opens/adds)
        • HOLD  = maintain position (never opens/exits/adds)
        • LONG entries:  BUY / ADD
        • LONG exit:     EXIT
        • SHORT entries: SELL / ADD_SHORT
        • SHORT exit:    EXIT_SHORT

    auto_side:
        "long"  → ignore short vocab for sim
        "short" → ignore long vocab for sim
        "both"  → accept both
    """
    dec = decision
    side = state.side
    qty = state.qty
    avg = state.avg
    realized = state.realized_pnl

    # Guardrails for auto_side — ignore opposite-side vocab.
    if auto_side == "long" and (dec in _SHORT_ENTRIES or dec == _SHORT_EXIT):
        return state
    if auto_side == "short" and (dec in _LONG_ENTRIES or dec == _LONG_EXIT):
        return state

    # 1) HOLD / AVOID → never change position
    if _is_hold(dec) or _is_avoid(dec):
        return state

    # 2) LONG entries / exit
    if _is_long_entry(dec):
        if side in ("FLAT", "LONG"):
            new_qty = qty + 1
            new_avg = ((avg * qty) + cmp_val) / new_qty if new_qty > 0 else cmp_val
            return SimState(side="LONG", qty=new_qty, avg=new_avg, realized_pnl=realized)
        return state

    if _is_long_exit(dec):
        if side == "LONG" and qty > 0:
            realized += (cmp_val - avg) * qty
        return SimState(side="FLAT", qty=0.0, avg=0.0, realized_pnl=realized)

    # 3) SHORT entries / exit
    if _is_short_entry(dec):
        if side in ("FLAT", "SHORT"):
            new_qty = qty + 1
            new_avg = ((avg * qty) + cmp_val) / new_qty if new_qty > 0 else cmp_val
            return SimState(side="SHORT", qty=new_qty, avg=new_avg, realized_pnl=realized)
        return state

    if _is_short_exit(dec):
        if side == "SHORT" and qty > 0:
            realized += (avg - cmp_val) * qty
        return SimState(side="FLAT", qty=0.0, avg=0.0, realized_pnl=realized)

    # Any unknown decision → no change
    return state


def _compute_unrealized(
    side: SimSide,
    qty: float,
    avg: float,
    cmp_val: float,
) -> float:
    if side == "LONG" and qty > 0:
        return (cmp_val - avg) * qty
    if side == "SHORT" and qty > 0:
        return (avg - cmp_val) * qty
    return 0.0


# ----------------- PUBLIC ENTRYPOINT -----------------
def build_actionable_row(
    *,
    symbol: str,
    df: pl.DataFrame,
    interval: str,
    book: str = "all",
    pos_mode: str = "flat",          # "flat" | "live" | "auto"
    auto_side: str = "both",         # "long" | "short" | "both"
    positions_map: Optional[Dict[str, Any]] = None,
    cmp_anchor: Optional[float] = None,
    sim_state: Optional[Dict[str, Any]] = None,
    eod_force: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Main orchestrator used by:
        • monitor/actionable
        • cli/replay_actionable.py
        • cli/scan_signals.py
        • cli/debug_decisions.py

    Returns:
        (row, new_sim_state_dict)
    """
    if df.is_empty():
        return {}, sim_state or {}

    symbol_u = str(symbol).upper()

    # 1) Engine decision (via scoring pipeline)
    base = _engine_build_base_row(
        symbol=symbol_u,
        df=df,
        interval=interval,
        book=book,
        cmp_anchor=cmp_anchor,
    )

    # Ensure cmp is available
    if "cmp" in base and base["cmp"] is not None:
        cmp_val = float(base["cmp"])
    else:
        try:
            cmp_val = float(df["close"].tail(1).item())
        except Exception:
            cmp_val = float(df.select("close").tail(1)[0, 0])
        base["cmp"] = cmp_val

    decision = _normalize_dec(base.get("decision"))
    cmp_val = float(base["cmp"])

    # 2) Position mode handling
    if pos_mode not in {"flat", "live", "auto"}:
        log.warning(
            f"[actionable_row] Unknown pos_mode={pos_mode!r}, defaulting to 'flat'"
        )
        pos_mode = "flat"

    # Previous sim state for this symbol in this replay
    state = _state_from_dict(sim_state)
    prev_state = state

    # 2a) EOD force only in auto-mode
    if pos_mode == "auto" and eod_force:
        if state.side == "LONG" and state.qty > 0:
            decision = _LONG_EXIT
        elif state.side == "SHORT" and state.qty > 0:
            decision = _SHORT_EXIT

    # 2b) R-space state before taking new action (only in auto-mode)
    trade_state: Optional[TradeState] = None
    ladder_meta: Dict[str, Any] = {"ladder_adds": 0, "last_add_price": None}

    if pos_mode == "auto":
        # Map sim side into PositionSide enum; guard against invalid values
        try:
            side_enum = PositionSide(prev_state.side)
        except ValueError:
            side_enum = PositionSide.FLAT

        if side_enum != PositionSide.FLAT:
            key = (symbol_u, side_enum.value)

            trade_state = _TRADE_STATE.get(key) or TradeState(
                symbol=symbol_u,
                side=side_enum,
            )

            entry_px = base.get("entry") or cmp_val
            sl_px = base.get("sl") or cmp_val

            trade_state = update_trade_state(
                trade_state,
                cmp_=cmp_val,
                entry_price=float(entry_px),
                sl_price=float(sl_px),
            )
            _TRADE_STATE[key] = trade_state

            ladder_meta = _LADDER_META.get(key) or {
                "ladder_adds": 0,
                "last_add_price": None,
            }
            _LADDER_META[key] = ladder_meta
        else:
            trade_state = None

    # 2c) Apply ladder/heat guardrails (auto-mode only)
    if pos_mode == "auto":
        # Decide side for context:
        if prev_state.side in ("LONG", "SHORT"):
            ctx_side = prev_state.side
        elif decision in _LONG_ENTRIES | {_LONG_EXIT}:
            ctx_side = "LONG"
        elif decision in _SHORT_ENTRIES | {_SHORT_EXIT}:
            ctx_side = "SHORT"
        else:
            ctx_side = "LONG"  # safe default

        ctx = LadderContext(
            side=ctx_side,
            sim_qty=float(prev_state.qty),
            ladder_adds=int(ladder_meta.get("ladder_adds", 0)),
            open_R=float(getattr(trade_state, "open_R", 0.0) or 0.0),
            peak_R=float(getattr(trade_state, "peak_open_R", 0.0) or 0.0),
            max_dd_R=float(getattr(trade_state, "max_dd_R", 0.0) or 0.0),
            entry_price=(
                getattr(trade_state, "entry_price", None) if trade_state else None
            ),
            last_add_price=ladder_meta.get("last_add_price", None),
            cmp=cmp_val,
        )

        adjusted_decision, reasons = apply_ladder_guardrails(decision, ctx)

        base["decision_raw"] = decision
        base["sim_guardrails"] = reasons
        decision_used = adjusted_decision
    else:
        base["decision_raw"] = decision
        base["sim_guardrails"] = []
        decision_used = decision

    # 2d) Apply synthetic sim in auto-mode with final decision
    if pos_mode == "auto":
        state = _apply_sim_step(
            decision_used,
            cmp_val,
            auto_side=auto_side,
            state=prev_state,
        )

        # Update ladder meta based on executed action
        prev_side = prev_state.side
        new_side = state.side

        # If we are flat now, clear R-space & ladder state
        if new_side == "FLAT" or state.qty <= 0:
            if prev_side in ("LONG", "SHORT"):
                key_prev = (symbol_u, prev_side)
                _TRADE_STATE.pop(key_prev, None)
                _LADDER_META.pop(key_prev, None)
        else:
            # We have an open position
            key_new = (symbol_u, new_side)
            lm = _LADDER_META.get(key_new) or {
                "ladder_adds": 0,
                "last_add_price": None,
            }

            # Treat true ADDs as any size increase while already in trade
            did_add_here = (
                prev_side == new_side
                and prev_state.qty > 0
                and state.qty > prev_state.qty
                and decision_used in ("ADD", "ADD_SHORT", "BUY", "SELL")
            )
            if did_add_here:
                lm["ladder_adds"] = int(lm.get("ladder_adds", 0)) + 1
                lm["last_add_price"] = cmp_val

            _LADDER_META[key_new] = lm
    else:
        # pos_mode == "flat" / "live": no internal sim
        state = prev_state

    # 3) PnL math
    unrealized = _compute_unrealized(state.side, state.qty, state.avg, cmp_val)
    total_pnl = state.realized_pnl + unrealized
    notional = abs(state.avg) * state.qty
    pnl_pct = (total_pnl / notional * 100.0) if notional > 0 else 0.0

    # 4) Attach sim fields; decision gets the risk-managed one in base
    base["decision"] = decision_used

    row = dict(base)
    row["sim_side"] = state.side
    row["sim_qty"] = state.qty
    row["sim_avg"] = round(state.avg, 4) if state.avg else 0.0
    row["sim_pnl"] = round(unrealized, 2)
    row["sim_pnl_pct"] = round(pnl_pct, 2)
    row["sim_realized_pnl"] = round(state.realized_pnl, 2)
    row["sim_total_pnl"] = round(total_pnl, 2)

    return row, asdict(state)

# ----------------- DEBUG DEMO HELPER -----------------
# Used only by queen/cli/debug_decisions.py
# -----------------------------------------------------


def simulate_rows_for_symbol(*args, **kwargs) -> List[Dict[str, Any]]:
    """Small deterministic demo used by debug_decisions.py.

    We intentionally accept *args/**kwargs so the helper stays compatible
    even if the caller's signature changes (symbol, interval, etc.).
    """
    symbol = kwargs.get("symbol", "DEMO")
    auto_side = kwargs.get("auto_side", "both")

    script = [
        ("2025-01-01T09:30:00", "BUY",        100.0),
        ("2025-01-01T09:40:00", "HOLD",       102.0),
        ("2025-01-01T09:50:00", "AVOID",      104.0),
        ("2025-01-01T10:00:00", "ADD",        103.0),
        ("2025-01-01T10:10:00", "EXIT",       106.0),
        ("2025-01-01T10:20:00", "SELL",       105.0),
        ("2025-01-01T10:30:00", "HOLD",       103.0),
        ("2025-01-01T10:40:00", "AVOID",      102.0),
        ("2025-01-01T10:50:00", "EXIT_SHORT", 104.0),
    ]

    rows: List[Dict[str, Any]] = []
    state = SimState()

    for ts, dec, cmp_val in script:
        state = _apply_sim_step(dec, cmp_val, auto_side=auto_side, state=state)

        unrealized = _compute_unrealized(state.side, state.qty, state.avg, cmp_val)
        total_pnl = state.realized_pnl + unrealized
        notional = abs(state.avg) * state.qty
        pnl_pct = (total_pnl / notional * 100.0) if notional > 0 else 0.0

        rows.append(
            {
                "timestamp": ts,
                "symbol": symbol,
                "decision": dec,
                "cmp": cmp_val,
                "sim_side": state.side,
                "sim_qty": state.qty,
                "sim_avg": round(state.avg, 2),
                "sim_pnl": round(unrealized, 2),
                "sim_pnl_pct": round(pnl_pct, 2),
                "sim_realized_pnl": round(state.realized_pnl, 2),
                "sim_total_pnl": round(total_pnl, 2),
            }
        )

    return rows
