# queen/technicals/microstructure/liquidity.py
"""Liquidity Sweep Detection Module
================================
Identifies liquidity sweeps - where price briefly breaks a level to
trigger stops before reversing sharply.

Liquidity Concepts:
- Buy-side Liquidity: Stops above swing highs (targeted by upward sweeps)
- Sell-side Liquidity: Stops below swing lows (targeted by downward sweeps)
- Sweep: Price takes out liquidity then reverses
- Run: Price takes out liquidity and continues

A Liquidity Sweep is detected when:
1. Price breaks above/below a swing high/low
2. Wick extends beyond the level by significant amount
3. Candle closes back inside the level
4. Often followed by reversal

Usage:
    from queen.technicals.microstructure.liquidity import (
        detect_liquidity_sweeps,
        detect_liquidity_pools,
        summarize_liquidity,
        LiquiditySweep,
    )

    # Detect sweeps
    result = detect_liquidity_sweeps(df)

    # Get liquidity pools (potential targets)
    pools = detect_liquidity_pools(df)

Settings:
    All thresholds configurable via settings/breakout_settings.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

import polars as pl

# ---------------------------------------------------------------------------
# Try to use existing helpers
# ---------------------------------------------------------------------------
try:
    from queen.helpers.swing_detection import SwingPoint, SwingType, find_swing_points
    _USE_SWING_HELPER = True
except ImportError:
    _USE_SWING_HELPER = False

    # Define fallback
    class SwingType(str, Enum):
        HIGH = "high"
        LOW = "low"

    @dataclass
    class SwingPoint:
        type: SwingType
        price: float
        bar_index: int
        timestamp: Optional[str] = None

try:
    from queen.helpers.ta_math import atr_wilder
    _USE_EXISTING_ATR = True
except ImportError:
    _USE_EXISTING_ATR = False

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
try:
    from queen.settings.breakout_settings import LIQUIDITY_SETTINGS
except ImportError:
    LIQUIDITY_SETTINGS = {
        "sweep_min_wick_atr": 0.3,      # Min wick beyond level (ATR ratio)
        "sweep_max_close_beyond": 0.1,   # Max close beyond level (ATR ratio)
        "pool_min_touches": 2,           # Min times level tested
        "pool_tolerance_pct": 0.002,     # Price tolerance for "same level"
        "lookback_default": 50,          # Default lookback
        "max_sweeps_to_track": 10,       # Max sweeps to return
        "equal_level_tolerance": 0.003,  # Tolerance for equal highs/lows
    }


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class SweepType(str, Enum):
    BULLISH = "bullish"   # Swept lows, reversed up
    BEARISH = "bearish"   # Swept highs, reversed down


class PoolType(str, Enum):
    BUY_SIDE = "buy_side"     # Above swing highs (stops for shorts)
    SELL_SIDE = "sell_side"   # Below swing lows (stops for longs)


@dataclass
class LiquiditySweep:
    """Represents a liquidity sweep event.

    Attributes:
        type: SweepType.BULLISH or BEARISH
        level_swept: The swing level that was swept
        wick_high: Highest point of the sweep wick
        wick_low: Lowest point of the sweep wick
        close_price: Where the candle closed
        sweep_size: How far beyond the level
        bar_index: Where the sweep occurred
        reversal_confirmed: Did price reverse after?
        strength: Sweep strength 0-100
        timestamp: Optional timestamp

    """

    type: SweepType
    level_swept: float
    wick_high: float
    wick_low: float
    close_price: float
    sweep_size: float
    bar_index: int
    reversal_confirmed: bool
    strength: float
    timestamp: Optional[str] = None

    def __repr__(self) -> str:
        confirmed = "confirmed" if self.reversal_confirmed else "pending"
        return f"LiquiditySweep({self.type.value}, level={self.level_swept:.2f}, {confirmed})"


@dataclass
class LiquidityPool:
    """Represents a liquidity pool - an area where stops likely accumulate.

    Attributes:
        type: PoolType.BUY_SIDE or SELL_SIDE
        level: Price level of the pool
        touches: How many times this level was tested
        strength: Pool strength (more touches = more liquidity)
        bar_indices: Bars that touched this level
        last_touch_idx: Most recent touch

    """

    type: PoolType
    level: float
    touches: int
    strength: float
    bar_indices: List[int]
    last_touch_idx: int

    def __repr__(self) -> str:
        return f"LiquidityPool({self.type.value}, {self.level:.2f}, touches={self.touches})"


@dataclass
class LiquidityResult:
    """Complete liquidity analysis result.

    Attributes:
        sweeps: List of detected sweeps
        buy_side_pools: Liquidity above (short stops)
        sell_side_pools: Liquidity below (long stops)
        recent_sweep: Most recent sweep
        nearest_buy_side: Nearest buy-side liquidity
        nearest_sell_side: Nearest sell-side liquidity
        swept_recently: Was there a sweep in last N bars?
        bias: Based on sweep direction

    """

    sweeps: List[LiquiditySweep]
    buy_side_pools: List[LiquidityPool]
    sell_side_pools: List[LiquidityPool]
    recent_sweep: Optional[LiquiditySweep]
    nearest_buy_side: Optional[LiquidityPool]
    nearest_sell_side: Optional[LiquidityPool]
    swept_recently: bool
    bias: Literal["bullish", "bearish", "neutral"]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _calculate_atr(df: pl.DataFrame, period: int = 14) -> float:
    """Get latest ATR value."""
    if _USE_EXISTING_ATR:
        try:
            high = df["high"].to_numpy()
            low = df["low"].to_numpy()
            close = df["close"].to_numpy()
            atr_arr = atr_wilder(high, low, close, period)
            for v in reversed(atr_arr):
                if v is not None and not (isinstance(v, float) and v != v):
                    return float(v)
        except Exception:
            pass

    # Local implementation
    df_with_atr = df.with_columns([
        (pl.col("high") - pl.col("low")).alias("_tr1"),
        (pl.col("high") - pl.col("close").shift(1)).abs().alias("_tr2"),
        (pl.col("low") - pl.col("close").shift(1)).abs().alias("_tr3"),
    ])

    df_with_atr = df_with_atr.with_columns(
        pl.max_horizontal("_tr1", "_tr2", "_tr3").alias("_tr")
    )

    df_with_atr = df_with_atr.with_columns(
        pl.col("_tr").rolling_mean(window_size=period).alias("_atr")
    )

    atr_list = df_with_atr["_atr"].to_list()
    for v in reversed(atr_list):
        if v is not None:
            return v
    return 1.0


def _find_swing_points_local(
    df: pl.DataFrame,
    max_points: int = 20,
) -> List[SwingPoint]:
    """Local swing detection if helper not available."""
    if _USE_SWING_HELPER:
        try:
            return find_swing_points(df, max_points=max_points)
        except Exception:
            pass

    # Local implementation
    n = df.height
    if n < 3:
        return []

    highs = df["high"].to_list()
    lows = df["low"].to_list()

    points = []
    for i in range(1, n - 1):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            points.append(SwingPoint(
                type=SwingType.HIGH,
                price=float(highs[i]),
                bar_index=i,
            ))
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            points.append(SwingPoint(
                type=SwingType.LOW,
                price=float(lows[i]),
                bar_index=i,
            ))

    return points[-max_points:]


def _find_equal_levels(
    swings: List[SwingPoint],
    tolerance: float,
) -> Dict[float, List[SwingPoint]]:
    """Group swing points that are at approximately the same level.
    These form liquidity pools.
    """
    if not swings:
        return {}

    clusters: Dict[float, List[SwingPoint]] = {}

    for swing in swings:
        found_cluster = False
        for level in list(clusters.keys()):
            if abs(swing.price - level) / level < tolerance:
                clusters[level].append(swing)
                found_cluster = True
                break

        if not found_cluster:
            clusters[swing.price] = [swing]

    return clusters


# ---------------------------------------------------------------------------
# Main Detection Functions
# ---------------------------------------------------------------------------
def detect_liquidity_pools(
    df: pl.DataFrame,
    lookback: int = 50,
    current_price: Optional[float] = None,
) -> tuple[List[LiquidityPool], List[LiquidityPool]]:
    """Detect liquidity pools above and below current price.

    Liquidity pools form at:
    - Equal highs (buy-side liquidity)
    - Equal lows (sell-side liquidity)
    - Prominent swing levels

    Returns:
        (buy_side_pools, sell_side_pools)

    """
    if df is None or df.is_empty():
        return [], []

    if current_price is None:
        current_price = float(df["close"].tail(1).item())

    tolerance = LIQUIDITY_SETTINGS["equal_level_tolerance"]
    min_touches = LIQUIDITY_SETTINGS["pool_min_touches"]

    # Get swing points
    swings = _find_swing_points_local(df, max_points=30)

    # Separate highs and lows
    swing_highs = [s for s in swings if s.type == SwingType.HIGH]
    swing_lows = [s for s in swings if s.type == SwingType.LOW]

    # Find equal highs (buy-side liquidity)
    high_clusters = _find_equal_levels(swing_highs, tolerance)
    buy_side_pools = []

    for level, points in high_clusters.items():
        if len(points) >= 1:  # Even single swing high is a pool
            pool = LiquidityPool(
                type=PoolType.BUY_SIDE,
                level=level,
                touches=len(points),
                strength=min(100.0, len(points) * 25.0),
                bar_indices=[p.bar_index for p in points],
                last_touch_idx=max(p.bar_index for p in points),
            )
            if level > current_price:  # Only above current price
                buy_side_pools.append(pool)

    # Find equal lows (sell-side liquidity)
    low_clusters = _find_equal_levels(swing_lows, tolerance)
    sell_side_pools = []

    for level, points in low_clusters.items():
        if len(points) >= 1:
            pool = LiquidityPool(
                type=PoolType.SELL_SIDE,
                level=level,
                touches=len(points),
                strength=min(100.0, len(points) * 25.0),
                bar_indices=[p.bar_index for p in points],
                last_touch_idx=max(p.bar_index for p in points),
            )
            if level < current_price:  # Only below current price
                sell_side_pools.append(pool)

    # Sort by proximity to price
    buy_side_pools.sort(key=lambda p: p.level)
    sell_side_pools.sort(key=lambda p: -p.level)

    return buy_side_pools, sell_side_pools


def detect_liquidity_sweeps(
    df: pl.DataFrame,
    lookback: int = 50,
) -> LiquidityResult:
    """Detect liquidity sweeps in price data.

    A sweep occurs when:
    1. Price wicks beyond a swing level
    2. Closes back inside the level
    3. Often reverses afterward

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    lookback : int
        How many bars back to search

    Returns
    -------
    LiquidityResult
        Complete liquidity analysis

    """
    if df is None or df.is_empty() or df.height < 5:
        return LiquidityResult(
            sweeps=[],
            buy_side_pools=[],
            sell_side_pools=[],
            recent_sweep=None,
            nearest_buy_side=None,
            nearest_sell_side=None,
            swept_recently=False,
            bias="neutral",
        )

    current_price = float(df["close"].tail(1).item())
    atr = _calculate_atr(df)

    min_wick = LIQUIDITY_SETTINGS["sweep_min_wick_atr"]
    max_close = LIQUIDITY_SETTINGS["sweep_max_close_beyond"]
    max_sweeps = LIQUIDITY_SETTINGS["max_sweeps_to_track"]

    # Get swing points
    swings = _find_swing_points_local(df, max_points=30)

    # Get OHLC
    opens = df["open"].to_list()
    highs = df["high"].to_list()
    lows = df["low"].to_list()
    closes = df["close"].to_list()

    timestamps = None
    if "timestamp" in df.columns:
        timestamps = df["timestamp"].cast(pl.Utf8).to_list()

    n = df.height
    start_idx = max(0, n - lookback)

    sweeps: List[LiquiditySweep] = []

    # For each bar, check if it swept any swing level
    for i in range(start_idx, n):
        h, l, c = highs[i], lows[i], closes[i]

        # Check for bearish sweep (swept highs above, closed below)
        for swing in swings:
            if swing.type != SwingType.HIGH:
                continue
            if swing.bar_index >= i:
                continue

            level = swing.price

            # Did we wick above the level?
            if h > level:
                sweep_size = h - level

                # Is sweep significant?
                if sweep_size >= min_wick * atr:
                    # Did we close back below?
                    if c <= level + (max_close * atr):
                        # Check for reversal (next bar lower?)
                        reversal = False
                        if i + 1 < n:
                            reversal = closes[i + 1] < c

                        sweep = LiquiditySweep(
                            type=SweepType.BEARISH,
                            level_swept=level,
                            wick_high=h,
                            wick_low=l,
                            close_price=c,
                            sweep_size=sweep_size,
                            bar_index=i,
                            reversal_confirmed=reversal,
                            strength=min(100.0, (sweep_size / atr) * 30),
                            timestamp=timestamps[i] if timestamps else None,
                        )
                        sweeps.append(sweep)

        # Check for bullish sweep (swept lows below, closed above)
        for swing in swings:
            if swing.type != SwingType.LOW:
                continue
            if swing.bar_index >= i:
                continue

            level = swing.price

            # Did we wick below the level?
            if l < level:
                sweep_size = level - l

                # Is sweep significant?
                if sweep_size >= min_wick * atr:
                    # Did we close back above?
                    if c >= level - (max_close * atr):
                        # Check for reversal
                        reversal = False
                        if i + 1 < n:
                            reversal = closes[i + 1] > c

                        sweep = LiquiditySweep(
                            type=SweepType.BULLISH,
                            level_swept=level,
                            wick_high=h,
                            wick_low=l,
                            close_price=c,
                            sweep_size=sweep_size,
                            bar_index=i,
                            reversal_confirmed=reversal,
                            strength=min(100.0, (sweep_size / atr) * 30),
                            timestamp=timestamps[i] if timestamps else None,
                        )
                        sweeps.append(sweep)

    # Keep most recent/strongest
    sweeps = sorted(sweeps, key=lambda x: (-x.bar_index, -x.strength))[:max_sweeps]

    # Get liquidity pools
    buy_side_pools, sell_side_pools = detect_liquidity_pools(df, current_price=current_price)

    # Recent sweep check
    recent_sweep = sweeps[0] if sweeps else None
    swept_recently = recent_sweep is not None and recent_sweep.bar_index >= n - 5

    # Determine bias from sweeps
    bullish_sweeps = sum(1 for s in sweeps if s.type == SweepType.BULLISH and s.bar_index >= n - 10)
    bearish_sweeps = sum(1 for s in sweeps if s.type == SweepType.BEARISH and s.bar_index >= n - 10)

    if bullish_sweeps > bearish_sweeps:
        bias = "bullish"
    elif bearish_sweeps > bullish_sweeps:
        bias = "bearish"
    else:
        bias = "neutral"

    return LiquidityResult(
        sweeps=sweeps,
        buy_side_pools=buy_side_pools,
        sell_side_pools=sell_side_pools,
        recent_sweep=recent_sweep,
        nearest_buy_side=buy_side_pools[0] if buy_side_pools else None,
        nearest_sell_side=sell_side_pools[0] if sell_side_pools else None,
        swept_recently=swept_recently,
        bias=bias,
    )


def summarize_liquidity(
    df: pl.DataFrame,
) -> Dict[str, Any]:
    """Get summary dict for signal cards.

    Returns dict with keys:
    - liquidity_above: Nearest buy-side level
    - liquidity_below: Nearest sell-side level
    - swept_recently: bool
    - sweep_type: "bullish"/"bearish"/None
    - sweep_level: Level that was swept
    - liquidity_bias: Overall bias
    """
    result = detect_liquidity_sweeps(df)

    return {
        "liquidity_above": result.nearest_buy_side.level if result.nearest_buy_side else None,
        "liquidity_below": result.nearest_sell_side.level if result.nearest_sell_side else None,
        "swept_recently": result.swept_recently,
        "sweep_type": result.recent_sweep.type.value if result.recent_sweep else None,
        "sweep_level": result.recent_sweep.level_swept if result.recent_sweep else None,
        "liquidity_bias": result.bias,
        "buy_side_count": len(result.buy_side_pools),
        "sell_side_count": len(result.sell_side_pools),
        "total_sweeps": len(result.sweeps),
    }


def attach_liquidity_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Attach liquidity columns to DataFrame."""
    summary = summarize_liquidity(df)

    return df.with_columns([
        pl.lit(summary["liquidity_above"]).alias("liquidity_above"),
        pl.lit(summary["liquidity_below"]).alias("liquidity_below"),
        pl.lit(summary["swept_recently"]).alias("swept_recently"),
        pl.lit(summary["liquidity_bias"]).alias("liquidity_bias"),
    ])


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "liquidity_sweeps": detect_liquidity_sweeps,
    "liquidity_pools": detect_liquidity_pools,
    "liquidity_summary": summarize_liquidity,
    "liquidity_attach": attach_liquidity_signals,
}

NAME = "liquidity"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("LIQUIDITY DETECTION TEST")
    print("=" * 60)

    # Create test data with liquidity sweep setup
    np.random.seed(42)
    n = 50

    # Create pattern with equal highs and a sweep
    prices = [100.0]
    for i in range(1, n):
        if i in [10, 20, 30]:
            # Create equal highs (liquidity pool)
            change = 2.0
        elif i == 35:
            # Sweep above equal highs then reverse
            change = 3.0  # Spike up
        elif i == 36:
            # Reversal down
            change = -4.0
        elif i in [15, 25]:
            # Create equal lows
            change = -2.0
        else:
            change = np.random.uniform(-0.5, 0.5)

        prices.append(prices[-1] + change)

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.5, 1.5) for p in prices],
        "low": [p - np.random.uniform(0.5, 1.5) for p in prices],
        "close": [prices[i] + np.random.uniform(-0.3, 0.3) for i in range(n)],
        "volume": [10000 + np.random.randint(-2000, 2000) for _ in range(n)],
    })

    # Run detection
    result = detect_liquidity_sweeps(df)

    print("\n📊 LIQUIDITY POOLS:")
    print(f"   Buy-side (above): {len(result.buy_side_pools)}")
    for pool in result.buy_side_pools[:3]:
        print(f"      {pool.level:.2f} | Touches: {pool.touches} | Strength: {pool.strength:.0f}")

    print(f"   Sell-side (below): {len(result.sell_side_pools)}")
    for pool in result.sell_side_pools[:3]:
        print(f"      {pool.level:.2f} | Touches: {pool.touches} | Strength: {pool.strength:.0f}")

    print(f"\n📊 SWEEPS DETECTED: {len(result.sweeps)}")
    for sweep in result.sweeps[:3]:
        confirmed = "✅ Confirmed" if sweep.reversal_confirmed else "⏳ Pending"
        print(f"   {sweep.type.value} | Level: {sweep.level_swept:.2f} | {confirmed}")

    print("\n📊 CURRENT STATE:")
    print(f"   Swept Recently: {result.swept_recently}")
    print(f"   Bias: {result.bias}")

    # Test summary
    print("\n📊 SUMMARY DICT:")
    summary = summarize_liquidity(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ Liquidity detection test complete!")
