#!/usr/bin/env python3
# ======================================================================
# queen/technicals/microstructure/risk.py — v1.0
# ----------------------------------------------------------------------
# Risk microstructure helper (Polars-agnostic).
#
# Responsibilities:
#   • Convert ATR ratio + gap + volume context into:
#       - risk_band: "low" / "medium" / "high"
#       - risk_reason: short text
#       - allow_trend: bool   (ok for INTRADAY_TREND / SWING_TREND)
#       - allow_scalp: bool   (ok for SCALP / CT_LONG)
#
# Output:
#   • RiskState dataclass (from state_objects.py)
#
# NOTE:
#   • v1 uses simple rules, tuned for intraday first.
# ======================================================================

from __future__ import annotations

from typing import Optional

from queen.technicals.microstructure.state_objects import RiskState
from queen.technicals.microstructure.state_objects import VolumeState, VWAPState, CPRState


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _risk_band_from_atr(atr_ratio: Optional[float]) -> str:
    """
    Map ATR_Ratio into a coarse risk band.

      • high   : atr_ratio ≥ 1.4
      • medium : 1.15 ≤ atr_ratio < 1.4
      • low    : atr_ratio < 1.15   or missing
    """
    if atr_ratio is None:
        return "low"
    if atr_ratio >= 1.4:
        return "high"
    if atr_ratio >= 1.15:
        return "medium"
    return "low"


def _adjust_band_for_gap(band: str, gap_pct: Optional[float]) -> str:
    """
    If there is a large overnight gap, bump risk up one band.
    """
    if gap_pct is None:
        return band

    gap_pct = abs(gap_pct)
    if gap_pct < 1.5:
        return band

    # bump up one band for large gaps
    if band == "low":
        return "medium"
    if band == "medium":
        return "high"
    return "high"


def _adjust_band_for_volume(
    band: str,
    volume_state: Optional[VolumeState],
) -> str:
    """
    If volume is extremely low (VDU) → effectively lower risk for **trend entries**
    but also lower reward. Here we only downgrade "high" to "medium".
    """
    if volume_state is None:
        return band

    if volume_state.vdu and band == "high":
        return "medium"

    return band


def _compose_reason(
    band: str,
    atr_ratio: Optional[float],
    gap_pct: Optional[float],
    volume_state: Optional[VolumeState],
) -> str:
    parts: list[str] = []

    if atr_ratio is not None:
        parts.append(f"ATR≈{atr_ratio:.2f}")
    if gap_pct is not None and abs(gap_pct) >= 1.0:
        parts.append(f"gap≈{gap_pct:.1f}%")
    if volume_state is not None:
        parts.append(f"vol={volume_state.regime}")

    if not parts:
        parts.append("no major volatility flags")

    return f"{band} risk: " + ", ".join(parts)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def detect_risk(
    *,
    atr_ratio: float | None,
    gap_pct: float | None = None,
    volume_state: VolumeState | None = None,
    vwap_state: VWAPState | None = None,
    cpr_state: CPRState | None = None,
) -> RiskState:
    """
    Lightweight risk classifier used by phases/playbook.

    It does NOT inspect the full DF; it only consumes pre-computed
    metrics from your pipeline.

    Parameters
    ----------
    atr_ratio : float | None
        Typically ATR / price (or ATR_Ratio column).
    gap_pct : float | None
        Overnight gap % (optional).
    volume_state : VolumeState | None
        From detect_volume() (optional).
    vwap_state : VWAPState | None
        From detect_vwap() (optional, reserved for v2 tweaks).
    cpr_state : CPRState | None
        From detect_cpr() (optional, reserved for v2 tweaks).

    Returns
    -------
    RiskState
        Dataclass with:
          • band           (low/medium/high)
          • reason         (short string)
          • allow_trend    (bool)
          • allow_scalp    (bool)
    """
    band = _risk_band_from_atr(atr_ratio)
    band = _adjust_band_for_gap(band, gap_pct)
    band = _adjust_band_for_volume(band, volume_state)

    # v1 permission matrix:
    #   • low risk    → allow_trend=True, allow_scalp=True
    #   • medium risk → allow_trend=True, allow_scalp=True
    #   • high risk   → allow_trend=False, allow_scalp=True
    if band == "high":
        allow_trend = False
        allow_scalp = True
    else:
        allow_trend = True
        allow_scalp = True

    reason = _compose_reason(band, atr_ratio, gap_pct, volume_state)

    return RiskState(
        band=band,
        reason=reason,
        allow_trend=allow_trend,
        allow_scalp=allow_scalp,
    )


# ======================================================================
# Example usage (manual test)
# ======================================================================

if __name__ == "__main__":
    # Example: slightly elevated ATR, no big gap, normal volume
    vs = VolumeState(
        last_volume=10000,
        avg_volume=9000,
        rel_volume=1.11,
        regime="NORMAL",
        vdu=False,
        spike=False,
    )
    rs = detect_risk(atr_ratio=1.2, gap_pct=0.8, volume_state=vs)
    print(rs)
    # Expect:
    #   band ≈ "medium"
    #   allow_trend=True, allow_scalp=True
