#!/usr/bin/env python3
# ======================================================================
# queen/technicals/microstructure/phases.py — v1.0
# ----------------------------------------------------------------------
# Phase Engine (v1) — intermediate rules:
#
# Uses:
#   • StructureState (trend + swing context)
#   • VolumeState    (VDU / spike)
#   • VWAPState      (location vs VWAP)
#   • CPRState       (narrow/wide, position in CPR)
#   • RiskState      (low/medium/high, allow_trend/scalp)
#
# Responsibilities:
#   • Derive a **single phase label**, like:
#       - "INTRADAY_ADVANCE"
#       - "INTRADAY_DECLINE"
#       - "RANGE_COIL"
#       - "POST_BREAKOUT_FADE"
#       - "NOISE"
#   • Attach secondary tags to help playbook:
#       - ["TREND_UP", "ABOVE_VWAP", "CPR_NARROW", "HIGH_VOL"]
#
# Output:
#   • PhaseState dataclass (from state_objects.py)
# ======================================================================

from __future__ import annotations

from typing import Optional

import polars as pl

from queen.technicals.microstructure.state_objects import (
    StructureState,
    VolumeState,
    VWAPState,
    CPRState,
    RiskState,
    PhaseState,
)
from queen.technicals.microstructure.structure import detect_structure
from queen.technicals.microstructure.volume import detect_volume
from queen.technicals.microstructure.vwap import detect_vwap
from queen.technicals.microstructure.cpr import detect_cpr
from queen.technicals.microstructure.risk import detect_risk


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _ensure_sorted(df: pl.DataFrame, ts_col: str = "timestamp") -> pl.DataFrame:
    if ts_col not in df.columns:
        return df
    return df.sort(ts_col)


def _phase_from_components(
    structure: StructureState,
    volume: VolumeState,
    vwap: VWAPState,
    cpr: CPRState,
    risk: RiskState,
) -> tuple[str, list[str]]:
    """
    Core rule sheet for Phase Engine v1.

    INPUTS are already normalised states; we just map them into:
      • phase (single string)
      • tags (list[str])
    """
    tags: list[str] = []

    # --- basic trend tags ---
    trend = (structure.trend or "").upper()
    if trend == "UP":
        tags.append("TREND_UP")
    elif trend == "DOWN":
        tags.append("TREND_DOWN")
    else:
        tags.append("TREND_FLAT")

    # --- VWAP tags ---
    if vwap.zone == "above":
        tags.append("ABOVE_VWAP")
    elif vwap.zone == "below":
        tags.append("BELOW_VWAP")
    else:
        tags.append("AT_VWAP")

    # --- Volume regime tags ---
    vol_reg = (volume.regime or "").upper()
    tags.append(f"VOL_{vol_reg or 'UNKNOWN'}")
    if volume.vdu:
        tags.append("VDU")
    if volume.spike:
        tags.append("VOL_SPIKE")

    # --- CPR tags ---
    width = (cpr.width_regime or "").upper()
    tags.append(f"CPR_{width or 'UNKNOWN'}")
    tags.append(f"CPR_LOC_{(cpr.location or '').upper()}")

    # --- Risk tags ---
    tags.append(f"RISK_{risk.band.upper()}")
    if not risk.allow_trend:
        tags.append("NO_TREND_ENTRY")
    if not risk.allow_scalp:
        tags.append("NO_SCALP_ENTRY")

    # --- Phase classification (v1 heuristics) ---

    # 1) Strong intraday advance:
    #    • Uptrend
    #    • Above VWAP
    #    • Volume NORMAL/HIGH/VERY_HIGH, not VDU
    #    • Risk not "high" for trend
    if (
        trend == "UP"
        and vwap.zone == "above"
        and vol_reg in ("NORMAL", "HIGH", "VERY_HIGH")
        and not volume.vdu
        and risk.allow_trend
    ):
        phase = "INTRADAY_ADVANCE"
        return phase, tags

    # 2) Intraday decline:
    #    • Downtrend
    #    • Below VWAP
    if trend == "DOWN" and vwap.zone == "below":
        phase = "INTRADAY_DECLINE"
        return phase, tags

    # 3) Coil / ready (range + narrow CPR + VDU)
    #    • Trend flat/unknown
    #    • CPR NARROW
    #    • Volume very low (VDU)
    if trend != "UP" and width == "NARROW" and volume.vdu:
        phase = "RANGE_COIL"
        return phase, tags

    # 4) Post-breakout fade:
    #    • Uptrend structure
    #    • Price at/just below VWAP
    #    • Volume decaying (LOW / VERY_LOW) without spike
    if (
        trend == "UP"
        and vwap.zone in ("at", "below")
        and vol_reg in ("LOW", "VERY_LOW")
        and not volume.spike
    ):
        phase = "POST_BREAKOUT_FADE"
        return phase, tags

    # 5) Wide CPR + flat trend → choppy range
    if trend == "FLAT" and width == "WIDE":
        phase = "CHOPPY_RANGE"
        return phase, tags

    # 6) High risk regardless of components
    if risk.band == "high":
        phase = "HIGH_RISK_NOISE"
        return phase, tags

    # Default: noise / unclassified
    phase = "NOISE"
    return phase, tags


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def detect_phase(
    df: pl.DataFrame,
    *,
    timestamp_col: str = "timestamp",
    atr_ratio: float | None = None,
    gap_pct: float | None = None,
) -> PhaseState:
    """
    Top-level Phase Engine v1.

    Inputs
    ------
    df : pl.DataFrame
        Intraday/daily frame (OHLCV), one symbol, one session.
    timestamp_col : str
        Column used for sorting.
    atr_ratio : float | None
        ATR_Ratio (or similar) used for risk classification.
    gap_pct : float | None
        Overnight gap %, optional.

    Returns
    -------
    PhaseState
        Dataclass capturing:
          • phase        (INTRADAY_ADVANCE / RANGE_COIL / etc.)
          • tags         (list[str])
          • structure    (StructureState)
          • volume       (VolumeState)
          • vwap         (VWAPState)
          • cpr          (CPRState)
          • risk         (RiskState)
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        # Use "NOISE" with default states
        empty_struct = StructureState.empty()
        empty_vol = VolumeState.empty()
        empty_vwap = VWAPState.empty()
        empty_cpr = CPRState.empty()
        empty_risk = RiskState.empty()
        return PhaseState(
            phase="NOISE",
            tags=["EMPTY_DF"],
            structure=empty_struct,
            volume=empty_vol,
            vwap=empty_vwap,
            cpr=empty_cpr,
            risk=empty_risk,
        )

    df_sorted = _ensure_sorted(df, ts_col=timestamp_col)

    # 1) Microstructure components
    structure = detect_structure(df_sorted)
    volume = detect_volume(df_sorted)
    vwap = detect_vwap(df_sorted)
    cpr = detect_cpr(df_sorted)

    # 2) Risk
    risk = detect_risk(
        atr_ratio=atr_ratio,
        gap_pct=gap_pct,
        volume_state=volume,
        vwap_state=vwap,
        cpr_state=cpr,
    )

    # 3) Phase + tags
    phase_label, tags = _phase_from_components(structure, volume, vwap, cpr, risk)

    return PhaseState(
        phase=phase_label,
        tags=tags,
        structure=structure,
        volume=volume,
        vwap=vwap,
        cpr=cpr,
        risk=risk,
    )


# ======================================================================
# Example usage (manual test)
# ======================================================================

if __name__ == "__main__":
    import polars as pl

    # Toy example DF (uptrend, above VWAP, normal volume)
    data = {
        "timestamp": [
            "2025-11-28 09:15",
            "2025-11-28 09:30",
            "2025-11-28 09:45",
            "2025-11-28 10:00",
            "2025-11-28 10:15",
        ],
        "open": [100, 101, 102, 103, 104],
        "high": [101, 102, 103, 104, 105],
        "low": [99, 100, 101, 102, 103],
        "close": [101, 102, 103, 104, 105],
        "volume": [1000, 1200, 1300, 1250, 1400],
    }
    df = pl.DataFrame(data)
    ps = detect_phase(df, atr_ratio=1.1, gap_pct=0.5)
    print(ps)
    # Expect:
    #   phase ≈ "INTRADAY_ADVANCE"
    #   tags includes ["TREND_UP", "ABOVE_VWAP", "VOL_NORMAL", "CPR_...", "RISK_LOW/ MEDIUM"]
