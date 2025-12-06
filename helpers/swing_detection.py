# queen/helpers/swing_detection.py
"""
Swing Point Detection Helper
============================
Canonical source for swing high/low detection.
Used by structure.py, false_breakout.py, and order_blocks.py.

A swing high/low is detected using the 3-bar fractal method:
- Swing High: bar[i].high > bar[i-1].high AND bar[i].high > bar[i+1].high
- Swing Low:  bar[i].low  < bar[i-1].low  AND bar[i].low  < bar[i+1].low

Usage:
    from queen.helpers.swing_detection import (
        find_swing_points,
        find_swing_prices,
        SwingPoint,
        SwingType,
    )

    # Full swing points with indices
    points = find_swing_points(df, max_points=5)

    # Just prices (legacy compatibility)
    highs, lows = find_swing_prices(df, max_points=3)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional, Literal
import polars as pl

# ---------------------------------------------------------------------------
# Try to use existing helpers - DRY COMPLIANCE
# ---------------------------------------------------------------------------
try:
    from queen.helpers.ta_math import atr_wilder
    _USE_EXISTING_ATR = True
except ImportError:
    _USE_EXISTING_ATR = False

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
try:
    from queen.settings.structure_settings import SWING_SETTINGS
except ImportError:
    SWING_SETTINGS = {
        "default_max_points": 5,
        "min_bars_required": 3,
        "fractal_window": 1,  # 1 = 3-bar fractal, 2 = 5-bar fractal
    }


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class SwingType(str, Enum):
    """Type of swing point"""
    HIGH = "high"
    LOW = "low"


@dataclass
class SwingPoint:
    """
    Represents a swing high or low point.

    Attributes:
        type: SwingType.HIGH or SwingType.LOW
        price: The price at the swing point
        bar_index: Index in the DataFrame
        timestamp: Optional timestamp if available
    """
    type: SwingType
    price: float
    bar_index: int
    timestamp: Optional[str] = None

    def __repr__(self) -> str:
        return f"SwingPoint({self.type.value}, {self.price:.2f}, idx={self.bar_index})"


# ---------------------------------------------------------------------------
# Core Detection Functions
# ---------------------------------------------------------------------------
def find_swing_points(
    df: pl.DataFrame,
    *,
    high_col: str = "high",
    low_col: str = "low",
    timestamp_col: str = "timestamp",
    max_points: int = 5,
    fractal_window: int = 1,
) -> List[SwingPoint]:
    """
    Detect swing highs and lows using fractal method.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV DataFrame
    high_col : str
        Column name for highs
    low_col : str
        Column name for lows
    timestamp_col : str
        Column name for timestamps (optional)
    max_points : int
        Maximum swing points to return (most recent)
    fractal_window : int
        Number of bars on each side (1 = 3-bar, 2 = 5-bar fractal)

    Returns
    -------
    List[SwingPoint]
        List of swing points, sorted by bar_index ascending

    Example
    -------
    >>> points = find_swing_points(df, max_points=5)
    >>> for p in points:
    ...     print(f"{p.type.value} at {p.price} (bar {p.bar_index})")
    """
    if df is None or df.is_empty():
        return []

    n = df.height
    min_bars = 2 * fractal_window + 1

    if n < min_bars:
        return []

    # Extract columns
    highs = df[high_col].cast(pl.Float64).to_list()
    lows = df[low_col].cast(pl.Float64).to_list()

    # Get timestamps if available
    timestamps = None
    if timestamp_col in df.columns:
        timestamps = df[timestamp_col].cast(pl.Utf8).to_list()

    swing_points: List[SwingPoint] = []

    # Detect swings
    for i in range(fractal_window, n - fractal_window):
        # Check swing high
        is_swing_high = True
        for j in range(1, fractal_window + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing_high = False
                break

        if is_swing_high:
            swing_points.append(SwingPoint(
                type=SwingType.HIGH,
                price=float(highs[i]),
                bar_index=i,
                timestamp=timestamps[i] if timestamps else None,
            ))

        # Check swing low
        is_swing_low = True
        for j in range(1, fractal_window + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing_low = False
                break

        if is_swing_low:
            swing_points.append(SwingPoint(
                type=SwingType.LOW,
                price=float(lows[i]),
                bar_index=i,
                timestamp=timestamps[i] if timestamps else None,
            ))

    # Sort by bar_index and return last max_points
    swing_points.sort(key=lambda p: p.bar_index)

    if max_points and len(swing_points) > max_points:
        swing_points = swing_points[-max_points:]

    return swing_points


def find_swing_prices(
    df: pl.DataFrame,
    *,
    high_col: str = "high",
    low_col: str = "low",
    max_points: int = 3,
    fractal_window: int = 1,
) -> Tuple[List[float], List[float]]:
    """
    Legacy function: Returns swing prices only (no indices).

    This maintains backwards compatibility with structure.py.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV DataFrame
    max_points : int
        Maximum points per type (highs and lows separately)

    Returns
    -------
    Tuple[List[float], List[float]]
        (swing_highs, swing_lows) as price lists

    Example
    -------
    >>> highs, lows = find_swing_prices(df, max_points=3)
    >>> print(f"Recent swing highs: {highs}")
    """
    points = find_swing_points(
        df,
        high_col=high_col,
        low_col=low_col,
        max_points=max_points * 2,  # Get more, then filter
        fractal_window=fractal_window,
    )

    swing_highs = [p.price for p in points if p.type == SwingType.HIGH]
    swing_lows = [p.price for p in points if p.type == SwingType.LOW]

    # Keep only last max_points of each
    return swing_highs[-max_points:], swing_lows[-max_points:]


def find_swing_highs(
    df: pl.DataFrame,
    *,
    high_col: str = "high",
    max_points: int = 5,
) -> List[SwingPoint]:
    """Get only swing highs."""
    points = find_swing_points(df, high_col=high_col, max_points=max_points * 2)
    highs = [p for p in points if p.type == SwingType.HIGH]
    return highs[-max_points:]


def find_swing_lows(
    df: pl.DataFrame,
    *,
    low_col: str = "low",
    max_points: int = 5,
) -> List[SwingPoint]:
    """Get only swing lows."""
    points = find_swing_points(df, low_col=low_col, max_points=max_points * 2)
    lows = [p for p in points if p.type == SwingType.LOW]
    return lows[-max_points:]


def get_nearest_swing(
    df: pl.DataFrame,
    current_price: float,
    swing_type: Literal["high", "low", "any"] = "any",
) -> Optional[SwingPoint]:
    """
    Find the nearest swing point to current price.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    current_price : float
        Current price to compare
    swing_type : str
        "high", "low", or "any"

    Returns
    -------
    SwingPoint or None
    """
    points = find_swing_points(df, max_points=20)

    if swing_type == "high":
        points = [p for p in points if p.type == SwingType.HIGH]
    elif swing_type == "low":
        points = [p for p in points if p.type == SwingType.LOW]

    if not points:
        return None

    # Find nearest by price distance
    nearest = min(points, key=lambda p: abs(p.price - current_price))
    return nearest


def get_swing_above(
    df: pl.DataFrame,
    current_price: float,
) -> Optional[SwingPoint]:
    """Find the nearest swing high ABOVE current price."""
    points = find_swing_points(df, max_points=20)
    above = [p for p in points if p.type == SwingType.HIGH and p.price > current_price]

    if not above:
        return None

    return min(above, key=lambda p: p.price)


def get_swing_below(
    df: pl.DataFrame,
    current_price: float,
) -> Optional[SwingPoint]:
    """Find the nearest swing low BELOW current price."""
    points = find_swing_points(df, max_points=20)
    below = [p for p in points if p.type == SwingType.LOW and p.price < current_price]

    if not below:
        return None

    return max(below, key=lambda p: p.price)


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "swing_points": find_swing_points,
    "swing_prices": find_swing_prices,
    "swing_highs": find_swing_highs,
    "swing_lows": find_swing_lows,
    "swing_nearest": get_nearest_swing,
    "swing_above": get_swing_above,
    "swing_below": get_swing_below,
}

NAME = "swing_detection"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("SWING DETECTION TEST")
    print("=" * 60)

    # Create test data with clear swings
    np.random.seed(42)
    n = 30

    # Create a wave pattern
    t = np.linspace(0, 4 * np.pi, n)
    base = 100 + 5 * np.sin(t)
    noise = np.random.uniform(-0.5, 0.5, n)

    prices = base + noise

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{i+1:02d}" for i in range(n)],
        "high": [p + np.random.uniform(0.5, 1.5) for p in prices],
        "low": [p - np.random.uniform(0.5, 1.5) for p in prices],
        "close": prices.tolist(),
    })

    # Test find_swing_points
    print("\n📊 All Swing Points:")
    points = find_swing_points(df, max_points=10)
    for p in points:
        print(f"  {p}")

    # Test find_swing_prices (legacy)
    print("\n📊 Legacy Format (prices only):")
    highs, lows = find_swing_prices(df, max_points=3)
    print(f"  Swing Highs: {[f'{h:.2f}' for h in highs]}")
    print(f"  Swing Lows:  {[f'{l:.2f}' for l in lows]}")

    # Test nearest swing
    current = 100.0
    print(f"\n📊 Nearest to {current}:")
    nearest = get_nearest_swing(df, current)
    if nearest:
        print(f"  {nearest}")

    above = get_swing_above(df, current)
    below = get_swing_below(df, current)
    print(f"  Above: {above}")
    print(f"  Below: {below}")

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
