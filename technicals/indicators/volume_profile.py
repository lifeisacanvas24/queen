# queen/technicals/indicators/volume_profile.py
"""
Volume Profile Analysis Module
==============================
Calculates Volume Profile metrics including POC, VAH, VAL, and value area.

Key Concepts:
- POC (Point of Control): Price level with highest volume
- VAH (Value Area High): Upper boundary of 70% volume
- VAL (Value Area Low): Lower boundary of 70% volume
- Value Area: Price range containing 70% of volume
- HVN (High Volume Node): Price levels with above-average volume
- LVN (Low Volume Node): Price levels with below-average volume

Usage:
    from queen.technicals.indicators.volume_profile import (
        calculate_volume_profile,
        get_poc,
        get_value_area,
        VolumeProfileResult,
    )

    result = calculate_volume_profile(df, num_bins=50)
    print(f"POC: {result.poc}")
    print(f"Value Area: {result.val} - {result.vah}")

Settings:
    Configurable bins and value area percentage
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import polars as pl
import math

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
# Settings
# ---------------------------------------------------------------------------
VOLUME_PROFILE_SETTINGS = {
    "num_bins": 50,                # Number of price bins
    "value_area_pct": 0.70,        # Value area contains 70% of volume
    "hvn_threshold": 1.5,          # HVN = bins with > 1.5x average volume
    "lvn_threshold": 0.5,          # LVN = bins with < 0.5x average volume
    "lookback_default": 50,        # Default bars for profile
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
@dataclass
class PriceBin:
    """Represents a price level bin in the volume profile."""
    price_low: float
    price_high: float
    price_mid: float
    volume: float
    volume_pct: float  # Percentage of total volume
    is_poc: bool
    is_hvn: bool
    is_lvn: bool
    bar_count: int


@dataclass
class VolumeProfileResult:
    """
    Complete Volume Profile analysis result.

    Attributes:
        poc: Point of Control (price with highest volume)
        vah: Value Area High
        val: Value Area Low
        value_area_volume: Total volume in value area
        value_area_pct: Actual percentage of volume in value area
        total_volume: Total volume analyzed
        num_bars: Number of bars analyzed
        range_high: Highest price in range
        range_low: Lowest price in range
        bins: List of all price bins
        hvn_levels: High Volume Node price levels
        lvn_levels: Low Volume Node price levels
        current_vs_poc: Current price position vs POC
        in_value_area: Whether current price is in value area
    """
    poc: float
    vah: float
    val: float
    value_area_volume: float
    value_area_pct: float
    total_volume: float
    num_bars: int
    range_high: float
    range_low: float
    bins: List[PriceBin]
    hvn_levels: List[float]
    lvn_levels: List[float]
    current_vs_poc: str  # "above", "below", "at"
    in_value_area: bool

    @property
    def value_area_size(self) -> float:
        return self.vah - self.val

    @property
    def range_size(self) -> float:
        return self.range_high - self.range_low


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------
def _create_bins(
    price_high: float,
    price_low: float,
    num_bins: int,
) -> List[Tuple[float, float, float]]:
    """Create price bins for volume profile."""
    if price_high <= price_low or num_bins <= 0:
        return []

    bin_size = (price_high - price_low) / num_bins
    bins = []

    for i in range(num_bins):
        bin_low = price_low + i * bin_size
        bin_high = price_low + (i + 1) * bin_size
        bin_mid = (bin_low + bin_high) / 2
        bins.append((bin_low, bin_high, bin_mid))

    return bins


def _assign_volume_to_bins(
    df: pl.DataFrame,
    bins: List[Tuple[float, float, float]],
) -> List[Tuple[float, int]]:
    """Assign volume to price bins based on OHLC."""
    if not bins:
        return []

    volumes = [0.0] * len(bins)
    counts = [0] * len(bins)

    # Get data
    highs = df["high"].to_list()
    lows = df["low"].to_list()
    closes = df["close"].to_list()
    vols = df["volume"].to_list() if "volume" in df.columns else [1.0] * len(highs)

    for h, l, c, v in zip(highs, lows, closes, vols):
        # Distribute volume across bins that the bar touched
        for i, (bin_low, bin_high, _) in enumerate(bins):
            # Check if bar overlaps with bin
            if h >= bin_low and l <= bin_high:
                # Calculate overlap
                overlap_low = max(l, bin_low)
                overlap_high = min(h, bin_high)
                bar_range = h - l if h > l else 1
                overlap_pct = (overlap_high - overlap_low) / bar_range

                # Assign proportional volume
                volumes[i] += v * overlap_pct
                counts[i] += 1

    return list(zip(volumes, counts))


def _calculate_value_area(
    bins: List[PriceBin],
    total_volume: float,
    value_area_pct: float,
) -> Tuple[float, float, float]:
    """
    Calculate Value Area using TPO (Time Price Opportunity) method.

    Returns (VAL, VAH, value_area_volume)
    """
    if not bins or total_volume <= 0:
        return 0.0, 0.0, 0.0

    # Find POC bin
    poc_bin = max(bins, key=lambda b: b.volume)
    poc_idx = bins.index(poc_bin)

    target_volume = total_volume * value_area_pct
    current_volume = poc_bin.volume

    # Expand from POC
    lower_idx = poc_idx
    upper_idx = poc_idx

    while current_volume < target_volume:
        # Check volume on each side
        lower_vol = bins[lower_idx - 1].volume if lower_idx > 0 else 0
        upper_vol = bins[upper_idx + 1].volume if upper_idx < len(bins) - 1 else 0

        if lower_vol == 0 and upper_vol == 0:
            break

        # Add the side with higher volume
        if lower_vol >= upper_vol and lower_idx > 0:
            lower_idx -= 1
            current_volume += bins[lower_idx].volume
        elif upper_idx < len(bins) - 1:
            upper_idx += 1
            current_volume += bins[upper_idx].volume
        elif lower_idx > 0:
            lower_idx -= 1
            current_volume += bins[lower_idx].volume
        else:
            break

    val = bins[lower_idx].price_low
    vah = bins[upper_idx].price_high

    return val, vah, current_volume


# ---------------------------------------------------------------------------
# Main Analysis Functions
# ---------------------------------------------------------------------------
def calculate_volume_profile(
    df: pl.DataFrame,
    num_bins: int = 50,
    lookback: int = 50,
    current_price: Optional[float] = None,
) -> VolumeProfileResult:
    """
    Calculate complete Volume Profile.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    num_bins : int
        Number of price bins for the profile
    lookback : int
        Number of bars to analyze
    current_price : float, optional
        Current price for comparison

    Returns
    -------
    VolumeProfileResult
        Complete volume profile analysis

    Example
    -------
    >>> result = calculate_volume_profile(df, num_bins=50)
    >>> print(f"POC: {result.poc:.2f}")
    >>> print(f"Value Area: {result.val:.2f} - {result.vah:.2f}")
    """
    if df is None or df.is_empty() or df.height < 5:
        return VolumeProfileResult(
            poc=0, vah=0, val=0, value_area_volume=0, value_area_pct=0,
            total_volume=0, num_bars=0, range_high=0, range_low=0,
            bins=[], hvn_levels=[], lvn_levels=[],
            current_vs_poc="at", in_value_area=True,
        )

    # Get window
    window = df.tail(lookback) if df.height > lookback else df

    if current_price is None:
        current_price = float(df["close"].tail(1).item())

    # Get range
    range_high = float(window["high"].max())
    range_low = float(window["low"].min())

    if range_high <= range_low:
        return VolumeProfileResult(
            poc=current_price, vah=current_price, val=current_price,
            value_area_volume=0, value_area_pct=0, total_volume=0,
            num_bars=window.height, range_high=range_high, range_low=range_low,
            bins=[], hvn_levels=[], lvn_levels=[],
            current_vs_poc="at", in_value_area=True,
        )

    # Create bins
    bin_specs = _create_bins(range_high, range_low, num_bins)

    # Assign volume
    volume_data = _assign_volume_to_bins(window, bin_specs)

    # Calculate total volume
    total_volume = sum(v for v, _ in volume_data)
    if total_volume <= 0:
        total_volume = 1.0

    # Calculate average volume per bin
    avg_bin_volume = total_volume / num_bins

    hvn_threshold = VOLUME_PROFILE_SETTINGS["hvn_threshold"]
    lvn_threshold = VOLUME_PROFILE_SETTINGS["lvn_threshold"]

    # Build PriceBin objects
    bins: List[PriceBin] = []
    poc_volume = 0
    poc_price = 0

    for i, ((bin_low, bin_high, bin_mid), (vol, count)) in enumerate(zip(bin_specs, volume_data)):
        vol_pct = vol / total_volume if total_volume > 0 else 0
        is_hvn = vol > avg_bin_volume * hvn_threshold
        is_lvn = vol < avg_bin_volume * lvn_threshold

        is_poc = False
        if vol > poc_volume:
            poc_volume = vol
            poc_price = bin_mid

        bins.append(PriceBin(
            price_low=bin_low,
            price_high=bin_high,
            price_mid=bin_mid,
            volume=vol,
            volume_pct=vol_pct,
            is_poc=False,  # Will set after finding max
            is_hvn=is_hvn,
            is_lvn=is_lvn,
            bar_count=count,
        ))

    # Mark POC
    for b in bins:
        if abs(b.price_mid - poc_price) < (range_high - range_low) / num_bins:
            b.is_poc = True
            break

    # Calculate Value Area
    value_area_pct = VOLUME_PROFILE_SETTINGS["value_area_pct"]
    val, vah, va_volume = _calculate_value_area(bins, total_volume, value_area_pct)

    # Get HVN and LVN levels
    hvn_levels = [b.price_mid for b in bins if b.is_hvn]
    lvn_levels = [b.price_mid for b in bins if b.is_lvn]

    # Current price vs POC
    if current_price > poc_price * 1.001:
        current_vs_poc = "above"
    elif current_price < poc_price * 0.999:
        current_vs_poc = "below"
    else:
        current_vs_poc = "at"

    # In value area?
    in_value_area = val <= current_price <= vah

    return VolumeProfileResult(
        poc=poc_price,
        vah=vah,
        val=val,
        value_area_volume=va_volume,
        value_area_pct=va_volume / total_volume if total_volume > 0 else 0,
        total_volume=total_volume,
        num_bars=window.height,
        range_high=range_high,
        range_low=range_low,
        bins=bins,
        hvn_levels=hvn_levels,
        lvn_levels=lvn_levels,
        current_vs_poc=current_vs_poc,
        in_value_area=in_value_area,
    )


def get_poc(df: pl.DataFrame, lookback: int = 50) -> float:
    """Get Point of Control (highest volume price level)."""
    result = calculate_volume_profile(df, lookback=lookback)
    return result.poc


def get_value_area(df: pl.DataFrame, lookback: int = 50) -> Tuple[float, float]:
    """Get Value Area (VAL, VAH)."""
    result = calculate_volume_profile(df, lookback=lookback)
    return result.val, result.vah


def summarize_volume_profile(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary dict for signal cards."""
    result = calculate_volume_profile(df)

    return {
        "poc": round(result.poc, 2),
        "vah": round(result.vah, 2),
        "val": round(result.val, 2),
        "value_area_size": round(result.value_area_size, 2),
        "value_area_pct": round(result.value_area_pct * 100, 1),
        "in_value_area": result.in_value_area,
        "current_vs_poc": result.current_vs_poc,
        "hvn_count": len(result.hvn_levels),
        "lvn_count": len(result.lvn_levels),
        "range_high": round(result.range_high, 2),
        "range_low": round(result.range_low, 2),
        "total_volume": round(result.total_volume, 0),
    }


def attach_volume_profile_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Attach volume profile columns to DataFrame."""
    result = calculate_volume_profile(df)

    return df.with_columns([
        pl.lit(round(result.poc, 2)).alias("vp_poc"),
        pl.lit(round(result.vah, 2)).alias("vp_vah"),
        pl.lit(round(result.val, 2)).alias("vp_val"),
        pl.lit(result.in_value_area).alias("vp_in_va"),
        pl.lit(result.current_vs_poc).alias("vp_vs_poc"),
    ])


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "volume_profile": calculate_volume_profile,
    "poc": get_poc,
    "value_area": get_value_area,
    "volume_profile_summary": summarize_volume_profile,
    "volume_profile_attach": attach_volume_profile_signals,
}

NAME = "volume_profile"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("VOLUME PROFILE TEST")
    print("=" * 60)

    np.random.seed(42)
    n = 60

    # Create data with concentrated volume at certain levels
    prices = [100.0]
    volumes = []

    for i in range(n):
        change = np.random.uniform(-0.8, 0.8)
        prices.append(prices[-1] + change)

        # High volume around 100-102 (POC area)
        if 99 <= prices[-1] <= 103:
            volumes.append(20000 + np.random.randint(0, 10000))
        else:
            volumes.append(8000 + np.random.randint(0, 5000))

    prices = prices[1:]  # Remove first placeholder

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.3, 0.8) for p in prices],
        "low": [p - np.random.uniform(0.3, 0.8) for p in prices],
        "close": prices,
        "volume": volumes,
    })

    result = calculate_volume_profile(df, num_bins=30, lookback=50)

    print(f"\n📊 VOLUME PROFILE:")
    print(f"   POC: {result.poc:.2f}")
    print(f"   VAH: {result.vah:.2f}")
    print(f"   VAL: {result.val:.2f}")
    print(f"   Value Area Size: {result.value_area_size:.2f}")

    print(f"\n📊 CURRENT PRICE:")
    current = float(df["close"].tail(1).item())
    print(f"   Price: {current:.2f}")
    print(f"   vs POC: {result.current_vs_poc}")
    print(f"   In Value Area: {result.in_value_area}")

    print(f"\n📊 VOLUME NODES:")
    print(f"   HVN Count: {len(result.hvn_levels)}")
    print(f"   LVN Count: {len(result.lvn_levels)}")
    if result.hvn_levels:
        print(f"   HVN Levels: {[round(x, 2) for x in result.hvn_levels[:5]]}")

    print(f"\n📊 SUMMARY:")
    summary = summarize_volume_profile(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ Volume Profile test complete!")
