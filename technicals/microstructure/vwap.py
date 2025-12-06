#!/usr/bin/env python3
# ======================================================================
# queen/technicals/microstructure/vwap.py — v2.0
# ----------------------------------------------------------------------
# VWAP microstructure engine (Polars-only) with Standard Deviation Bands.
#
# Responsibilities:
#   • Ensure DF is time-sorted (AUTO).
#   • Find price + volume columns robustly.
#   • Compute session VWAP (or window VWAP).
#   • Compute Standard Deviation Bands (1σ, 2σ, 3σ).
#   • Compute last-close distance vs VWAP.
#   • Classify:
#       - zone: "above" / "at" / "below"
#       - band: "far_above" / "above" / "near" / "below" / "far_below"
#       - std_band: which standard deviation band price is in
#
# Output:
#   • VWAPState dataclass (extended with band levels)
#
# v2.0 Changes:
#   • Added Standard Deviation Bands (1σ, 2σ, 3σ)
#   • Added band level detection
#   • Added VWAPBands dataclass
#   • Added detect_vwap_bands() function
# ======================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal
import math

import polars as pl

# ---------------------------------------------------------------------------
# Try to use existing helpers - DRY COMPLIANCE
# ---------------------------------------------------------------------------
try:
    from queen.helpers.swing_detection import find_swing_points, SwingPoint, SwingType
    _USE_SHARED_SWING = True
except ImportError:
    _USE_SHARED_SWING = False

try:
    from queen.helpers.ta_math import atr_wilder
    _USE_EXISTING_ATR = True
except ImportError:
    _USE_EXISTING_ATR = False

# ---------------------------------------------------------------------------
# Try to import existing state object, fallback to local
# ---------------------------------------------------------------------------
try:
    from queen.technicals.microstructure.state_objects import VWAPState as _VWAPStateBase
    _USE_EXISTING_STATE = True
except ImportError:
    _USE_EXISTING_STATE = False


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
@dataclass
class VWAPState:
    """VWAP state with price relationship."""
    vwap: float
    last_price: float
    offset_pct: float
    zone: str  # "above" / "at" / "below"
    band: str  # "far_above" / "above" / "near" / "below" / "far_below"


@dataclass
class VWAPBands:
    """
    VWAP with Standard Deviation Bands.

    Attributes:
        vwap: Volume Weighted Average Price
        upper_1: +1 Standard Deviation
        upper_2: +2 Standard Deviation
        upper_3: +3 Standard Deviation
        lower_1: -1 Standard Deviation
        lower_2: -2 Standard Deviation
        lower_3: -3 Standard Deviation
        std_dev: Standard deviation value
        current_price: Current/last price
        current_band: Which band price is in
        band_position: Position within bands (-3 to +3)
    """
    vwap: float
    upper_1: float
    upper_2: float
    upper_3: float
    lower_1: float
    lower_2: float
    lower_3: float
    std_dev: float
    current_price: float
    current_band: str
    band_position: float

    @property
    def upper_bands(self) -> Dict[int, float]:
        return {1: self.upper_1, 2: self.upper_2, 3: self.upper_3}

    @property
    def lower_bands(self) -> Dict[int, float]:
        return {1: self.lower_1, 2: self.lower_2, 3: self.lower_3}


@dataclass
class VWAPResult:
    """
    Complete VWAP analysis result.

    Attributes:
        state: Basic VWAP state
        bands: Standard deviation bands
        is_overbought: Price above +2σ
        is_oversold: Price below -2σ
        is_extreme: Price beyond ±3σ
        mean_reversion_signal: Signal for mean reversion
        bias: Trading bias based on VWAP
    """
    state: VWAPState
    bands: VWAPBands
    is_overbought: bool
    is_oversold: bool
    is_extreme: bool
    mean_reversion_signal: Optional[str]
    bias: Literal["bullish", "bearish", "neutral"]


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------
def _ensure_sorted(df: pl.DataFrame, ts_col: str = "timestamp") -> pl.DataFrame:
    """Ensure DF is sorted by timestamp ascending."""
    if ts_col not in df.columns:
        return df
    return df.sort(ts_col)


def _pick_price_col(df: pl.DataFrame) -> Optional[str]:
    """Try to find a logical "close/price" column."""
    candidates = ["close", "Close", "price", "Price", "last_price"]
    existing = [c for c in candidates if c in df.columns]
    return existing[0] if existing else None


def _pick_volume_col(df: pl.DataFrame) -> Optional[str]:
    """Try to find a volume column."""
    candidates = ["volume", "Volume", "VOL", "qty"]
    existing = [c for c in candidates if c in df.columns]
    return existing[0] if existing else None


def _select_window(df: pl.DataFrame, lookback_bars: int | None) -> pl.DataFrame:
    """Select window for VWAP calculation."""
    if lookback_bars is None:
        return df
    if df.height <= lookback_bars:
        return df
    return df.tail(lookback_bars)


def _zone_and_band(offset_pct: float, at_tol_pct: float = 0.15) -> tuple[str, str]:
    """Derive zone and band from offset percentage."""
    # zone
    if abs(offset_pct) <= at_tol_pct:
        zone = "at"
    elif offset_pct > 0:
        zone = "above"
    else:
        zone = "below"

    # band
    if offset_pct >= 1.5:
        band = "far_above"
    elif offset_pct >= 0.3:
        band = "above"
    elif offset_pct > -0.3:
        band = "near"
    elif offset_pct > -1.5:
        band = "below"
    else:
        band = "far_below"

    return zone, band


def _calculate_vwap_std(
    prices: pl.Series,
    volumes: pl.Series,
    vwap: float,
) -> float:
    """
    Calculate Volume-Weighted Standard Deviation.

    Formula: sqrt(sum(v * (p - vwap)^2) / sum(v))
    """
    vol_sum = float(volumes.sum() or 0.0)
    if vol_sum <= 0:
        return 0.0

    # (price - vwap)^2 * volume
    squared_diff = ((prices - vwap) ** 2) * volumes
    variance = float(squared_diff.sum()) / vol_sum

    return math.sqrt(variance) if variance > 0 else 0.0


def _determine_std_band(price: float, vwap: float, std: float) -> tuple[str, float]:
    """
    Determine which standard deviation band the price is in.

    Returns: (band_name, band_position)
    band_position: -3 to +3 (negative = below VWAP)
    """
    if std <= 0:
        return "at_vwap", 0.0

    # Calculate position in terms of standard deviations
    position = (price - vwap) / std

    if position >= 3:
        return "above_3σ", min(position, 4.0)
    elif position >= 2:
        return "above_2σ", position
    elif position >= 1:
        return "above_1σ", position
    elif position > -1:
        return "at_vwap", position
    elif position > -2:
        return "below_1σ", position
    elif position > -3:
        return "below_2σ", position
    else:
        return "below_3σ", max(position, -4.0)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def detect_vwap(
    df: pl.DataFrame,
    *,
    price_col: str | None = None,
    volume_col: str | None = None,
    timestamp_col: str = "timestamp",
    lookback_bars: int | None = None,
) -> VWAPState:
    """
    POLARS DF (OHLCV-like) → VWAPState

    Parameters
    ----------
    df : pl.DataFrame
        Intraday or daily DF with price + volume columns.
    price_col : str | None
        Name of the price/close column. If None, auto-detected.
    volume_col : str | None
        Name of the volume column. If None, auto-detected.
    timestamp_col : str
        Column used to sort the DF (default: "timestamp").
    lookback_bars : int | None
        If given: use only the last N bars for VWAP.
        If None: use the full DF (session VWAP).

    Returns
    -------
    VWAPState
        Dataclass with vwap, last_price, offset_pct, zone, band
    """
    # Empty → neutral VWAP state
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return VWAPState(
            vwap=0.0,
            last_price=0.0,
            offset_pct=0.0,
            zone="at",
            band="near",
        )

    # 1) Ensure sorted
    df_sorted = _ensure_sorted(df, ts_col=timestamp_col)

    # 2) Detect columns
    px_col = price_col or _pick_price_col(df_sorted)
    vol_col = volume_col or _pick_volume_col(df_sorted)

    if px_col is None or vol_col is None:
        return VWAPState(
            vwap=0.0,
            last_price=0.0,
            offset_pct=0.0,
            zone="at",
            band="near",
        )

    # 3) Window
    window = _select_window(df_sorted, lookback_bars)

    # 4) Prepare series
    px = window.get_column(px_col).cast(pl.Float64)
    vol = window.get_column(vol_col).cast(pl.Float64)

    # 5) VWAP = sum(p * v) / sum(v)
    vol_sum = float(vol.sum() or 0.0)
    if vol_sum <= 0:
        vwap_val = float(px.tail(1).item())
    else:
        vwap_val = float((px * vol).sum() / vol_sum)

    last_price = float(px.tail(1).item())
    if vwap_val > 0:
        offset_pct = (last_price - vwap_val) / vwap_val * 100.0
    else:
        offset_pct = 0.0

    zone, band = _zone_and_band(offset_pct)

    return VWAPState(
        vwap=vwap_val,
        last_price=last_price,
        offset_pct=offset_pct,
        zone=zone,
        band=band,
    )


def detect_vwap_bands(
    df: pl.DataFrame,
    *,
    price_col: str | None = None,
    volume_col: str | None = None,
    timestamp_col: str = "timestamp",
    lookback_bars: int | None = None,
    num_std: int = 3,
) -> VWAPBands:
    """
    Calculate VWAP with Standard Deviation Bands.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    price_col : str | None
        Price column name (auto-detected if None)
    volume_col : str | None
        Volume column name (auto-detected if None)
    timestamp_col : str
        Timestamp column for sorting
    lookback_bars : int | None
        Window size (None = full session)
    num_std : int
        Number of standard deviation bands (default: 3)

    Returns
    -------
    VWAPBands
        VWAP with standard deviation bands

    Example
    -------
    >>> bands = detect_vwap_bands(df)
    >>> if bands.current_band == "below_2σ":
    ...     print("Potential mean reversion long!")
    """
    # Empty check
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return VWAPBands(
            vwap=0, upper_1=0, upper_2=0, upper_3=0,
            lower_1=0, lower_2=0, lower_3=0,
            std_dev=0, current_price=0,
            current_band="at_vwap", band_position=0,
        )

    # Sort and prepare
    df_sorted = _ensure_sorted(df, ts_col=timestamp_col)
    px_col = price_col or _pick_price_col(df_sorted)
    vol_col = volume_col or _pick_volume_col(df_sorted)

    if px_col is None or vol_col is None:
        return VWAPBands(
            vwap=0, upper_1=0, upper_2=0, upper_3=0,
            lower_1=0, lower_2=0, lower_3=0,
            std_dev=0, current_price=0,
            current_band="at_vwap", band_position=0,
        )

    # Window
    window = _select_window(df_sorted, lookback_bars)

    # Get series
    px = window.get_column(px_col).cast(pl.Float64)
    vol = window.get_column(vol_col).cast(pl.Float64)

    # Calculate VWAP
    vol_sum = float(vol.sum() or 0.0)
    if vol_sum <= 0:
        vwap_val = float(px.tail(1).item())
    else:
        vwap_val = float((px * vol).sum() / vol_sum)

    # Calculate Standard Deviation
    std_dev = _calculate_vwap_std(px, vol, vwap_val)

    # Calculate bands
    upper_1 = vwap_val + std_dev
    upper_2 = vwap_val + 2 * std_dev
    upper_3 = vwap_val + 3 * std_dev
    lower_1 = vwap_val - std_dev
    lower_2 = vwap_val - 2 * std_dev
    lower_3 = vwap_val - 3 * std_dev

    # Current price analysis
    current_price = float(px.tail(1).item())
    current_band, band_position = _determine_std_band(current_price, vwap_val, std_dev)

    return VWAPBands(
        vwap=vwap_val,
        upper_1=upper_1,
        upper_2=upper_2,
        upper_3=upper_3,
        lower_1=lower_1,
        lower_2=lower_2,
        lower_3=lower_3,
        std_dev=std_dev,
        current_price=current_price,
        current_band=current_band,
        band_position=band_position,
    )


def analyze_vwap(
    df: pl.DataFrame,
    *,
    price_col: str | None = None,
    volume_col: str | None = None,
    lookback_bars: int | None = None,
) -> VWAPResult:
    """
    Complete VWAP analysis with bands and signals.

    Returns
    -------
    VWAPResult
        Complete analysis including overbought/oversold and mean reversion
    """
    state = detect_vwap(df, price_col=price_col, volume_col=volume_col, lookback_bars=lookback_bars)
    bands = detect_vwap_bands(df, price_col=price_col, volume_col=volume_col, lookback_bars=lookback_bars)

    # Overbought/Oversold
    is_overbought = bands.band_position >= 2
    is_oversold = bands.band_position <= -2
    is_extreme = abs(bands.band_position) >= 3

    # Mean reversion signal
    mean_reversion_signal = None
    if is_extreme:
        if bands.band_position >= 3:
            mean_reversion_signal = "strong_short"
        elif bands.band_position <= -3:
            mean_reversion_signal = "strong_long"
    elif is_overbought:
        mean_reversion_signal = "potential_short"
    elif is_oversold:
        mean_reversion_signal = "potential_long"

    # Bias
    if state.zone == "above" and not is_overbought:
        bias = "bullish"
    elif state.zone == "below" and not is_oversold:
        bias = "bearish"
    elif is_overbought:
        bias = "bearish"  # Mean reversion expected
    elif is_oversold:
        bias = "bullish"  # Mean reversion expected
    else:
        bias = "neutral"

    return VWAPResult(
        state=state,
        bands=bands,
        is_overbought=is_overbought,
        is_oversold=is_oversold,
        is_extreme=is_extreme,
        mean_reversion_signal=mean_reversion_signal,
        bias=bias,
    )


def summarize_vwap(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary dict for signal cards."""
    result = analyze_vwap(df)

    return {
        "vwap": round(result.state.vwap, 2),
        "last_price": round(result.state.last_price, 2),
        "offset_pct": round(result.state.offset_pct, 2),
        "zone": result.state.zone,
        "band": result.state.band,
        "std_dev": round(result.bands.std_dev, 2),
        "upper_1σ": round(result.bands.upper_1, 2),
        "upper_2σ": round(result.bands.upper_2, 2),
        "lower_1σ": round(result.bands.lower_1, 2),
        "lower_2σ": round(result.bands.lower_2, 2),
        "current_band": result.bands.current_band,
        "band_position": round(result.bands.band_position, 2),
        "is_overbought": result.is_overbought,
        "is_oversold": result.is_oversold,
        "mean_reversion_signal": result.mean_reversion_signal,
        "vwap_bias": result.bias,
    }


def attach_vwap_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Attach VWAP columns to DataFrame."""
    result = analyze_vwap(df)

    return df.with_columns([
        pl.lit(round(result.state.vwap, 2)).alias("vwap"),
        pl.lit(result.state.zone).alias("vwap_zone"),
        pl.lit(result.bands.current_band).alias("vwap_band"),
        pl.lit(round(result.bands.band_position, 2)).alias("vwap_band_position"),
        pl.lit(result.is_overbought).alias("vwap_overbought"),
        pl.lit(result.is_oversold).alias("vwap_oversold"),
    ])


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "vwap": detect_vwap,
    "vwap_bands": detect_vwap_bands,
    "vwap_analysis": analyze_vwap,
    "vwap_summary": summarize_vwap,
    "vwap_attach": attach_vwap_signals,
}

NAME = "vwap"


# ======================================================================
# CLI Test
# ======================================================================
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("VWAP WITH STANDARD DEVIATION BANDS TEST")
    print("=" * 60)

    # Create sample data
    np.random.seed(42)
    n = 50

    base_price = 100.0
    prices = [base_price]
    volumes = []

    for i in range(n):
        change = np.random.uniform(-0.5, 0.6)  # Slight upward bias
        prices.append(prices[-1] + change)
        volumes.append(10000 + np.random.randint(-3000, 5000))

    prices = prices[1:]

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d} 09:{15 + i}" for i in range(n)],
        "close": prices,
        "volume": volumes,
    })

    # Test basic VWAP
    state = detect_vwap(df)
    print(f"\n📊 BASIC VWAP:")
    print(f"   VWAP: {state.vwap:.2f}")
    print(f"   Last Price: {state.last_price:.2f}")
    print(f"   Offset: {state.offset_pct:.2f}%")
    print(f"   Zone: {state.zone}")
    print(f"   Band: {state.band}")

    # Test VWAP Bands
    bands = detect_vwap_bands(df)
    print(f"\n📊 STANDARD DEVIATION BANDS:")
    print(f"   +3σ: {bands.upper_3:.2f}")
    print(f"   +2σ: {bands.upper_2:.2f}")
    print(f"   +1σ: {bands.upper_1:.2f}")
    print(f"   VWAP: {bands.vwap:.2f}")
    print(f"   -1σ: {bands.lower_1:.2f}")
    print(f"   -2σ: {bands.lower_2:.2f}")
    print(f"   -3σ: {bands.lower_3:.2f}")
    print(f"\n   Std Dev: {bands.std_dev:.2f}")
    print(f"   Current Band: {bands.current_band}")
    print(f"   Band Position: {bands.band_position:.2f}σ")

    # Test Full Analysis
    result = analyze_vwap(df)
    print(f"\n📊 ANALYSIS:")
    print(f"   Overbought: {result.is_overbought}")
    print(f"   Oversold: {result.is_oversold}")
    print(f"   Extreme: {result.is_extreme}")
    print(f"   Mean Reversion Signal: {result.mean_reversion_signal}")
    print(f"   Bias: {result.bias}")

    # Test Summary
    print(f"\n📊 SUMMARY:")
    summary = summarize_vwap(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ VWAP with Standard Deviation Bands test complete!")
