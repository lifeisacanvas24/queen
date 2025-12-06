#!/usr/bin/env python3
# ============================================================
# queen/settings/sim_settings.py — v1.0
# ------------------------------------------------------------
# Centralised simulator semantics for LONG / SHORT positions
# and decision vocabulary.
#
# This is *side-agnostic* config used by:
#   • queen/services/actionable_row.py
#   • queen/cli/replay_actionable.py
#   • queen/cli/scan_signals.py (indirectly via replay_actionable)
#
# Semantics (agreed with Kavya):
#   • AVOID → entry filter, NEVER exits positions
#   • HOLD  → maintain position (no open/close/add)
#   • LONG:  BUY / ADD / EXIT
#   • SHORT: SELL / ADD_SHORT / EXIT_SHORT
#   • EOD:   force EXIT / EXIT_SHORT if configured
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import Enum
from typing import Dict


class PositionSide(str, Enum):
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


class Decision(str, Enum):
    BUY = "BUY"
    ADD = "ADD"
    EXIT = "EXIT"
    SELL = "SELL"
    ADD_SHORT = "ADD_SHORT"
    EXIT_SHORT = "EXIT_SHORT"
    HOLD = "HOLD"
    AVOID = "AVOID"


@dataclass(frozen=True)
class SimConfig:
    """Top-level simulator configuration.

    Note:
        This does *not* know about capital, symbol weights, etc.
        It only encodes structural behaviour:
          • EOD rules
          • Whether overnight positions are allowed

    """

    # EOD cut-off (exchange local time)
    eod_cutoff: time = time(hour=15, minute=20)

    # Overnight rules
    allow_overnight_longs: bool = True
    allow_overnight_shorts: bool = False


# Default global config used by simulator.
DEFAULT_SIM_CONFIG = SimConfig()


# ---------------------------------------------------------------------
# Decision semantics (static, side-agnostic)
# ---------------------------------------------------------------------

# These semantics are applied *after* we know the current PositionSide.
# The simulator in actionable_row.py uses this table plus side-specific
# logic (e.g. EXIT_SHORT only valid on SHORT).



DECISION_RULES: Dict[str, Dict[str, bool]] = {
    Decision.BUY.value: {"opens_new_trade": True, "adds_to_position": True, "closes_existing": False},
    Decision.ADD.value: {"opens_new_trade": False, "adds_to_position": True, "closes_existing": False},
    Decision.EXIT.value: {"opens_new_trade": False, "adds_to_position": False, "closes_existing": True},
    Decision.SELL.value: {"opens_new_trade": True, "adds_to_position": True, "closes_existing": False},
    Decision.ADD_SHORT.value: {"opens_new_trade": False, "adds_to_position": True, "closes_existing": False},
    Decision.EXIT_SHORT.value: {"opens_new_trade": False, "adds_to_position": False, "closes_existing": True},
    Decision.HOLD.value: {"opens_new_trade": False, "adds_to_position": False, "closes_existing": False},
    Decision.AVOID.value: {"opens_new_trade": False, "adds_to_position": False, "closes_existing": False},
}

__all__ = ["PositionSide", "Decision", "SimConfig", "DEFAULT_SIM_CONFIG", "DECISION_RULES"]
