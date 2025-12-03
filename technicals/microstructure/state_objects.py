#!/usr/bin/env python3
# ======================================================================
# queen/helpers/state_objects.py — v1.0
# ----------------------------------------------------------------------
# Canonical state dataclasses for microstructure + phase engine.
#
# Everything in strategies/ and services/ should operate ONLY on these
# typed objects, not raw dicts. This is the foundation for:
#
#   • Structure detection (HH-HL, LH-LL, compression, breaks)
#   • Volume context (VDU, expansion, exhaustion)
#   • VWAP location (above/below/inside)
#   • CPR bias (above/inside/below)
#   • ATR + risk regime (low/med/high)
#   • Composite PhaseState used by playbook + decision_engine
#
# ======================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal, List, Dict


# ----------------------------------------------------------------------
# Small enums as Literal types (safe & IDE friendly)
# ----------------------------------------------------------------------

TrendDirection = Literal["UP", "DOWN", "FLAT"]
StructureLabel = Literal[
    "IMPULSE_UP", "IMPULSE_DOWN",
    "PULLBACK_UP", "PULLBACK_DOWN",
    "COMPRESSION", "EXPANSION",
    "RANGE"
]

VolumeLabel = Literal[
    "LOW_VDU",          # Volume Dry-Up
    "NORMAL",
    "EXPANDING",
    "CLIMAX",
]

VWAPZone = Literal[
    "ABOVE_VWAP",
    "BELOW_VWAP",
    "AT_VWAP",
]

CPRZone = Literal[
    "ABOVE_CPR",
    "INSIDE_CPR",
    "BELOW_CPR",
]

RiskBand = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
]

PhaseLabel = Literal[
    "ACCUMULATION",
    "CONSOLIDATION",
    "MARKUP",
    "DISTRIBUTION",
    "DECLINE",
    "REVERSAL_SETUP",
    "BREAKOUT_SETUP",
    "PULLBACK_BUY",
    "PULLBACK_SELL",
]


# ======================================================================
# Dataclasses — Core State Objects
# ======================================================================

# ----------------------------------------------------------------------
# Structure State (HH-HL-LH-LL + compression + directional intent)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class StructureState:
    direction: TrendDirection
    label: StructureLabel
    swing_highs: List[float] = field(default_factory=list)
    swing_lows: List[float] = field(default_factory=list)
    compression_ratio: float = 0.0  # 0 → no compression, 1 → extremely tight

    def is_bullish(self) -> bool:
        return self.direction == "UP"

    def is_bearish(self) -> bool:
        return self.direction == "DOWN"

    def is_range(self) -> bool:
        return self.label == "RANGE" or self.direction == "FLAT"


# ----------------------------------------------------------------------
# Volume State (VDU, expansion, exhaustion)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class VolumeState:
    label: VolumeLabel
    relative_vol: float               # volume / avg_volume
    avg_volume: float
    last_volume: float

    @property
    def is_vdu(self) -> bool:
        return self.label == "LOW_VDU"

    @property
    def is_expanding(self) -> bool:
        return self.label == "EXPANDING"


# ----------------------------------------------------------------------
# VWAP State (market control)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class VWAPState:
    zone: VWAPZone
    vwap: float
    price: float

    @property
    def bullish(self) -> bool:
        return self.zone == "ABOVE_VWAP"

    @property
    def bearish(self) -> bool:
        return self.zone == "BELOW_VWAP"


# ----------------------------------------------------------------------
# CPR State (the holy CPR alignment)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CPRState:
    zone: CPRZone
    tc: float  # Top Central
    bc: float  # Bottom Central
    width: float

    @property
    def narrow(self) -> bool:
        """Narrow CPR → potential trending day."""
        return self.width < 0.0025  # Adaptive threshold later


# ----------------------------------------------------------------------
# Risk State (ATR-driven)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class RiskState:
    band: RiskBand
    atr: float
    atr_ratio: float                  # ATR / price
    volatility_score: float           # optional composite score


# ----------------------------------------------------------------------
# Composite Phase State
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class PhaseState:
    """
    The final unified phase classification produced by phases.py.

    This single object drives:
        • playbook tagging
        • decision_engine classification
        • scalp readiness
        • breakout readiness
    """
    phase: PhaseLabel

    # Embedded microstructure components:
    structure: StructureState
    volume: VolumeState
    vwap: VWAPState
    cpr: CPRState
    risk: RiskState

    # Optional metadata for transparency / debugging:
    notes: List[str] = field(default_factory=list)
    drivers: Dict[str, float] = field(default_factory=dict)

    def is_accumulation(self) -> bool:
        return self.phase == "ACCUMULATION"

    def is_breakout_setup(self) -> bool:
        return self.phase == "BREAKOUT_SETUP"

    def is_pullback_buy(self) -> bool:
        return self.phase == "PULLBACK_BUY"

    def is_reversal(self) -> bool:
        return self.phase == "REVERSAL_SETUP"

    def is_decline(self) -> bool:
        return self.phase == "DECLINE"


# ======================================================================
# Example JSON output (for scan_signals / cockpit)
# ======================================================================

"""
{
  "symbol": "VOLTAMP",
  "phase": "BREAKOUT_SETUP",
  "structure": {
      "direction": "UP",
      "label": "IMPULSE_UP",
      "compression_ratio": 0.14
  },
  "volume": {
      "label": "EXPANDING",
      "relative_vol": 1.32
  },
  "vwap": {
      "zone": "ABOVE_VWAP"
  },
  "cpr": {
      "zone": "ABOVE_CPR",
      "width": 0.0012
  },
  "risk": {
      "band": "MEDIUM",
      "atr_ratio": 0.0081
  },
  "notes": ["Bullish structure + rising volume"]
}
"""
