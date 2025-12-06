#!/usr/bin/env python3
# ============================================================
# queen/services/trade_state.py — v1.1
# ------------------------------------------------------------
# Maintains per-trade R-space geometry for guardrails:
#   • open_R        → current R relative to entry & SL
#   • peak_open_R   → highest open_R seen so far
#   • max_dd_R      → largest drawdown from peak in R
#
# Called on every actionable_row in pos_mode="auto".
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union, Any


@dataclass
class TradeState:
    symbol: str
    side: Any  # PositionSide enum ("LONG" / "SHORT") or plain "LONG"/"SHORT" str

    # reference geometry
    entry_price: float = 0.0
    sl_price: float = 0.0

    # dynamic R metrics
    open_R: float = 0.0        # current R
    peak_open_R: float = 0.0   # best open_R seen so far
    max_dd_R: float = 0.0      # max drawdown in R: peak_open_R - lowest open_R


def _side_to_str(side: Any) -> str:
    """Normalize side to 'LONG' / 'SHORT' / ''."""
    if side is None:
        return ""
    if hasattr(side, "value"):
        return str(side.value).upper()
    return str(side).upper()


def _compute_R(side: str, cmp_: float, entry_price: float, sl_price: float) -> float:
    """
    Compute R-space value for LONG or SHORT.

        LONG:  R = (cmp - entry) / (entry - SL)
        SHORT: R = (entry - cmp) / (entry - SL)

    If risk is zero or invalid geometry → 0.0 (no-op).
    """
    risk = abs(entry_price - sl_price)
    if risk <= 0:
        return 0.0

    if side == "LONG":
        return (cmp_ - entry_price) / risk

    if side == "SHORT":
        return (entry_price - cmp_) / risk

    return 0.0


def update_trade_state(
    state: TradeState,
    *,
    cmp_: float,
    entry_price: float,
    sl_price: float,
) -> TradeState:
    """
    Mutates + returns state with updated R metrics.

    Assumes caller only uses this while position is non-FLAT.
    """
    side_str = _side_to_str(state.side)

    # Store geometry
    state.entry_price = float(entry_price)
    state.sl_price = float(sl_price)

    # Compute new open_R
    new_R = _compute_R(side_str, cmp_, entry_price, sl_price)
    state.open_R = new_R

    # Track peak open_R
    if new_R > state.peak_open_R:
        state.peak_open_R = new_R

    # Track drawdown: peak - current (always >= 0)
    dd = state.peak_open_R - new_R
    if dd > state.max_dd_R:
        state.max_dd_R = dd

    return state
