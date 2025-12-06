# queen/technicals/microstructure/premium_discount.py
"""
Premium/Discount Zone Analysis Module
=====================================
Analyzes price position relative to a trading range to identify
premium (expensive) and discount (cheap) zones.

Key Concepts:
- Premium Zone: Upper 30% of range (price is expensive, look to sell)
- Equilibrium: Middle 40% of range (fair value)
- Discount Zone: Lower 30% of range (price is cheap, look to buy)

This is a core Smart Money Concept (SMC) that helps traders:
1. Buy in discount zones
2. Sell in premium zones
3. Avoid entries at equilibrium

Usage:
    from queen.technicals.microstructure.premium_discount import (
        analyze_premium_discount,
        get_zone_for_price,
        PriceZone,
    )

    result = analyze_premium_discount(df, lookback=50)
    if result.current_zone == PriceZone.DISCOUNT:
        print("Price is in discount - good for longs!")

Settings:
    Configurable zone boundaries via settings
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Literal, Dict, Any
from enum import Enum
import polars as pl

# ---------------------------------------------------------------------------
# Try to use existing helpers - DRY COMPLIANCE
# ---------------------------------------------------------------------------
try:
    from queen.helpers.swing_detection import find_swing_points, SwingType
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
PREMIUM_DISCOUNT_SETTINGS = {
    "premium_threshold": 0.7,      # Above 70% = premium
    "discount_threshold": 0.3,    # Below 30% = discount
    "lookback_default": 50,        # Default bars for range calculation
    "use_swing_range": True,       # Use swing H/L vs absolute H/L
    "extreme_premium": 0.85,       # Above 85% = extreme premium
    "extreme_discount": 0.15,      # Below 15% = extreme discount
    "equilibrium_center": 0.5,     # Center of equilibrium zone
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class PriceZone(str, Enum):
    EXTREME_PREMIUM = "extreme_premium"    # >85% - Very expensive
    PREMIUM = "premium"                     # 70-85% - Expensive
    EQUILIBRIUM = "equilibrium"             # 30-70% - Fair value
    DISCOUNT = "discount"                   # 15-30% - Cheap
    EXTREME_DISCOUNT = "extreme_discount"   # <15% - Very cheap


@dataclass
class ZoneLevel:
    """Represents a price level with zone information."""
    price: float
    zone: PriceZone
    position_pct: float  # 0-100 where in range
    distance_from_eq: float  # Distance from equilibrium (50%)


@dataclass
class PremiumDiscountResult:
    """
    Complete Premium/Discount analysis result.

    Attributes:
        range_high: Top of the trading range
        range_low: Bottom of the trading range
        range_size: Size of the range
        equilibrium: Middle price (50%)
        premium_start: Where premium zone begins
        discount_end: Where discount zone ends
        current_price: Current price being analyzed
        current_position: Position in range (0-1)
        current_zone: Which zone price is in
        bias: Trading bias based on zone
        fib_levels: Key Fibonacci levels within range
        zone_levels: All zone boundary levels
    """
    range_high: float
    range_low: float
    range_size: float
    equilibrium: float
    premium_start: float
    discount_end: float
    current_price: float
    current_position: float
    current_zone: PriceZone
    bias: Literal["bullish", "bearish", "neutral"]
    fib_levels: Dict[str, float]
    zone_levels: Dict[str, ZoneLevel]

    @property
    def is_premium(self) -> bool:
        return self.current_zone in [PriceZone.PREMIUM, PriceZone.EXTREME_PREMIUM]

    @property
    def is_discount(self) -> bool:
        return self.current_zone in [PriceZone.DISCOUNT, PriceZone.EXTREME_DISCOUNT]

    @property
    def is_extreme(self) -> bool:
        return self.current_zone in [PriceZone.EXTREME_PREMIUM, PriceZone.EXTREME_DISCOUNT]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _get_range_from_swings(df: pl.DataFrame, lookback: int) -> tuple[float, float]:
    """Get range using swing highs and lows."""
    if _USE_SHARED_SWING:
        try:
            points = find_swing_points(df, max_points=lookback)
            swing_highs = [p.price for p in points if p.type == SwingType.HIGH]
            swing_lows = [p.price for p in points if p.type == SwingType.LOW]

            if swing_highs and swing_lows:
                return max(swing_highs), min(swing_lows)
        except Exception:
            pass

    # Fallback to simple H/L
    return _get_range_absolute(df, lookback)


def _get_range_absolute(df: pl.DataFrame, lookback: int) -> tuple[float, float]:
    """Get range using absolute high/low."""
    window = df.tail(lookback) if df.height > lookback else df

    high = float(window["high"].max())
    low = float(window["low"].min())

    return high, low


def _calculate_position(price: float, range_high: float, range_low: float) -> float:
    """Calculate position in range (0 = bottom, 1 = top)."""
    range_size = range_high - range_low
    if range_size <= 0:
        return 0.5
    return (price - range_low) / range_size


def _determine_zone(position: float) -> PriceZone:
    """Determine which zone based on position."""
    extreme_premium = PREMIUM_DISCOUNT_SETTINGS["extreme_premium"]
    premium = PREMIUM_DISCOUNT_SETTINGS["premium_threshold"]
    discount = PREMIUM_DISCOUNT_SETTINGS["discount_threshold"]
    extreme_discount = PREMIUM_DISCOUNT_SETTINGS["extreme_discount"]

    if position >= extreme_premium:
        return PriceZone.EXTREME_PREMIUM
    elif position >= premium:
        return PriceZone.PREMIUM
    elif position <= extreme_discount:
        return PriceZone.EXTREME_DISCOUNT
    elif position <= discount:
        return PriceZone.DISCOUNT
    else:
        return PriceZone.EQUILIBRIUM


def _calculate_fib_levels(range_high: float, range_low: float) -> Dict[str, float]:
    """Calculate key Fibonacci retracement levels."""
    range_size = range_high - range_low

    return {
        "0.0": range_low,
        "0.236": range_low + range_size * 0.236,
        "0.382": range_low + range_size * 0.382,
        "0.5": range_low + range_size * 0.5,
        "0.618": range_low + range_size * 0.618,
        "0.786": range_low + range_size * 0.786,
        "1.0": range_high,
    }


# ---------------------------------------------------------------------------
# Main Analysis Functions
# ---------------------------------------------------------------------------
def analyze_premium_discount(
    df: pl.DataFrame,
    lookback: int = 50,
    current_price: Optional[float] = None,
    use_swings: bool = True,
) -> PremiumDiscountResult:
    """
    Analyze price position in Premium/Discount zones.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    lookback : int
        Bars to use for range calculation
    current_price : float, optional
        Price to analyze. If None, uses last close.
    use_swings : bool
        Use swing H/L instead of absolute H/L

    Returns
    -------
    PremiumDiscountResult
        Complete analysis with zone classification

    Example
    -------
    >>> result = analyze_premium_discount(df, lookback=50)
    >>> if result.is_discount:
    ...     print("Good zone for longs!")
    """
    if df is None or df.is_empty() or df.height < 5:
        return PremiumDiscountResult(
            range_high=0, range_low=0, range_size=0, equilibrium=0,
            premium_start=0, discount_end=0, current_price=0,
            current_position=0.5, current_zone=PriceZone.EQUILIBRIUM,
            bias="neutral", fib_levels={}, zone_levels={},
        )

    # Get current price
    if current_price is None:
        current_price = float(df["close"].tail(1).item())

    # Get range
    if use_swings and _USE_SHARED_SWING:
        range_high, range_low = _get_range_from_swings(df, lookback)
    else:
        range_high, range_low = _get_range_absolute(df, lookback)

    range_size = range_high - range_low

    # Calculate key levels
    premium_threshold = PREMIUM_DISCOUNT_SETTINGS["premium_threshold"]
    discount_threshold = PREMIUM_DISCOUNT_SETTINGS["discount_threshold"]

    equilibrium = range_low + range_size * 0.5
    premium_start = range_low + range_size * premium_threshold
    discount_end = range_low + range_size * discount_threshold

    # Determine current position and zone
    current_position = _calculate_position(current_price, range_high, range_low)
    current_zone = _determine_zone(current_position)

    # Determine bias
    if current_zone in [PriceZone.DISCOUNT, PriceZone.EXTREME_DISCOUNT]:
        bias = "bullish"  # Look for longs in discount
    elif current_zone in [PriceZone.PREMIUM, PriceZone.EXTREME_PREMIUM]:
        bias = "bearish"  # Look for shorts in premium
    else:
        bias = "neutral"  # Equilibrium - no clear edge

    # Calculate Fib levels
    fib_levels = _calculate_fib_levels(range_high, range_low)

    # Build zone levels
    zone_levels = {}
    for name, pct in [
        ("extreme_premium", 0.85),
        ("premium_start", 0.7),
        ("equilibrium", 0.5),
        ("discount_end", 0.3),
        ("extreme_discount", 0.15),
    ]:
        level_price = range_low + range_size * pct
        zone_levels[name] = ZoneLevel(
            price=level_price,
            zone=_determine_zone(pct),
            position_pct=pct * 100,
            distance_from_eq=abs(pct - 0.5) * 100,
        )

    return PremiumDiscountResult(
        range_high=range_high,
        range_low=range_low,
        range_size=range_size,
        equilibrium=equilibrium,
        premium_start=premium_start,
        discount_end=discount_end,
        current_price=current_price,
        current_position=current_position,
        current_zone=current_zone,
        bias=bias,
        fib_levels=fib_levels,
        zone_levels=zone_levels,
    )


def get_zone_for_price(
    price: float,
    df: pl.DataFrame,
    lookback: int = 50,
) -> PriceZone:
    """Get the zone classification for a specific price."""
    result = analyze_premium_discount(df, lookback, price)
    return result.current_zone


def is_discount_zone(df: pl.DataFrame, lookback: int = 50) -> bool:
    """Check if current price is in discount zone."""
    result = analyze_premium_discount(df, lookback)
    return result.is_discount


def is_premium_zone(df: pl.DataFrame, lookback: int = 50) -> bool:
    """Check if current price is in premium zone."""
    result = analyze_premium_discount(df, lookback)
    return result.is_premium


def summarize_premium_discount(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary dict for signal cards."""
    result = analyze_premium_discount(df)

    return {
        "range_high": round(result.range_high, 2),
        "range_low": round(result.range_low, 2),
        "range_size": round(result.range_size, 2),
        "equilibrium": round(result.equilibrium, 2),
        "current_position_pct": round(result.current_position * 100, 1),
        "current_zone": result.current_zone.value,
        "is_premium": result.is_premium,
        "is_discount": result.is_discount,
        "is_extreme": result.is_extreme,
        "zone_bias": result.bias,
        "premium_level": round(result.premium_start, 2),
        "discount_level": round(result.discount_end, 2),
        "fib_50": round(result.fib_levels.get("0.5", 0), 2),
        "fib_618": round(result.fib_levels.get("0.618", 0), 2),
        "fib_382": round(result.fib_levels.get("0.382", 0), 2),
    }


def attach_premium_discount_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Attach premium/discount columns to DataFrame."""
    result = analyze_premium_discount(df)

    return df.with_columns([
        pl.lit(result.current_zone.value).alias("price_zone"),
        pl.lit(round(result.current_position * 100, 1)).alias("range_position_pct"),
        pl.lit(result.bias).alias("zone_bias"),
        pl.lit(result.is_discount).alias("is_discount"),
        pl.lit(result.is_premium).alias("is_premium"),
    ])


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "premium_discount": analyze_premium_discount,
    "get_zone": get_zone_for_price,
    "is_discount": is_discount_zone,
    "is_premium": is_premium_zone,
    "premium_discount_summary": summarize_premium_discount,
    "premium_discount_attach": attach_premium_discount_signals,
}

NAME = "premium_discount"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("PREMIUM/DISCOUNT ZONE TEST")
    print("=" * 60)
    print(f"Using shared swing helper: {_USE_SHARED_SWING}")

    np.random.seed(42)
    n = 60

    # Create a range-bound market
    prices = [100.0]
    for i in range(1, n):
        # Oscillate between 95 and 110
        change = np.random.uniform(-0.8, 0.8)
        new_price = prices[-1] + change
        new_price = max(95, min(110, new_price))  # Bound to range
        prices.append(new_price)

    # Put current price in discount
    prices[-1] = 96.5

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.3, 0.8) for p in prices],
        "low": [p - np.random.uniform(0.3, 0.8) for p in prices],
        "close": prices,
        "volume": [10000 + np.random.randint(-2000, 2000) for _ in range(n)],
    })

    result = analyze_premium_discount(df, lookback=50)

    print(f"\n📊 RANGE ANALYSIS:")
    print(f"   Range High: {result.range_high:.2f}")
    print(f"   Range Low: {result.range_low:.2f}")
    print(f"   Range Size: {result.range_size:.2f}")
    print(f"   Equilibrium: {result.equilibrium:.2f}")

    print(f"\n📊 ZONE LEVELS:")
    print(f"   Premium Start: {result.premium_start:.2f}")
    print(f"   Discount End: {result.discount_end:.2f}")

    print(f"\n📊 CURRENT PRICE:")
    print(f"   Price: {result.current_price:.2f}")
    print(f"   Position: {result.current_position * 100:.1f}%")
    print(f"   Zone: {result.current_zone.value}")
    print(f"   Bias: {result.bias}")

    print(f"\n📊 FIBONACCI LEVELS:")
    for fib, price in result.fib_levels.items():
        print(f"   {fib}: {price:.2f}")

    print(f"\n📊 SUMMARY:")
    summary = summarize_premium_discount(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    # Test different prices
    print(f"\n📊 ZONE CHECK FOR DIFFERENT PRICES:")
    for test_price in [96, 100, 105, 109]:
        zone = get_zone_for_price(test_price, df)
        print(f"   Price {test_price}: {zone.value}")

    print("\n" + "=" * 60)
    print("✅ Premium/Discount test complete!")
