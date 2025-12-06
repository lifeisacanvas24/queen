# queen/technicals/microstructure/fvg.py
"""
Fair Value Gap (FVG) Detection Module
=====================================
Identifies institutional imbalances where price moved too fast,
leaving gaps that often act as magnets for future price action.

FVG Types:
- Bullish FVG: Gap between candle[i-2].high and candle[i].low (price moved up fast)
- Bearish FVG: Gap between candle[i-2].low and candle[i].high (price moved down fast)

Usage:
    from queen.technicals.microstructure.fvg import detect_fvg, summarize_fvg

    result = detect_fvg(df, lookback=50)
    summary = summarize_fvg(df, current_price=2850.0)

Settings Integration:
    All thresholds configurable via settings/breakout_settings.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Literal
import polars as pl

# ---------------------------------------------------------------------------
# Try to use existing helpers, fallback to local implementation
# ---------------------------------------------------------------------------
try:
    from queen.helpers.ta_math import atr_wilder
    _USE_EXISTING_ATR = True
except ImportError:
    _USE_EXISTING_ATR = False

# ---------------------------------------------------------------------------
# Settings (import from settings when available, fallback to defaults)
# ---------------------------------------------------------------------------
try:
    from queen.settings.breakout_settings import FVG_SETTINGS
except ImportError:
    # Fallback defaults - move to settings/breakout_settings.py
    FVG_SETTINGS = {
        "min_gap_atr_ratio": 0.3,      # Minimum gap size as % of ATR
        "max_age_bars": 50,             # How far back to look for unfilled FVGs
        "fill_tolerance_pct": 0.1,      # Gap considered filled if 90% filled
        "significance_atr_ratio": 0.5,  # Large FVG threshold
        "lookback_default": 50,         # Default lookback period
    }


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class FVGZone:
    """Represents a single Fair Value Gap zone"""
    type: Literal["bullish", "bearish"]
    top: float                          # Upper boundary of gap
    bottom: float                       # Lower boundary of gap
    midpoint: float                     # Middle of gap (often tested)
    size: float                         # Gap size in price
    size_atr_ratio: float              # Gap size relative to ATR
    bar_index: int                      # When the FVG was created
    timestamp: Optional[str] = None     # Timestamp of creation
    filled: bool = False                # Has price filled this gap?
    fill_percentage: float = 0.0        # How much of gap was filled (0-100)

    def contains_price(self, price: float) -> bool:
        """Check if a price is within this FVG zone"""
        return self.bottom <= price <= self.top

    def distance_from(self, price: float) -> float:
        """Distance from price to nearest edge of zone"""
        if price < self.bottom:
            return self.bottom - price
        elif price > self.top:
            return price - self.top
        return 0.0  # Price is inside zone


@dataclass
class FVGResult:
    """Complete FVG analysis result"""
    bullish_zones: List[FVGZone]        # Unfilled bullish FVGs (support)
    bearish_zones: List[FVGZone]        # Unfilled bearish FVGs (resistance)
    nearest_above: Optional[FVGZone]    # Nearest FVG above current price
    nearest_below: Optional[FVGZone]    # Nearest FVG below current price
    in_fvg: bool                        # Is current price inside an FVG?
    current_fvg: Optional[FVGZone]      # The FVG price is currently in
    total_unfilled: int                 # Total unfilled FVG count
    bias: Literal["bullish", "bearish", "neutral"]  # Overall FVG bias


# ---------------------------------------------------------------------------
# Core Detection Functions
# ---------------------------------------------------------------------------
def _ensure_sorted(df: pl.DataFrame, ts_col: str = "timestamp") -> pl.DataFrame:
    """Ensure DataFrame is sorted by timestamp ascending"""
    if ts_col in df.columns:
        return df.sort(ts_col)
    return df


def _calculate_atr(df: pl.DataFrame, period: int = 14) -> pl.Series:
    """Calculate ATR for gap size normalization"""
    # Try to use existing helper
    if _USE_EXISTING_ATR:
        try:
            high = df["high"].to_numpy()
            low = df["low"].to_numpy()
            close = df["close"].to_numpy()
            atr_arr = atr_wilder(high, low, close, period)
            return pl.Series("atr", atr_arr)
        except Exception:
            pass  # Fall through to local implementation

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


def _detect_single_fvg(
    i: int,
    high: List[float],
    low: List[float],
    atr_val: float,
    timestamps: Optional[List] = None,
    min_gap_ratio: float = 0.3,
) -> Optional[FVGZone]:
    """
    Detect FVG at bar index i using 3-candle pattern:
    - Bullish FVG: candle[i-2].high < candle[i].low (gap up)
    - Bearish FVG: candle[i-2].low > candle[i].high (gap down)
    """
    if i < 2:
        return None

    if atr_val is None or atr_val <= 0:
        return None

    candle_minus_2_high = high[i - 2]
    candle_minus_2_low = low[i - 2]
    candle_i_high = high[i]
    candle_i_low = low[i]

    # Check for Bullish FVG (gap up)
    if candle_i_low > candle_minus_2_high:
        gap_size = candle_i_low - candle_minus_2_high
        gap_ratio = gap_size / atr_val

        if gap_ratio >= min_gap_ratio:
            return FVGZone(
                type="bullish",
                top=candle_i_low,
                bottom=candle_minus_2_high,
                midpoint=(candle_i_low + candle_minus_2_high) / 2,
                size=gap_size,
                size_atr_ratio=gap_ratio,
                bar_index=i,
                timestamp=str(timestamps[i]) if timestamps else None,
                filled=False,
                fill_percentage=0.0,
            )

    # Check for Bearish FVG (gap down)
    if candle_i_high < candle_minus_2_low:
        gap_size = candle_minus_2_low - candle_i_high
        gap_ratio = gap_size / atr_val

        if gap_ratio >= min_gap_ratio:
            return FVGZone(
                type="bearish",
                top=candle_minus_2_low,
                bottom=candle_i_high,
                midpoint=(candle_minus_2_low + candle_i_high) / 2,
                size=gap_size,
                size_atr_ratio=gap_ratio,
                bar_index=i,
                timestamp=str(timestamps[i]) if timestamps else None,
                filled=False,
                fill_percentage=0.0,
            )

    return None


def _check_fvg_fill(
    zone: FVGZone,
    subsequent_highs: List[float],
    subsequent_lows: List[float],
    fill_tolerance: float = 0.1,
) -> FVGZone:
    """
    Check if an FVG has been filled by subsequent price action.
    Updates the zone's filled status and fill_percentage.
    """
    if not subsequent_highs or not subsequent_lows:
        return zone

    max_high = max(subsequent_highs)
    min_low = min(subsequent_lows)

    gap_size = zone.top - zone.bottom

    if zone.type == "bullish":
        # Bullish FVG filled when price drops into the gap
        if min_low <= zone.top:
            filled_amount = zone.top - max(min_low, zone.bottom)
            fill_pct = min(100.0, (filled_amount / gap_size) * 100)
            zone.fill_percentage = fill_pct
            zone.filled = fill_pct >= (100.0 - fill_tolerance * 100)
    else:
        # Bearish FVG filled when price rises into the gap
        if max_high >= zone.bottom:
            filled_amount = min(max_high, zone.top) - zone.bottom
            fill_pct = min(100.0, (filled_amount / gap_size) * 100)
            zone.fill_percentage = fill_pct
            zone.filled = fill_pct >= (100.0 - fill_tolerance * 100)

    return zone


def detect_fvg(
    df: pl.DataFrame,
    *,
    lookback: int = None,
    min_gap_atr_ratio: float = None,
    fill_tolerance_pct: float = None,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    timestamp_col: str = "timestamp",
) -> FVGResult:
    """
    Detect Fair Value Gaps in price data.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data with at minimum high, low, close columns
    lookback : int, optional
        Number of bars to look back for FVGs. Default from settings.
    min_gap_atr_ratio : float, optional
        Minimum gap size as ratio of ATR. Default from settings.
    fill_tolerance_pct : float, optional
        Tolerance for considering gap "filled". Default from settings.

    Returns
    -------
    FVGResult
        Complete analysis including all unfilled zones and nearest zones

    Example
    -------
    >>> result = detect_fvg(df, lookback=50)
    >>> print(f"Found {result.total_unfilled} unfilled FVGs")
    >>> if result.nearest_below:
    ...     print(f"Support FVG at {result.nearest_below.bottom}-{result.nearest_below.top}")
    """
    # Apply settings defaults
    lookback = lookback or FVG_SETTINGS["lookback_default"]
    min_gap_atr_ratio = min_gap_atr_ratio or FVG_SETTINGS["min_gap_atr_ratio"]
    fill_tolerance_pct = fill_tolerance_pct or FVG_SETTINGS["fill_tolerance_pct"]

    # Ensure sorted
    df = _ensure_sorted(df, timestamp_col)

    # Get data as lists for faster iteration
    n = len(df)
    if n < 3:
        return FVGResult(
            bullish_zones=[],
            bearish_zones=[],
            nearest_above=None,
            nearest_below=None,
            in_fvg=False,
            current_fvg=None,
            total_unfilled=0,
            bias="neutral",
        )

    high = df[high_col].to_list()
    low = df[low_col].to_list()
    close = df[close_col].to_list()
    timestamps = df[timestamp_col].to_list() if timestamp_col in df.columns else None

    # Calculate ATR
    atr_series = _calculate_atr(df)
    atr = atr_series.to_list()

    # Get current price
    current_price = close[-1]

    # Detect FVGs within lookback period
    start_idx = max(2, n - lookback)
    all_zones: List[FVGZone] = []

    for i in range(start_idx, n):
        atr_val = atr[i] if atr[i] is not None else atr[i - 1] if i > 0 else None
        zone = _detect_single_fvg(
            i, high, low, atr_val, timestamps, min_gap_atr_ratio
        )
        if zone:
            # Check if filled by subsequent price action
            subsequent_highs = high[i + 1:] if i + 1 < n else []
            subsequent_lows = low[i + 1:] if i + 1 < n else []
            zone = _check_fvg_fill(zone, subsequent_highs, subsequent_lows, fill_tolerance_pct)
            all_zones.append(zone)

    # Separate unfilled zones by type
    bullish_zones = [z for z in all_zones if z.type == "bullish" and not z.filled]
    bearish_zones = [z for z in all_zones if z.type == "bearish" and not z.filled]

    # Find nearest zones to current price
    nearest_above = None
    nearest_below = None
    current_fvg = None

    for zone in bullish_zones + bearish_zones:
        if zone.contains_price(current_price):
            current_fvg = zone
        elif zone.bottom > current_price:
            if nearest_above is None or zone.bottom < nearest_above.bottom:
                nearest_above = zone
        elif zone.top < current_price:
            if nearest_below is None or zone.top > nearest_below.top:
                nearest_below = zone

    # Determine bias based on FVG distribution
    bullish_count = len(bullish_zones)
    bearish_count = len(bearish_zones)

    if bullish_count > bearish_count + 2:
        bias = "bullish"
    elif bearish_count > bullish_count + 2:
        bias = "bearish"
    else:
        bias = "neutral"

    return FVGResult(
        bullish_zones=bullish_zones,
        bearish_zones=bearish_zones,
        nearest_above=nearest_above,
        nearest_below=nearest_below,
        in_fvg=current_fvg is not None,
        current_fvg=current_fvg,
        total_unfilled=len(bullish_zones) + len(bearish_zones),
        bias=bias,
    )


def summarize_fvg(
    df: pl.DataFrame,
    current_price: Optional[float] = None,
    **kwargs,
) -> dict:
    """
    Generate a summary dict suitable for signal cards and API responses.

    Returns
    -------
    dict with keys:
        - fvg_above: dict or None (nearest resistance FVG)
        - fvg_below: dict or None (nearest support FVG)
        - in_fvg: bool
        - fvg_bias: str
        - total_unfilled: int
        - bullish_count: int
        - bearish_count: int
    """
    result = detect_fvg(df, **kwargs)

    if current_price is None:
        current_price = df["close"].to_list()[-1]

    def zone_to_dict(zone: Optional[FVGZone]) -> Optional[dict]:
        if zone is None:
            return None
        return {
            "type": zone.type,
            "top": round(zone.top, 2),
            "bottom": round(zone.bottom, 2),
            "midpoint": round(zone.midpoint, 2),
            "size": round(zone.size, 2),
            "size_atr_ratio": round(zone.size_atr_ratio, 2),
            "distance": round(zone.distance_from(current_price), 2),
        }

    return {
        "fvg_above": zone_to_dict(result.nearest_above),
        "fvg_below": zone_to_dict(result.nearest_below),
        "in_fvg": result.in_fvg,
        "current_fvg": zone_to_dict(result.current_fvg) if result.current_fvg else None,
        "fvg_bias": result.bias,
        "total_unfilled": result.total_unfilled,
        "bullish_count": len(result.bullish_zones),
        "bearish_count": len(result.bearish_zones),
    }


# ---------------------------------------------------------------------------
# Polars DataFrame Extension (adds FVG columns)
# ---------------------------------------------------------------------------
def attach_fvg_signals(
    df: pl.DataFrame,
    lookback: int = 50,
) -> pl.DataFrame:
    """
    Attach FVG-related columns to DataFrame for use in signal generation.

    Adds columns:
        - fvg_bullish_nearby: bool (bullish FVG within 1% of price)
        - fvg_bearish_nearby: bool (bearish FVG within 1% of price)
        - fvg_in_zone: bool (price is inside an FVG)
        - fvg_bias: str ("bullish", "bearish", "neutral")
    """
    result = detect_fvg(df, lookback=lookback)
    n = len(df)

    # Current price for distance calculations
    close = df["close"].to_list()
    current_price = close[-1]

    # Create column values (simplified - just for last bar context)
    fvg_bullish_nearby = result.nearest_below is not None and \
        result.nearest_below.distance_from(current_price) / current_price < 0.01

    fvg_bearish_nearby = result.nearest_above is not None and \
        result.nearest_above.distance_from(current_price) / current_price < 0.01

    # Add columns
    return df.with_columns([
        pl.lit(fvg_bullish_nearby).alias("fvg_bullish_nearby"),
        pl.lit(fvg_bearish_nearby).alias("fvg_bearish_nearby"),
        pl.lit(result.in_fvg).alias("fvg_in_zone"),
        pl.lit(result.bias).alias("fvg_bias"),
    ])


# ---------------------------------------------------------------------------
# Registry Export (for auto-discovery)
# ---------------------------------------------------------------------------
EXPORTS = {
    "fvg": detect_fvg,
    "fvg_summary": summarize_fvg,
    "fvg_attach": attach_fvg_signals,
}

NAME = "fvg"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    # Create sample data with FVGs
    np.random.seed(42)
    n = 100

    # Simulate price with some gaps
    base_price = 100.0
    prices = [base_price]
    for i in range(1, n):
        # Occasionally create gaps
        if i % 20 == 0:
            gap = np.random.uniform(1, 3) * (1 if np.random.random() > 0.5 else -1)
        else:
            gap = 0
        change = np.random.uniform(-0.5, 0.5) + gap
        prices.append(prices[-1] + change)

    # Create OHLCV
    df = pl.DataFrame({
        "timestamp": list(range(n)),
        "open": prices,
        "high": [p + np.random.uniform(0.5, 1.5) for p in prices],
        "low": [p - np.random.uniform(0.5, 1.5) for p in prices],
        "close": [p + np.random.uniform(-0.3, 0.3) for p in prices],
        "volume": [np.random.randint(1000, 10000) for _ in range(n)],
    })

    # Test detection
    result = detect_fvg(df, lookback=50)
    print(f"Total FVGs found: {result.total_unfilled}")
    print(f"Bullish FVGs: {len(result.bullish_zones)}")
    print(f"Bearish FVGs: {len(result.bearish_zones)}")
    print(f"Bias: {result.bias}")

    if result.nearest_below:
        print(f"Nearest support FVG: {result.nearest_below.bottom:.2f} - {result.nearest_below.top:.2f}")

    if result.nearest_above:
        print(f"Nearest resistance FVG: {result.nearest_above.bottom:.2f} - {result.nearest_above.top:.2f}")

    # Test summary
    summary = summarize_fvg(df)
    print(f"\nSummary: {summary}")
