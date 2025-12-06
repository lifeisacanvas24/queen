#!/usr/bin/env python3
# ============================================================
# queen/settings/risk.py — v1.2
# ------------------------------------------------------------
# Global risk & guardrail settings for:
#   • Laddering (adds)
#   • Heat / R-based stops
#
# Intent (Kavya):
#   • No more "Upstox-style" blowups
#   • Strict limits on:
#       - How many times we can add
#       - How much R we are allowed to lose
#       - How much R we are allowed to GIVE BACK from peak
# ============================================================

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LadderSettings:
    # After this size, we demand "proof of edge" before more adds.
    proof_qty: float = 2.0

    # Minimum peak R (unrealized) required to keep laddering
    # once proof_qty is reached.
    min_proof_R: float = 1.0

    # Hard cap on number of adds per trade.
    # This kills 1→30 / 1→35 ladders.
    max_adds_per_trade: int = 1

    # (Optional) future: require each add to be at least X% above/below
    # last add price for momentum pyramiding. Not enforced yet.
    add_gain_pct: float = 0.01


@dataclass(frozen=True)
class HeatSettings:
    # Hard stop per trade in R-space (absolute loss).
    # If open_R <= loss_stop_R → force EXIT/EXIT_SHORT.
    #
    # With loss_stop_R=-2.5, realized loss should usually live
    # around -2.5R to -3R even with some slippage/gaps.
    loss_stop_R: float = -2.5

    # Max allowed giveback from peak in R.
    # If drawdown_R >= giveback_stop_R → force EXIT/EXIT_SHORT,
    # even if trade is still positive in absolute terms.
    #
    # Example:
    #   peak_R = +4.5R
    #   giveback_stop_R = 3.0R
    # → If we drop to +1.5R or worse, trade is killed.
    giveback_stop_R: float = 3.0

    # Backward-compatible alias, if any old code still reads heat_stop_R.
    @property
    def heat_stop_R(self) -> float:
        return self.loss_stop_R


LADDER = LadderSettings()
HEAT = HeatSettings()

__all__ = [
    "LadderSettings",
    "HeatSettings",
    "LADDER",
    "HEAT",
]
