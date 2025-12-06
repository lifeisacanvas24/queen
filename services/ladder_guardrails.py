#!/usr/bin/env python3
# ============================================================
# queen/services/ladder_guardrails.py — v1.2
# ------------------------------------------------------------
# R-space + ladder guardrails for synthetic auto-positioning.
#
# Responsibilities:
#   • Take raw engine decision (BUY/ADD/SELL/ADD_SHORT/EXIT/EXIT_SHORT/HOLD/AVOID)
#   • Take current ladder + heat context (R metrics + adds meta)
#   • Optionally *neutralize* or *exit* risk by:
#       1) Heat stops in R-space:
#            - absolute loss (loss_stop_R)
#            - giveback from peak (giveback_stop_R)
#       2) Ladder cap (max adds / trade)
#       3) Proof-of-edge (don’t pyramid without demonstrated edge)
#
# Important:
#   • We NEVER upsize here.
#   • We only:
#       → turn entries into HOLD
#       → or force EXIT / EXIT_SHORT
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from queen.settings.risk import HEAT, LADDER

# ----------------- context model -----------------


@dataclass
class LadderContext:
    side: str                      # "LONG" or "SHORT"
    sim_qty: float                 # current synthetic position size
    ladder_adds: int               # how many adds have been done in this trade
    open_R: float                  # current open R (unrealized / 1R)
    peak_R: float                  # best open R seen so far in this trade
    max_dd_R: float                # max drawdown in R (peak_R - min_open_R, >= 0)
    entry_price: float | None      # first entry price for this trade (optional; for logging)
    last_add_price: float | None   # last add price (optional; for logging)
    cmp: float | None              # current cmp (optional; for logging)


# ----------------- decision helpers -----------------


_LONG_ENTRY = {"BUY", "ADD"}
_SHORT_ENTRY = {"SELL", "ADD_SHORT"}
_EXIT_TOKENS = {"EXIT", "EXIT_SHORT"}
_ENTRY_TOKENS = _LONG_ENTRY | _SHORT_ENTRY


def _norm_dec(dec: str | None) -> str:
    if dec is None:
        return ""
    return str(dec).strip().upper()


def _is_entry(dec: str) -> bool:
    return _norm_dec(dec) in _ENTRY_TOKENS


def _is_exit(dec: str) -> bool:
    return _norm_dec(dec) in _EXIT_TOKENS


def _exit_token_for_side(side: str) -> str:
    side = (side or "").upper()
    if side == "SHORT":
        return "EXIT_SHORT"
    # default to long-exit for anything else / FLAT
    return "EXIT"


# ----------------- main guardrails -----------------


def apply_ladder_guardrails(decision: str, ctx: LadderContext) -> Tuple[str, List[str]]:
    """Given:
        • raw decision from engine (BUY/ADD/SELL/ADD_SHORT/EXIT/EXIT_SHORT/HOLD/AVOID)
        • current ladder/heat context (R-space + ladder meta)

    Return:
        (adjusted_decision, reasons)

    Rules (v1.2):
        1) Heat stops:
            a) Absolute loss:
                - If open_R <= HEAT.loss_stop_R
                  → FORCE EXIT / EXIT_SHORT
            b) Giveback from peak:
                - If max_dd_R >= HEAT.giveback_stop_R
                  → FORCE EXIT / EXIT_SHORT
        2) Ladder cap:
            - If in a trade and ladder_adds >= LADDER.max_adds_per_trade:
                → block further adds → HOLD
        3) Proof-of-edge:
            - If in a trade AND sim_qty >= proof_qty AND peak_R < min_proof_R:
                → block further adds → HOLD

    We never upsize a trade here; only *neutralize* or *exit* risk.

    """
    reasons: List[str] = []
    dec = _norm_dec(decision)

    # If flat or no active size, nothing to guard.
    if ctx.sim_qty <= 0:
        return dec, reasons

    # -------------------------
    # 1) HEAT STOPS (R-based)
    # -------------------------
    open_R = float(ctx.open_R or 0.0)
    max_dd_R = float(ctx.max_dd_R or 0.0)

    loss_trigger = open_R <= float(HEAT.loss_stop_R)
    giveback_trigger = max_dd_R >= float(HEAT.giveback_stop_R)

    if loss_trigger or giveback_trigger:
        if not _is_exit(dec):
            forced_dec = _exit_token_for_side(ctx.side)
            if loss_trigger and giveback_trigger:
                reasons.append(
                    "loss_stop + giveback_stop: "
                    f"open_R={open_R:.2f} <= loss_stop_R={HEAT.loss_stop_R:.2f}, "
                    f"max_dd_R={max_dd_R:.2f} >= giveback_stop_R={HEAT.giveback_stop_R:.2f} "
                    f"→ {forced_dec}"
                )
            elif loss_trigger:
                reasons.append(
                    "loss_stop: "
                    f"open_R={open_R:.2f} <= loss_stop_R={HEAT.loss_stop_R:.2f} "
                    f"→ {forced_dec}"
                )
            else:
                reasons.append(
                    "giveback_stop: "
                    f"max_dd_R={max_dd_R:.2f} >= giveback_stop_R={HEAT.giveback_stop_R:.2f} "
                    f"→ {forced_dec}"
                )
            return forced_dec, reasons

        # Engine already exiting; annotate why it is within heat limits.
        if loss_trigger and giveback_trigger:
            reasons.append(
                "loss_stop + giveback_stop: engine_exit_within_heat "
                f"(open_R={open_R:.2f}, loss_stop_R={HEAT.loss_stop_R:.2f}, "
                f"max_dd_R={max_dd_R:.2f}, giveback_stop_R={HEAT.giveback_stop_R:.2f})"
            )
        elif loss_trigger:
            reasons.append(
                "loss_stop: engine_exit_within_heat "
                f"(open_R={open_R:.2f}, threshold={HEAT.loss_stop_R:.2f})"
            )
        else:
            reasons.append(
                "giveback_stop: engine_exit_within_heat "
                f"(max_dd_R={max_dd_R:.2f}, threshold={HEAT.giveback_stop_R:.2f})"
            )
        return dec, reasons

    # -------------------------
    # 2) LADDER CAP
    # -------------------------
    if _is_entry(dec) and ctx.ladder_adds >= int(LADDER.max_adds_per_trade):
        reasons.append(
            "ladder_cap: "
            f"ladder_adds={ctx.ladder_adds} >= "
            f"max_adds={LADDER.max_adds_per_trade} → HOLD"
        )
        return "HOLD", reasons

    # -------------------------
    # 3) PROOF-OF-EDGE
    # -------------------------
    if (
        _is_entry(dec)
        and ctx.sim_qty >= float(LADDER.proof_qty)
        and ctx.peak_R < float(LADDER.min_proof_R)
    ):
        reasons.append(
            "no_proof_of_edge: "
            f"qty={ctx.sim_qty:.1f} >= proof_qty={LADDER.proof_qty}, "
            f"but peak_R={ctx.peak_R:.2f} < "
            f"min_proof_R={LADDER.min_proof_R:.2f} → HOLD"
        )
        return "HOLD", reasons

    # If nothing triggered, return original decision.
    return dec, reasons
