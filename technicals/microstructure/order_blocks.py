# queen/technicals/microstructure/order_blocks.py
"""
Order Block Detection Module
============================
Identifies institutional order blocks - zones where smart money
entered positions before a significant move.

Order Block Types:
- Bullish OB: Last bearish candle before a bullish impulse move
- Bearish OB: Last bullish candle before a bearish impulse move

An Order Block is valid when:
1. Followed by an impulse move (> 1.5x ATR)
2. The OB candle shows strong momentum (large body)
3. Not yet mitigated (price hasn't returned to OB zone)

Usage:
    from queen.technicals.microstructure.order_blocks import (
        detect_order_blocks,
        summarize_order_blocks,
        OrderBlock,
    )

    result = detect_order_blocks(df, lookback=50)
    for ob in result.bullish_obs:
        print(f"Bullish OB at {ob.zone_low:.2f} - {ob.zone_high:.2f}")

Settings:
    All thresholds configurable via settings/breakout_settings.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Literal, Dict, Any
from enum import Enum
import polars as pl

# ---------------------------------------------------------------------------
# Try to use existing helpers
# ---------------------------------------------------------------------------
try:
    from queen.helpers.ta_math import atr_wilder
    _USE_EXISTING_ATR = True
except ImportError:
    _USE_EXISTING_ATR = False

try:
    from queen.helpers.swing_detection import find_swing_points, SwingPoint
    _USE_SWING_HELPER = True
except ImportError:
    _USE_SWING_HELPER = False

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
try:
    from queen.settings.breakout_settings import ORDER_BLOCK_SETTINGS
except ImportError:
    ORDER_BLOCK_SETTINGS = {
        "min_impulse_atr_ratio": 1.5,    # Impulse must be > 1.5x ATR
        "min_ob_body_ratio": 0.5,         # OB candle body > 50% of range
        "max_age_bars": 50,               # How far back to look
        "mitigation_tolerance": 0.1,      # 10% into zone = mitigated
        "max_obs_to_track": 10,           # Max OBs to return
        "lookback_default": 50,           # Default lookback
        "impulse_bars": 3,                # Bars to confirm impulse
    }


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class OBType(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class OrderBlock:
    """
    Represents an Order Block zone.

    Attributes:
        type: OBType.BULLISH or OBType.BEARISH
        zone_high: Top of the OB zone
        zone_low: Bottom of the OB zone
        midpoint: Middle of the zone
        bar_index: Where the OB candle is
        impulse_size: Size of the impulse move that followed
        impulse_atr_ratio: Impulse size relative to ATR
        mitigated: Has price returned to this zone?
        mitigation_pct: How much of zone has been touched
        strength: Strength score 0-100
        timestamp: Optional timestamp
    """
    type: OBType
    zone_high: float
    zone_low: float
    midpoint: float
    bar_index: int
    impulse_size: float
    impulse_atr_ratio: float
    mitigated: bool
    mitigation_pct: float
    strength: float
    timestamp: Optional[str] = None

    @property
    def zone_size(self) -> float:
        return self.zone_high - self.zone_low

    def contains_price(self, price: float) -> bool:
        """Check if price is within the OB zone."""
        return self.zone_low <= price <= self.zone_high

    def __repr__(self) -> str:
        status = "mitigated" if self.mitigated else "active"
        return f"OrderBlock({self.type.value}, {self.zone_low:.2f}-{self.zone_high:.2f}, {status})"


@dataclass
class OrderBlockResult:
    """
    Complete Order Block analysis result.

    Attributes:
        bullish_obs: List of bullish (demand) OBs
        bearish_obs: List of bearish (supply) OBs
        nearest_bullish: Nearest bullish OB below price
        nearest_bearish: Nearest bearish OB above price
        in_ob: Whether current price is inside an OB
        current_ob: The OB we're currently in (if any)
        total_active: Count of unmitigated OBs
        bias: Overall bias based on OB distribution
    """
    bullish_obs: List[OrderBlock]
    bearish_obs: List[OrderBlock]
    nearest_bullish: Optional[OrderBlock]
    nearest_bearish: Optional[OrderBlock]
    in_ob: bool
    current_ob: Optional[OrderBlock]
    total_active: int
    bias: Literal["bullish", "bearish", "neutral"]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _calculate_atr(df: pl.DataFrame, period: int = 14) -> pl.Series:
    """Calculate ATR - tries existing helper first."""
    if _USE_EXISTING_ATR:
        try:
            high = df["high"].to_numpy()
            low = df["low"].to_numpy()
            close = df["close"].to_numpy()
            atr_arr = atr_wilder(high, low, close, period)
            return pl.Series("atr", atr_arr)
        except Exception:
            pass

    # Local Polars implementation
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

    return df_with_atr["_atr"]


def _is_bullish_candle(open_price: float, close_price: float) -> bool:
    """Check if candle is bullish (close > open)."""
    return close_price > open_price


def _is_bearish_candle(open_price: float, close_price: float) -> bool:
    """Check if candle is bearish (close < open)."""
    return close_price < open_price


def _candle_body_ratio(open_price: float, high: float, low: float, close: float) -> float:
    """Calculate body as ratio of total range."""
    total_range = high - low
    if total_range <= 0:
        return 0.0
    body = abs(close - open_price)
    return body / total_range


def _check_impulse_move(
    df: pl.DataFrame,
    start_idx: int,
    direction: Literal["up", "down"],
    atr_value: float,
    impulse_bars: int = 3,
) -> tuple[bool, float]:
    """
    Check if there's an impulse move after the OB candle.

    Returns:
        (is_valid_impulse, impulse_size)
    """
    if start_idx + impulse_bars >= df.height:
        return False, 0.0

    min_ratio = ORDER_BLOCK_SETTINGS["min_impulse_atr_ratio"]

    # Get price data for impulse check
    closes = df["close"].to_list()
    highs = df["high"].to_list()
    lows = df["low"].to_list()

    start_price = closes[start_idx]

    # Look at next `impulse_bars` bars
    if direction == "up":
        max_high = max(highs[start_idx + 1 : start_idx + 1 + impulse_bars])
        impulse_size = max_high - start_price
    else:
        min_low = min(lows[start_idx + 1 : start_idx + 1 + impulse_bars])
        impulse_size = start_price - min_low

    if atr_value <= 0:
        return False, impulse_size

    impulse_ratio = impulse_size / atr_value
    is_valid = impulse_ratio >= min_ratio

    return is_valid, impulse_size


def _check_mitigation(
    df: pl.DataFrame,
    ob: OrderBlock,
    from_idx: int,
) -> tuple[bool, float]:
    """
    Check if an OB has been mitigated (price returned to zone).

    Returns:
        (is_mitigated, mitigation_percentage)
    """
    tolerance = ORDER_BLOCK_SETTINGS["mitigation_tolerance"]

    if from_idx >= df.height:
        return False, 0.0

    highs = df["high"].to_list()[from_idx:]
    lows = df["low"].to_list()[from_idx:]

    max_penetration = 0.0
    zone_size = ob.zone_high - ob.zone_low

    if zone_size <= 0:
        return True, 1.0

    for h, l in zip(highs, lows):
        if ob.type == OBType.BULLISH:
            # Bullish OB: check if price came down into it
            if l <= ob.zone_high:
                penetration = (ob.zone_high - max(l, ob.zone_low)) / zone_size
                max_penetration = max(max_penetration, penetration)
        else:
            # Bearish OB: check if price came up into it
            if h >= ob.zone_low:
                penetration = (min(h, ob.zone_high) - ob.zone_low) / zone_size
                max_penetration = max(max_penetration, penetration)

    is_mitigated = max_penetration > tolerance
    return is_mitigated, max_penetration


def _calculate_ob_strength(
    impulse_atr_ratio: float,
    body_ratio: float,
    mitigated: bool,
    mitigation_pct: float,
) -> float:
    """
    Calculate OB strength score 0-100.

    Factors:
    - Impulse size (bigger = stronger)
    - Body ratio (fuller candle = stronger)
    - Mitigation (unmitigated = stronger)
    """
    score = 50.0  # Base

    # Impulse bonus (up to +25)
    if impulse_atr_ratio >= 3.0:
        score += 25
    elif impulse_atr_ratio >= 2.0:
        score += 15
    elif impulse_atr_ratio >= 1.5:
        score += 10

    # Body ratio bonus (up to +15)
    if body_ratio >= 0.8:
        score += 15
    elif body_ratio >= 0.6:
        score += 10
    elif body_ratio >= 0.5:
        score += 5

    # Mitigation penalty
    if mitigated:
        score -= 30
    elif mitigation_pct > 0.5:
        score -= 15
    elif mitigation_pct > 0.25:
        score -= 5

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Main Detection Functions
# ---------------------------------------------------------------------------
def detect_order_blocks(
    df: pl.DataFrame,
    lookback: int = 50,
    current_price: Optional[float] = None,
) -> OrderBlockResult:
    """
    Detect Order Blocks in price data.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    lookback : int
        How many bars back to search
    current_price : float, optional
        Current price for proximity analysis

    Returns
    -------
    OrderBlockResult
        Complete OB analysis

    Example
    -------
    >>> result = detect_order_blocks(df, lookback=50)
    >>> print(f"Found {len(result.bullish_obs)} bullish OBs")
    >>> if result.nearest_bullish:
    ...     print(f"Support at {result.nearest_bullish.zone_high}")
    """
    if df is None or df.is_empty() or df.height < 5:
        return OrderBlockResult(
            bullish_obs=[],
            bearish_obs=[],
            nearest_bullish=None,
            nearest_bearish=None,
            in_ob=False,
            current_ob=None,
            total_active=0,
            bias="neutral",
        )

    # Get current price if not provided
    if current_price is None:
        current_price = float(df["close"].tail(1).item())

    # Calculate ATR
    atr_series = _calculate_atr(df)
    atr_list = atr_series.to_list()

    # Get OHLC data
    opens = df["open"].to_list()
    highs = df["high"].to_list()
    lows = df["low"].to_list()
    closes = df["close"].to_list()

    timestamps = None
    if "timestamp" in df.columns:
        timestamps = df["timestamp"].cast(pl.Utf8).to_list()

    n = df.height
    start_idx = max(0, n - lookback)

    bullish_obs: List[OrderBlock] = []
    bearish_obs: List[OrderBlock] = []

    min_body_ratio = ORDER_BLOCK_SETTINGS["min_ob_body_ratio"]
    impulse_bars = ORDER_BLOCK_SETTINGS["impulse_bars"]
    max_obs = ORDER_BLOCK_SETTINGS["max_obs_to_track"]

    # Scan for OBs
    for i in range(start_idx, n - impulse_bars):
        atr_val = atr_list[i] if atr_list[i] is not None else 1.0

        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        body_ratio = _candle_body_ratio(o, h, l, c)

        # Skip weak candles
        if body_ratio < min_body_ratio:
            continue

        # Check for BULLISH OB (bearish candle before bullish impulse)
        if _is_bearish_candle(o, c):
            is_impulse, impulse_size = _check_impulse_move(
                df, i, "up", atr_val, impulse_bars
            )

            if is_impulse:
                # OB zone is the bearish candle's body
                zone_high = o  # Open of bearish = top
                zone_low = c   # Close of bearish = bottom

                ob = OrderBlock(
                    type=OBType.BULLISH,
                    zone_high=zone_high,
                    zone_low=zone_low,
                    midpoint=(zone_high + zone_low) / 2,
                    bar_index=i,
                    impulse_size=impulse_size,
                    impulse_atr_ratio=impulse_size / atr_val if atr_val > 0 else 0,
                    mitigated=False,
                    mitigation_pct=0.0,
                    strength=0.0,
                    timestamp=timestamps[i] if timestamps else None,
                )

                # Check mitigation
                mitigated, mit_pct = _check_mitigation(df, ob, i + 1)
                ob.mitigated = mitigated
                ob.mitigation_pct = mit_pct

                # Calculate strength
                ob.strength = _calculate_ob_strength(
                    ob.impulse_atr_ratio, body_ratio, mitigated, mit_pct
                )

                bullish_obs.append(ob)

        # Check for BEARISH OB (bullish candle before bearish impulse)
        if _is_bullish_candle(o, c):
            is_impulse, impulse_size = _check_impulse_move(
                df, i, "down", atr_val, impulse_bars
            )

            if is_impulse:
                # OB zone is the bullish candle's body
                zone_high = c  # Close of bullish = top
                zone_low = o   # Open of bullish = bottom

                ob = OrderBlock(
                    type=OBType.BEARISH,
                    zone_high=zone_high,
                    zone_low=zone_low,
                    midpoint=(zone_high + zone_low) / 2,
                    bar_index=i,
                    impulse_size=impulse_size,
                    impulse_atr_ratio=impulse_size / atr_val if atr_val > 0 else 0,
                    mitigated=False,
                    mitigation_pct=0.0,
                    strength=0.0,
                    timestamp=timestamps[i] if timestamps else None,
                )

                # Check mitigation
                mitigated, mit_pct = _check_mitigation(df, ob, i + 1)
                ob.mitigated = mitigated
                ob.mitigation_pct = mit_pct

                # Calculate strength
                ob.strength = _calculate_ob_strength(
                    ob.impulse_atr_ratio, body_ratio, mitigated, mit_pct
                )

                bearish_obs.append(ob)

    # Keep only strongest/most recent
    bullish_obs = sorted(bullish_obs, key=lambda x: (-x.strength, -x.bar_index))[:max_obs]
    bearish_obs = sorted(bearish_obs, key=lambda x: (-x.strength, -x.bar_index))[:max_obs]

    # Find nearest OBs
    nearest_bullish = None
    nearest_bearish = None

    active_bullish = [ob for ob in bullish_obs if not ob.mitigated]
    active_bearish = [ob for ob in bearish_obs if not ob.mitigated]

    # Nearest bullish OB below current price
    below = [ob for ob in active_bullish if ob.zone_high < current_price]
    if below:
        nearest_bullish = max(below, key=lambda ob: ob.zone_high)

    # Nearest bearish OB above current price
    above = [ob for ob in active_bearish if ob.zone_low > current_price]
    if above:
        nearest_bearish = min(above, key=lambda ob: ob.zone_low)

    # Check if currently in an OB
    in_ob = False
    current_ob = None
    for ob in bullish_obs + bearish_obs:
        if ob.contains_price(current_price):
            in_ob = True
            current_ob = ob
            break

    # Determine bias
    total_active = len(active_bullish) + len(active_bearish)
    if len(active_bullish) > len(active_bearish) + 2:
        bias = "bullish"
    elif len(active_bearish) > len(active_bullish) + 2:
        bias = "bearish"
    else:
        bias = "neutral"

    return OrderBlockResult(
        bullish_obs=bullish_obs,
        bearish_obs=bearish_obs,
        nearest_bullish=nearest_bullish,
        nearest_bearish=nearest_bearish,
        in_ob=in_ob,
        current_ob=current_ob,
        total_active=total_active,
        bias=bias,
    )


def summarize_order_blocks(
    df: pl.DataFrame,
    current_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Get summary dict for signal cards.

    Returns dict with keys:
    - ob_support: Nearest bullish OB level (support)
    - ob_resistance: Nearest bearish OB level (resistance)
    - in_ob: bool
    - ob_type: "bullish"/"bearish"/None if in OB
    - total_active: Count of active OBs
    - ob_bias: Overall bias
    - bullish_count: Active bullish OBs
    - bearish_count: Active bearish OBs
    """
    result = detect_order_blocks(df, current_price=current_price)

    ob_support = None
    ob_resistance = None

    if result.nearest_bullish:
        ob_support = result.nearest_bullish.zone_high

    if result.nearest_bearish:
        ob_resistance = result.nearest_bearish.zone_low

    return {
        "ob_support": ob_support,
        "ob_resistance": ob_resistance,
        "in_ob": result.in_ob,
        "ob_type": result.current_ob.type.value if result.current_ob else None,
        "total_active": result.total_active,
        "ob_bias": result.bias,
        "bullish_count": len([ob for ob in result.bullish_obs if not ob.mitigated]),
        "bearish_count": len([ob for ob in result.bearish_obs if not ob.mitigated]),
    }


def attach_order_block_signals(df: pl.DataFrame) -> pl.DataFrame:
    """
    Attach OB-related columns to DataFrame.

    Adds columns:
    - ob_support: Nearest support level
    - ob_resistance: Nearest resistance level
    - in_ob: Boolean
    - ob_bias: String
    """
    summary = summarize_order_blocks(df)

    return df.with_columns([
        pl.lit(summary["ob_support"]).alias("ob_support"),
        pl.lit(summary["ob_resistance"]).alias("ob_resistance"),
        pl.lit(summary["in_ob"]).alias("in_ob"),
        pl.lit(summary["ob_bias"]).alias("ob_bias"),
    ])


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "order_blocks": detect_order_blocks,
    "order_blocks_summary": summarize_order_blocks,
    "order_blocks_attach": attach_order_block_signals,
}

NAME = "order_blocks"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("ORDER BLOCKS TEST")
    print("=" * 60)

    # Create sample data with clear OB setup
    np.random.seed(42)
    n = 60

    # Create a pattern: down move, OB candle, then impulse up
    prices = [100.0]
    for i in range(1, n):
        if i < 20:
            # Downtrend
            change = np.random.uniform(-0.5, 0.2)
        elif i == 20:
            # Strong bearish candle (potential bullish OB)
            change = -1.5
        elif 21 <= i <= 25:
            # Impulse up
            change = np.random.uniform(0.5, 1.0)
        elif i < 40:
            # Uptrend
            change = np.random.uniform(-0.2, 0.5)
        elif i == 40:
            # Strong bullish candle (potential bearish OB)
            change = 1.5
        elif 41 <= i <= 45:
            # Impulse down
            change = np.random.uniform(-1.0, -0.5)
        else:
            change = np.random.uniform(-0.3, 0.3)

        prices.append(prices[-1] + change)

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d} 09:{(i % 60):02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.3, 0.8) for p in prices],
        "low": [p - np.random.uniform(0.3, 0.8) for p in prices],
        "close": [prices[i] + np.random.uniform(-0.2, 0.2) for i in range(n)],
        "volume": [10000 + np.random.randint(-2000, 2000) for _ in range(n)],
    })

    # Run detection
    result = detect_order_blocks(df, lookback=50)

    print(f"\n📊 ORDER BLOCKS FOUND:")
    print(f"   Bullish OBs (Demand): {len(result.bullish_obs)}")
    for ob in result.bullish_obs[:3]:
        status = "⚠️ Mitigated" if ob.mitigated else "✅ Active"
        print(f"      {ob.zone_low:.2f} - {ob.zone_high:.2f} | Strength: {ob.strength:.0f} | {status}")

    print(f"\n   Bearish OBs (Supply): {len(result.bearish_obs)}")
    for ob in result.bearish_obs[:3]:
        status = "⚠️ Mitigated" if ob.mitigated else "✅ Active"
        print(f"      {ob.zone_low:.2f} - {ob.zone_high:.2f} | Strength: {ob.strength:.0f} | {status}")

    print(f"\n📊 CURRENT ANALYSIS:")
    print(f"   In OB: {result.in_ob}")
    print(f"   Bias: {result.bias}")
    print(f"   Total Active: {result.total_active}")

    if result.nearest_bullish:
        print(f"   Support (Bullish OB): {result.nearest_bullish.zone_high:.2f}")
    if result.nearest_bearish:
        print(f"   Resistance (Bearish OB): {result.nearest_bearish.zone_low:.2f}")

    # Test summary
    print(f"\n📊 SUMMARY DICT:")
    summary = summarize_order_blocks(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ Order Blocks test complete!")
