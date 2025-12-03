#!/usr/bin/env python3
# ======================================================================
# queen/technicals/microstructure/volume.py — v1.0
# ----------------------------------------------------------------------
# Volume microstructure engine (Polars-only).
#
# Responsibilities:
#   • Ensure DF is time-sorted (AUTO).
#   • Detect:
#       - Last bar volume
#       - Average volume over lookback
#       - Relative volume vs average
#       - Volume regime:
#           VERY_LOW / LOW / NORMAL / HIGH / VERY_HIGH
#       - VDU (Very Dry Up) flag
#       - Volume spike flag
#
# Output:
#   • VolumeState dataclass (from state_objects.py)
#
# NOTE:
#   • This is deliberately simple & robust.
#   • All thresholds are v1 defaults; can be moved to settings later.
# ======================================================================

from __future__ import annotations

from typing import Optional

import polars as pl
from queen.technicals.microstructure.state_objects import VolumeState

# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _ensure_sorted(df: pl.DataFrame, ts_col: str = "timestamp") -> pl.DataFrame:
    """Ensure DF is sorted by timestamp ascending.

    AUTO behaviour: all helpers take responsibility for sorting.
    Safe to call even if already sorted.
    """
    if ts_col not in df.columns:
        return df
    return df.sort(ts_col)


def _pick_volume_col(df: pl.DataFrame) -> Optional[str]:
    """Try to find a volume column in a robust way.

    Priority:
      • "volume"
      • "Volume"
      • "VOL"
      • "qty"
    """
    candidates = ["volume", "Volume", "VOL", "qty"]
    existing = [c for c in candidates if c in df.columns]
    return existing[0] if existing else None


def _select_window(df: pl.DataFrame, lookback_bars: int) -> pl.DataFrame:
    """Last `lookback_bars` rows, or all if smaller.
    """
    if df.height <= lookback_bars:
        return df
    return df.tail(lookback_bars)


def _volume_regime(rel_vol: float) -> str:
    """Map relative volume into a simple regime label.

    rel_vol ≈ last_volume / avg_volume

    • VERY_LOW  : rel_vol < 0.4
    • LOW       : 0.4 ≤ rel_vol < 0.8
    • NORMAL    : 0.8 ≤ rel_vol ≤ 1.2
    • HIGH      : 1.2 < rel_vol ≤ 2.0
    • VERY_HIGH : rel_vol > 2.0
    """
    if rel_vol < 0.4:
        return "VERY_LOW"
    if rel_vol < 0.8:
        return "LOW"
    if rel_vol <= 1.2:
        return "NORMAL"
    if rel_vol <= 2.0:
        return "HIGH"
    return "VERY_HIGH"


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def detect_volume(
    df: pl.DataFrame,
    *,
    volume_col: str | None = None,
    timestamp_col: str = "timestamp",
    lookback_bars: int = 20,
) -> VolumeState:
    """Main entrypoint:

    POLARS DF (OHLCV-like)  →  VolumeState

    Parameters
    ----------
    df : pl.DataFrame
        Intraday or daily DF with a volume column.
    volume_col : str | None
        Name of the volume column. If None, auto-detected.
    timestamp_col : str
        Column used to sort the DF (default: "timestamp").
    lookback_bars : int
        Window size for computing average volume.

    Returns
    -------
    VolumeState
        Dataclass with:
          • last_volume
          • avg_volume
          • rel_volume
          • regime
          • vdu
          • spike

    """
    # Empty → fully neutral volume state
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return VolumeState(
            last_volume=0.0,
            avg_volume=0.0,
            rel_volume=0.0,
            regime="VERY_LOW",
            vdu=True,
            spike=False,
        )

    # 1) Ensure sorted
    df_sorted = _ensure_sorted(df, ts_col=timestamp_col)

    # 2) Pick volume column
    vol_col = volume_col or _pick_volume_col(df_sorted)
    if vol_col is None:
        # No volume information → treat as extreme VDU
        return VolumeState(
            last_volume=0.0,
            avg_volume=0.0,
            rel_volume=0.0,
            regime="VERY_LOW",
            vdu=True,
            spike=False,
        )

    # 3) Select window
    window = _select_window(df_sorted, lookback_bars)

    # 4) Extract series
    vol_series = window.get_column(vol_col).cast(pl.Float64)

    # Last bar volume
    last_vol = float(vol_series.tail(1).item())

    # Average volume over window
    avg_vol = float(vol_series.mean()) if window.height > 0 else 0.0

    if avg_vol <= 0:
        rel = 0.0
    else:
        rel = float(last_vol / avg_vol)

    # 5) Derive regime + VDU + spike flags
    regime = _volume_regime(rel)

    # Simple VDU / spike rules (v1 defaults):
    #   • VDU if rel_vol <= 0.5
    #   • Spike if rel_vol >= 1.8
    vdu = rel <= 0.5
    spike = rel >= 1.8

    return VolumeState(
        last_volume=last_vol,
        avg_volume=avg_vol,
        rel_volume=rel,
        regime=regime,
        vdu=vdu,
        spike=spike,
    )


# ======================================================================
# Example usage (manual test)
# ======================================================================

if __name__ == "__main__":
    data = {
        "timestamp": [
            "2025-11-28 09:15",
            "2025-11-28 09:30",
            "2025-11-28 09:45",
            "2025-11-28 10:00",
            "2025-11-28 10:15",
            "2025-11-28 10:30",
        ],
        "close": [100, 101, 102, 103, 104, 105],
        "volume": [1000, 1200, 1100, 900, 800, 2500],  # last bar = spike
    }
    df = pl.DataFrame(data)
    vs = detect_volume(df, lookback_bars=6)
    print(vs)
    # Expected:
    #   last_volume ≈ 2500
    #   avg_volume  ≈ ~1250
    #   rel_volume  ≈ 2.0
    #   regime      ≈ "VERY_HIGH" or "HIGH" (depending on thresholds)
    #   vdu         = False
    #   spike       = True
