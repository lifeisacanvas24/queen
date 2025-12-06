# queen/technicals/microstructure/mitigation_blocks.py
"""
Mitigation Block Tracking Module
================================
Tracks Order Blocks and their mitigation status over time.

A Mitigation Block is an Order Block that has been partially or fully
"mitigated" (price has returned to the zone). Unmitigated OBs are
considered stronger and more likely to cause reactions.

Key Concepts:
- Unmitigated OB: Price hasn't returned to the zone yet (strongest)
- Partially Mitigated: Price touched but didn't fully fill the zone
- Fully Mitigated: Price completely filled/passed through the zone
- Respected: Price touched and bounced (confirms the zone)

Usage:
    from queen.technicals.microstructure.mitigation_blocks import (
        track_mitigation_status,
        get_unmitigated_obs,
        get_respected_zones,
        MitigationStatus,
    )

    result = track_mitigation_status(df, lookback=100)
    for ob in result.unmitigated:
        print(f"Strong zone at {ob.zone_low:.2f} - {ob.zone_high:.2f}")

Settings:
    Uses ORDER_BLOCK_SETTINGS from settings/breakout_settings.py
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
    from queen.technicals.microstructure.order_blocks import (
        detect_order_blocks,
        OrderBlock,
        OBType,
    )
    _USE_ORDER_BLOCKS = True
except ImportError:
    _USE_ORDER_BLOCKS = False

try:
    from queen.helpers.ta_math import atr_wilder
    _USE_EXISTING_ATR = True
except ImportError:
    _USE_EXISTING_ATR = False

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
try:
    from queen.settings.breakout_settings import ORDER_BLOCK_SETTINGS
except ImportError:
    ORDER_BLOCK_SETTINGS = {
        "mitigation_tolerance": 0.1,
        "max_age_bars": 50,
        "max_obs_to_track": 10,
    }


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class MitigationStatus(str, Enum):
    UNMITIGATED = "unmitigated"       # Price never returned
    TOUCHED = "touched"                # Price touched zone edge
    PARTIAL = "partial"                # Price entered zone partially
    FULL = "full"                      # Price passed through entirely
    RESPECTED = "respected"            # Touched and bounced (confirmed)


@dataclass
class MitigationBlock:
    """
    An Order Block with mitigation tracking.

    Attributes:
        ob_type: bullish or bearish
        zone_high: Top of zone
        zone_low: Bottom of zone
        midpoint: Middle of zone
        creation_bar: When OB was created
        status: Current mitigation status
        mitigation_pct: How much of zone has been mitigated (0-1)
        touch_count: How many times price has touched the zone
        last_touch_bar: Last bar that touched the zone
        bounce_count: Times price bounced off the zone
        strength: Adjusted strength based on mitigation
    """
    ob_type: Literal["bullish", "bearish"]
    zone_high: float
    zone_low: float
    midpoint: float
    creation_bar: int
    status: MitigationStatus
    mitigation_pct: float
    touch_count: int
    last_touch_bar: Optional[int]
    bounce_count: int
    strength: float
    timestamp: Optional[str] = None

    @property
    def zone_size(self) -> float:
        return self.zone_high - self.zone_low

    @property
    def is_active(self) -> bool:
        """Zone is still active (not fully mitigated)."""
        return self.status != MitigationStatus.FULL

    @property
    def is_strong(self) -> bool:
        """Zone is considered strong."""
        return self.status in [MitigationStatus.UNMITIGATED, MitigationStatus.RESPECTED]


@dataclass
class MitigationResult:
    """
    Complete mitigation tracking result.

    Attributes:
        all_blocks: All tracked blocks with status
        unmitigated: Blocks that haven't been touched
        respected: Blocks that bounced (confirmed zones)
        partial: Partially mitigated blocks
        full: Fully mitigated blocks
        bullish_zones: Active bullish zones (support)
        bearish_zones: Active bearish zones (resistance)
        nearest_support: Nearest unmitigated bullish zone
        nearest_resistance: Nearest unmitigated bearish zone
    """
    all_blocks: List[MitigationBlock]
    unmitigated: List[MitigationBlock]
    respected: List[MitigationBlock]
    partial: List[MitigationBlock]
    full: List[MitigationBlock]
    bullish_zones: List[MitigationBlock]
    bearish_zones: List[MitigationBlock]
    nearest_support: Optional[MitigationBlock]
    nearest_resistance: Optional[MitigationBlock]
    total_active: int


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _calculate_mitigation(
    df: pl.DataFrame,
    zone_high: float,
    zone_low: float,
    ob_type: str,
    from_bar: int,
) -> tuple[MitigationStatus, float, int, int, int]:
    """
    Calculate mitigation status for an Order Block.

    Returns:
        (status, mitigation_pct, touch_count, last_touch_bar, bounce_count)
    """
    if from_bar >= df.height:
        return MitigationStatus.UNMITIGATED, 0.0, 0, None, 0

    highs = df["high"].to_list()[from_bar:]
    lows = df["low"].to_list()[from_bar:]
    closes = df["close"].to_list()[from_bar:]

    zone_size = zone_high - zone_low
    if zone_size <= 0:
        return MitigationStatus.UNMITIGATED, 0.0, 0, None, 0

    touch_count = 0
    bounce_count = 0
    last_touch_bar = None
    max_penetration = 0.0

    for i, (h, l, c) in enumerate(zip(highs, lows, closes)):
        actual_bar = from_bar + i

        if ob_type == "bullish":
            # Bullish OB = demand zone, price should come down to it
            if l <= zone_high:  # Price reached the zone
                touch_count += 1
                last_touch_bar = actual_bar

                # Calculate penetration
                if l < zone_low:
                    penetration = 1.0  # Fully passed through
                else:
                    penetration = (zone_high - l) / zone_size

                max_penetration = max(max_penetration, penetration)

                # Check for bounce (close back above zone)
                if c > zone_high:
                    bounce_count += 1
        else:
            # Bearish OB = supply zone, price should come up to it
            if h >= zone_low:  # Price reached the zone
                touch_count += 1
                last_touch_bar = actual_bar

                if h > zone_high:
                    penetration = 1.0
                else:
                    penetration = (h - zone_low) / zone_size

                max_penetration = max(max_penetration, penetration)

                # Check for bounce (close back below zone)
                if c < zone_low:
                    bounce_count += 1

    # Determine status
    if touch_count == 0:
        status = MitigationStatus.UNMITIGATED
    elif max_penetration >= 1.0:
        status = MitigationStatus.FULL
    elif bounce_count > 0:
        status = MitigationStatus.RESPECTED
    elif max_penetration > 0.5:
        status = MitigationStatus.PARTIAL
    else:
        status = MitigationStatus.TOUCHED

    return status, max_penetration, touch_count, last_touch_bar, bounce_count


def _calculate_adjusted_strength(
    base_strength: float,
    status: MitigationStatus,
    touch_count: int,
    bounce_count: int,
) -> float:
    """Calculate strength adjusted for mitigation."""
    strength = base_strength

    # Status adjustments
    if status == MitigationStatus.UNMITIGATED:
        strength += 15  # Untested = strongest
    elif status == MitigationStatus.RESPECTED:
        strength += 20  # Confirmed by bounce = very strong
    elif status == MitigationStatus.TOUCHED:
        strength += 5   # Touched but held
    elif status == MitigationStatus.PARTIAL:
        strength -= 10  # Partially filled
    elif status == MitigationStatus.FULL:
        strength -= 30  # Fully mitigated = weak

    # Multiple bounces = stronger
    if bounce_count >= 2:
        strength += 10
    elif bounce_count == 1:
        strength += 5

    # Too many touches without bounce = weakening
    if touch_count > 3 and bounce_count == 0:
        strength -= 15

    return max(0.0, min(100.0, strength))


# ---------------------------------------------------------------------------
# Main Detection Functions
# ---------------------------------------------------------------------------
def track_mitigation_status(
    df: pl.DataFrame,
    lookback: int = 100,
    current_price: Optional[float] = None,
) -> MitigationResult:
    """
    Track mitigation status of all Order Blocks.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    lookback : int
        How many bars back to search for OBs
    current_price : float, optional
        Current price for proximity analysis

    Returns
    -------
    MitigationResult
        Complete mitigation tracking with categorized blocks
    """
    if df is None or df.is_empty() or df.height < 10:
        return MitigationResult(
            all_blocks=[], unmitigated=[], respected=[], partial=[], full=[],
            bullish_zones=[], bearish_zones=[],
            nearest_support=None, nearest_resistance=None, total_active=0,
        )

    if current_price is None:
        current_price = float(df["close"].tail(1).item())

    timestamps = None
    if "timestamp" in df.columns:
        timestamps = df["timestamp"].cast(pl.Utf8).to_list()

    # Get Order Blocks
    if not _USE_ORDER_BLOCKS:
        return MitigationResult(
            all_blocks=[], unmitigated=[], respected=[], partial=[], full=[],
            bullish_zones=[], bearish_zones=[],
            nearest_support=None, nearest_resistance=None, total_active=0,
        )

    try:
        ob_result = detect_order_blocks(df, lookback=lookback)
        all_obs = ob_result.bullish_obs + ob_result.bearish_obs
    except Exception:
        all_obs = []

    mitigation_blocks: List[MitigationBlock] = []

    for ob in all_obs:
        status, mit_pct, touches, last_touch, bounces = _calculate_mitigation(
            df, ob.zone_high, ob.zone_low, ob.type.value, ob.bar_index + 1
        )

        strength = _calculate_adjusted_strength(
            ob.strength, status, touches, bounces
        )

        mb = MitigationBlock(
            ob_type=ob.type.value,
            zone_high=ob.zone_high,
            zone_low=ob.zone_low,
            midpoint=ob.midpoint,
            creation_bar=ob.bar_index,
            status=status,
            mitigation_pct=mit_pct,
            touch_count=touches,
            last_touch_bar=last_touch,
            bounce_count=bounces,
            strength=strength,
            timestamp=timestamps[ob.bar_index] if timestamps and ob.bar_index < len(timestamps) else None,
        )
        mitigation_blocks.append(mb)

    # Categorize
    unmitigated = [b for b in mitigation_blocks if b.status == MitigationStatus.UNMITIGATED]
    respected = [b for b in mitigation_blocks if b.status == MitigationStatus.RESPECTED]
    partial = [b for b in mitigation_blocks if b.status == MitigationStatus.PARTIAL]
    full = [b for b in mitigation_blocks if b.status == MitigationStatus.FULL]

    # Active zones by type
    bullish_zones = [b for b in mitigation_blocks if b.ob_type == "bullish" and b.is_active]
    bearish_zones = [b for b in mitigation_blocks if b.ob_type == "bearish" and b.is_active]

    # Sort by strength
    bullish_zones = sorted(bullish_zones, key=lambda x: -x.strength)
    bearish_zones = sorted(bearish_zones, key=lambda x: -x.strength)

    # Find nearest support/resistance
    nearest_support = None
    nearest_resistance = None

    support_candidates = [b for b in bullish_zones if b.zone_high < current_price]
    if support_candidates:
        nearest_support = max(support_candidates, key=lambda b: b.zone_high)

    resistance_candidates = [b for b in bearish_zones if b.zone_low > current_price]
    if resistance_candidates:
        nearest_resistance = min(resistance_candidates, key=lambda b: b.zone_low)

    total_active = len([b for b in mitigation_blocks if b.is_active])

    return MitigationResult(
        all_blocks=mitigation_blocks,
        unmitigated=unmitigated,
        respected=respected,
        partial=partial,
        full=full,
        bullish_zones=bullish_zones,
        bearish_zones=bearish_zones,
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        total_active=total_active,
    )


def get_unmitigated_obs(df: pl.DataFrame, lookback: int = 100) -> List[MitigationBlock]:
    """Get only unmitigated (strongest) Order Blocks."""
    result = track_mitigation_status(df, lookback)
    return result.unmitigated


def get_respected_zones(df: pl.DataFrame, lookback: int = 100) -> List[MitigationBlock]:
    """Get respected (confirmed) zones."""
    result = track_mitigation_status(df, lookback)
    return result.respected


def summarize_mitigation(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary dict for signal cards."""
    result = track_mitigation_status(df)

    return {
        "total_obs": len(result.all_blocks),
        "unmitigated_count": len(result.unmitigated),
        "respected_count": len(result.respected),
        "partial_count": len(result.partial),
        "full_count": len(result.full),
        "active_support_zones": len(result.bullish_zones),
        "active_resistance_zones": len(result.bearish_zones),
        "nearest_support": result.nearest_support.zone_high if result.nearest_support else None,
        "nearest_resistance": result.nearest_resistance.zone_low if result.nearest_resistance else None,
        "strongest_support_strength": result.bullish_zones[0].strength if result.bullish_zones else None,
        "strongest_resistance_strength": result.bearish_zones[0].strength if result.bearish_zones else None,
    }


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "mitigation_status": track_mitigation_status,
    "unmitigated_obs": get_unmitigated_obs,
    "respected_zones": get_respected_zones,
    "mitigation_summary": summarize_mitigation,
}

NAME = "mitigation_blocks"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("MITIGATION BLOCKS TEST")
    print("=" * 60)
    print(f"Using Order Blocks module: {_USE_ORDER_BLOCKS}")

    np.random.seed(42)
    n = 80

    prices = [100.0]
    for i in range(1, n):
        if i < 20:
            change = np.random.uniform(-0.5, 0.5)
        elif i == 20:
            change = 2.0  # Create bullish OB
        elif 21 <= i <= 25:
            change = np.random.uniform(0.5, 1.0)  # Impulse up
        elif 26 <= i <= 40:
            change = np.random.uniform(-0.3, 0.3)  # Consolidate
        elif 41 <= i <= 45:
            change = np.random.uniform(-0.5, -0.2)  # Come back to OB
        else:
            change = np.random.uniform(0.2, 0.6)  # Bounce
        prices.append(prices[-1] + change)

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.3, 0.8) for p in prices],
        "low": [p - np.random.uniform(0.3, 0.8) for p in prices],
        "close": [prices[i] + np.random.uniform(-0.2, 0.2) for i in range(n)],
        "volume": [10000 + np.random.randint(-2000, 2000) for _ in range(n)],
    })

    result = track_mitigation_status(df, lookback=80)

    print(f"\n📊 MITIGATION STATUS:")
    print(f"   Total OBs: {len(result.all_blocks)}")
    print(f"   Unmitigated: {len(result.unmitigated)}")
    print(f"   Respected: {len(result.respected)}")
    print(f"   Partial: {len(result.partial)}")
    print(f"   Full: {len(result.full)}")

    print(f"\n📊 ACTIVE ZONES:")
    print(f"   Support Zones: {len(result.bullish_zones)}")
    print(f"   Resistance Zones: {len(result.bearish_zones)}")

    if result.nearest_support:
        print(f"\n   Nearest Support: {result.nearest_support.zone_high:.2f}")
        print(f"      Status: {result.nearest_support.status.value}")
        print(f"      Strength: {result.nearest_support.strength:.0f}")

    print(f"\n📊 SUMMARY:")
    summary = summarize_mitigation(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ Mitigation Blocks test complete!")
