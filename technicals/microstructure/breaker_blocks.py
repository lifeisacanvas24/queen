# queen/technicals/microstructure/breaker_blocks.py
"""
Breaker Block Detection Module
==============================
Identifies Breaker Blocks - failed Order Blocks that become reversal zones.

A Breaker Block forms when:
1. A valid Order Block is created
2. Price later breaks through the OB (mitigates it)
3. The former OB zone becomes a reversal point in the opposite direction

Breaker Block Types:
- Bullish Breaker: Former bearish OB broken upward (now acts as support)
- Bearish Breaker: Former bullish OB broken downward (now acts as resistance)

Usage:
    from queen.technicals.microstructure.breaker_blocks import (
        detect_breaker_blocks,
        summarize_breaker_blocks,
        BreakerBlock,
    )

    result = detect_breaker_blocks(df, lookback=100)
    for bb in result.bullish_breakers:
        print(f"Bullish Breaker at {bb.zone_low:.2f} - {bb.zone_high:.2f}")

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
    from queen.technicals.microstructure.order_blocks import (
        detect_order_blocks,
        OrderBlock,
        OBType,
    )
    _USE_ORDER_BLOCKS = True
except ImportError:
    _USE_ORDER_BLOCKS = False

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
try:
    from queen.settings.breakout_settings import BREAKER_BLOCK_SETTINGS
except ImportError:
    BREAKER_BLOCK_SETTINGS = {
        "mitigation_threshold": 0.5,      # OB 50% mitigated = breaker candidate
        "confirmation_bars": 2,           # Bars needed to confirm break
        "max_age_bars": 100,              # Look further back for breakers
        "max_breakers_to_track": 5,
        "lookback_default": 100,
        "strong_breaker_impulse": 2.0,    # Original impulse was > 2x ATR
        "retest_tolerance_pct": 0.002,    # 0.2% tolerance for retest
    }


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class BreakerType(str, Enum):
    BULLISH = "bullish"   # Former bearish OB, now support
    BEARISH = "bearish"   # Former bullish OB, now resistance


@dataclass
class BreakerBlock:
    """
    Represents a Breaker Block zone.

    Attributes:
        type: BreakerType.BULLISH or BEARISH
        zone_high: Top of the breaker zone
        zone_low: Bottom of the breaker zone
        midpoint: Middle of the zone
        original_ob_type: What type of OB it was before breaking
        break_bar_index: When the OB was broken
        creation_bar_index: When the original OB was created
        retested: Has price returned to test the breaker?
        retest_held: Did the retest hold (confirm breaker validity)?
        strength: Strength score 0-100
        timestamp: Optional timestamp of the break
    """
    type: BreakerType
    zone_high: float
    zone_low: float
    midpoint: float
    original_ob_type: str
    break_bar_index: int
    creation_bar_index: int
    retested: bool
    retest_held: bool
    strength: float
    timestamp: Optional[str] = None

    @property
    def zone_size(self) -> float:
        return self.zone_high - self.zone_low

    def contains_price(self, price: float) -> bool:
        """Check if price is within the breaker zone."""
        return self.zone_low <= price <= self.zone_high

    def __repr__(self) -> str:
        status = "retested & held" if self.retest_held else ("retested" if self.retested else "untested")
        return f"BreakerBlock({self.type.value}, {self.zone_low:.2f}-{self.zone_high:.2f}, {status})"


@dataclass
class BreakerBlockResult:
    """
    Complete Breaker Block analysis result.

    Attributes:
        bullish_breakers: List of bullish breakers (support zones)
        bearish_breakers: List of bearish breakers (resistance zones)
        nearest_bullish: Nearest bullish breaker below price
        nearest_bearish: Nearest bearish breaker above price
        in_breaker: Whether current price is inside a breaker
        current_breaker: The breaker we're currently in (if any)
        total_active: Count of active breakers
        bias: Overall bias based on breaker distribution
    """
    bullish_breakers: List[BreakerBlock]
    bearish_breakers: List[BreakerBlock]
    nearest_bullish: Optional[BreakerBlock]
    nearest_bearish: Optional[BreakerBlock]
    in_breaker: bool
    current_breaker: Optional[BreakerBlock]
    total_active: int
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


def _check_ob_broken(
    df: pl.DataFrame,
    ob_zone_high: float,
    ob_zone_low: float,
    ob_type: str,
    from_idx: int,
) -> tuple[bool, int, float]:
    """
    Check if an Order Block has been broken through.

    Returns:
        (is_broken, break_bar_index, break_percentage)
    """
    if from_idx >= df.height:
        return False, -1, 0.0

    mitigation_threshold = BREAKER_BLOCK_SETTINGS["mitigation_threshold"]
    confirmation_bars = BREAKER_BLOCK_SETTINGS["confirmation_bars"]

    closes = df["close"].to_list()[from_idx:]
    highs = df["high"].to_list()[from_idx:]
    lows = df["low"].to_list()[from_idx:]

    zone_size = ob_zone_high - ob_zone_low
    if zone_size <= 0:
        return False, -1, 0.0

    for i, (h, l, c) in enumerate(zip(highs, lows, closes)):
        actual_idx = from_idx + i

        if ob_type == "bullish":
            # Bullish OB broken when price closes below zone_low
            if c < ob_zone_low:
                # Check for confirmation
                if i + confirmation_bars < len(closes):
                    confirm_closes = closes[i:i + confirmation_bars]
                    if all(cc < ob_zone_low for cc in confirm_closes):
                        break_pct = (ob_zone_low - c) / zone_size
                        return True, actual_idx, break_pct
        else:
            # Bearish OB broken when price closes above zone_high
            if c > ob_zone_high:
                if i + confirmation_bars < len(closes):
                    confirm_closes = closes[i:i + confirmation_bars]
                    if all(cc > ob_zone_high for cc in confirm_closes):
                        break_pct = (c - ob_zone_high) / zone_size
                        return True, actual_idx, break_pct

    return False, -1, 0.0


def _check_retest(
    df: pl.DataFrame,
    breaker: BreakerBlock,
    from_idx: int,
) -> tuple[bool, bool]:
    """
    Check if a breaker has been retested and if it held.

    Returns:
        (retested, retest_held)
    """
    if from_idx >= df.height:
        return False, False

    tolerance = BREAKER_BLOCK_SETTINGS["retest_tolerance_pct"]

    highs = df["high"].to_list()[from_idx:]
    lows = df["low"].to_list()[from_idx:]
    closes = df["close"].to_list()[from_idx:]

    retested = False
    retest_held = False

    for h, l, c in zip(highs, lows, closes):
        if breaker.type == BreakerType.BULLISH:
            # Bullish breaker: Price should come down to zone and bounce
            if l <= breaker.zone_high * (1 + tolerance):
                retested = True
                # Held if closed back above zone
                if c > breaker.zone_high:
                    retest_held = True
                    break
        else:
            # Bearish breaker: Price should come up to zone and reject
            if h >= breaker.zone_low * (1 - tolerance):
                retested = True
                # Held if closed back below zone
                if c < breaker.zone_low:
                    retest_held = True
                    break

    return retested, retest_held


def _calculate_breaker_strength(
    original_impulse_atr: float,
    retested: bool,
    retest_held: bool,
) -> float:
    """
    Calculate breaker block strength score 0-100.

    Factors:
    - Original OB impulse size (bigger = stronger breaker)
    - Has been retested (tested = more reliable)
    - Retest held (confirmed = very strong)
    """
    score = 40.0  # Base

    # Original impulse bonus (up to +30)
    strong_impulse = BREAKER_BLOCK_SETTINGS["strong_breaker_impulse"]
    if original_impulse_atr >= strong_impulse:
        score += 30
    elif original_impulse_atr >= strong_impulse * 0.75:
        score += 20
    elif original_impulse_atr >= strong_impulse * 0.5:
        score += 10

    # Retest bonus
    if retest_held:
        score += 25  # Confirmed breaker
    elif retested:
        score += 10  # Tested but not confirmed

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Main Detection Functions
# ---------------------------------------------------------------------------
def detect_breaker_blocks(
    df: pl.DataFrame,
    lookback: int = 100,
    current_price: Optional[float] = None,
) -> BreakerBlockResult:
    """
    Detect Breaker Blocks in price data.

    A Breaker Block is a former Order Block that has been broken through
    and now acts as a reversal zone in the opposite direction.

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
    BreakerBlockResult
        Complete breaker block analysis

    Example
    -------
    >>> result = detect_breaker_blocks(df, lookback=100)
    >>> if result.nearest_bullish:
    ...     print(f"Support at {result.nearest_bullish.zone_high}")
    """
    if df is None or df.is_empty() or df.height < 10:
        return BreakerBlockResult(
            bullish_breakers=[],
            bearish_breakers=[],
            nearest_bullish=None,
            nearest_bearish=None,
            in_breaker=False,
            current_breaker=None,
            total_active=0,
            bias="neutral",
        )

    # Get current price if not provided
    if current_price is None:
        current_price = float(df["close"].tail(1).item())

    # Get timestamps
    timestamps = None
    if "timestamp" in df.columns:
        timestamps = df["timestamp"].cast(pl.Utf8).to_list()

    n = df.height
    max_breakers = BREAKER_BLOCK_SETTINGS["max_breakers_to_track"]

    bullish_breakers: List[BreakerBlock] = []
    bearish_breakers: List[BreakerBlock] = []

    # Get Order Blocks first
    if _USE_ORDER_BLOCKS:
        try:
            ob_result = detect_order_blocks(df, lookback=lookback)
            all_obs = ob_result.bullish_obs + ob_result.bearish_obs
        except Exception:
            all_obs = []
    else:
        all_obs = []

    # Check each OB to see if it's been broken (becoming a breaker)
    for ob in all_obs:
        is_broken, break_idx, break_pct = _check_ob_broken(
            df,
            ob.zone_high,
            ob.zone_low,
            ob.type.value,
            ob.bar_index + 1,
        )

        if is_broken:
            # Create breaker block
            if ob.type == OBType.BULLISH:
                # Bullish OB broken down = Bearish Breaker (resistance)
                breaker_type = BreakerType.BEARISH
            else:
                # Bearish OB broken up = Bullish Breaker (support)
                breaker_type = BreakerType.BULLISH

            breaker = BreakerBlock(
                type=breaker_type,
                zone_high=ob.zone_high,
                zone_low=ob.zone_low,
                midpoint=ob.midpoint,
                original_ob_type=ob.type.value,
                break_bar_index=break_idx,
                creation_bar_index=ob.bar_index,
                retested=False,
                retest_held=False,
                strength=0.0,
                timestamp=timestamps[break_idx] if timestamps and break_idx < len(timestamps) else None,
            )

            # Check for retest
            retested, held = _check_retest(df, breaker, break_idx + 1)
            breaker.retested = retested
            breaker.retest_held = held

            # Calculate strength
            breaker.strength = _calculate_breaker_strength(
                ob.impulse_atr_ratio,
                retested,
                held,
            )

            if breaker_type == BreakerType.BULLISH:
                bullish_breakers.append(breaker)
            else:
                bearish_breakers.append(breaker)

    # Sort by strength and keep top N
    bullish_breakers = sorted(bullish_breakers, key=lambda x: -x.strength)[:max_breakers]
    bearish_breakers = sorted(bearish_breakers, key=lambda x: -x.strength)[:max_breakers]

    # Find nearest breakers
    nearest_bullish = None
    nearest_bearish = None

    # Nearest bullish breaker below current price
    below = [bb for bb in bullish_breakers if bb.zone_high < current_price]
    if below:
        nearest_bullish = max(below, key=lambda bb: bb.zone_high)

    # Nearest bearish breaker above current price
    above = [bb for bb in bearish_breakers if bb.zone_low > current_price]
    if above:
        nearest_bearish = min(above, key=lambda bb: bb.zone_low)

    # Check if currently in a breaker
    in_breaker = False
    current_breaker = None
    for bb in bullish_breakers + bearish_breakers:
        if bb.contains_price(current_price):
            in_breaker = True
            current_breaker = bb
            break

    # Determine bias
    total_active = len(bullish_breakers) + len(bearish_breakers)
    confirmed_bullish = sum(1 for bb in bullish_breakers if bb.retest_held)
    confirmed_bearish = sum(1 for bb in bearish_breakers if bb.retest_held)

    if confirmed_bullish > confirmed_bearish:
        bias = "bullish"
    elif confirmed_bearish > confirmed_bullish:
        bias = "bearish"
    else:
        bias = "neutral"

    return BreakerBlockResult(
        bullish_breakers=bullish_breakers,
        bearish_breakers=bearish_breakers,
        nearest_bullish=nearest_bullish,
        nearest_bearish=nearest_bearish,
        in_breaker=in_breaker,
        current_breaker=current_breaker,
        total_active=total_active,
        bias=bias,
    )


def summarize_breaker_blocks(
    df: pl.DataFrame,
    current_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Get summary dict for signal cards.

    Returns dict with keys:
    - breaker_support: Nearest bullish breaker level
    - breaker_resistance: Nearest bearish breaker level
    - in_breaker: bool
    - breaker_type: "bullish"/"bearish"/None
    - breaker_bias: Overall bias
    - total_breakers: Count
    - confirmed_breakers: Count of retested & held
    """
    result = detect_breaker_blocks(df, current_price=current_price)

    breaker_support = None
    breaker_resistance = None

    if result.nearest_bullish:
        breaker_support = result.nearest_bullish.zone_high

    if result.nearest_bearish:
        breaker_resistance = result.nearest_bearish.zone_low

    confirmed = sum(1 for bb in result.bullish_breakers + result.bearish_breakers if bb.retest_held)

    return {
        "breaker_support": breaker_support,
        "breaker_resistance": breaker_resistance,
        "in_breaker": result.in_breaker,
        "breaker_type": result.current_breaker.type.value if result.current_breaker else None,
        "breaker_bias": result.bias,
        "total_breakers": result.total_active,
        "confirmed_breakers": confirmed,
        "bullish_count": len(result.bullish_breakers),
        "bearish_count": len(result.bearish_breakers),
    }


def attach_breaker_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Attach breaker block columns to DataFrame."""
    summary = summarize_breaker_blocks(df)

    return df.with_columns([
        pl.lit(summary["breaker_support"]).alias("breaker_support"),
        pl.lit(summary["breaker_resistance"]).alias("breaker_resistance"),
        pl.lit(summary["in_breaker"]).alias("in_breaker"),
        pl.lit(summary["breaker_bias"]).alias("breaker_bias"),
    ])


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "breaker_blocks": detect_breaker_blocks,
    "breaker_blocks_summary": summarize_breaker_blocks,
    "breaker_blocks_attach": attach_breaker_signals,
}

NAME = "breaker_blocks"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("BREAKER BLOCKS TEST")
    print("=" * 60)
    print(f"Using Order Blocks module: {_USE_ORDER_BLOCKS}")

    # Create test data
    np.random.seed(42)
    n = 80

    # Create a pattern:
    # 1. Downtrend with bearish OB
    # 2. Break above bearish OB (creates bullish breaker)
    # 3. Retest the breaker zone
    prices = [100.0]
    for i in range(1, n):
        if i < 20:
            # Downtrend
            change = np.random.uniform(-0.8, 0.2)
        elif i == 20:
            # Bearish OB candle (strong bullish before down move)
            change = 1.5
        elif 21 <= i <= 25:
            # Impulse down
            change = np.random.uniform(-1.0, -0.5)
        elif 26 <= i <= 35:
            # Consolidation
            change = np.random.uniform(-0.3, 0.3)
        elif 36 <= i <= 45:
            # Break above the bearish OB (create bullish breaker)
            change = np.random.uniform(0.5, 1.0)
        elif 46 <= i <= 55:
            # Pullback to retest the breaker
            change = np.random.uniform(-0.5, 0.0)
        else:
            # Bounce off breaker
            change = np.random.uniform(0.2, 0.8)

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
    result = detect_breaker_blocks(df, lookback=80)

    print(f"\n📊 BREAKER BLOCKS FOUND:")
    print(f"   Bullish Breakers (Support): {len(result.bullish_breakers)}")
    for bb in result.bullish_breakers[:3]:
        status = "✅ Confirmed" if bb.retest_held else ("⏳ Retested" if bb.retested else "🔲 Untested")
        print(f"      {bb.zone_low:.2f} - {bb.zone_high:.2f} | Strength: {bb.strength:.0f} | {status}")

    print(f"\n   Bearish Breakers (Resistance): {len(result.bearish_breakers)}")
    for bb in result.bearish_breakers[:3]:
        status = "✅ Confirmed" if bb.retest_held else ("⏳ Retested" if bb.retested else "🔲 Untested")
        print(f"      {bb.zone_low:.2f} - {bb.zone_high:.2f} | Strength: {bb.strength:.0f} | {status}")

    print(f"\n📊 CURRENT ANALYSIS:")
    print(f"   In Breaker: {result.in_breaker}")
    print(f"   Bias: {result.bias}")
    print(f"   Total Active: {result.total_active}")

    if result.nearest_bullish:
        print(f"   Support (Bullish Breaker): {result.nearest_bullish.zone_high:.2f}")
    if result.nearest_bearish:
        print(f"   Resistance (Bearish Breaker): {result.nearest_bearish.zone_low:.2f}")

    # Test summary
    print(f"\n📊 SUMMARY DICT:")
    summary = summarize_breaker_blocks(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ Breaker Blocks test complete!")
