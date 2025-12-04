"""Fair Value Gap (FVG) Detection Module
=====================================

Smart Money Concepts - Identifies institutional imbalances in price action.

A Fair Value Gap occurs when price moves so aggressively that it leaves
a gap between candle wicks, indicating institutional order flow.

Types:
- Bullish FVG: Gap up (current low > previous-previous high)
- Bearish FVG: Gap down (current high < previous-previous low)

Usage:
    from queen.technicals.microstructure.fvg import detect_fvg, find_fvg_zones

    # Get all FVG zones
    result = detect_fvg(df, lookback=50)

    # Get nearest FVG zones for trading
    zones = find_fvg_zones(df, current_price=1850.0)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

import polars as pl

# Import settings if available, otherwise use defaults
try:
    from queen.settings import fvg as FVG_SETTINGS
except ImportError:
    FVG_SETTINGS = None


# =============================================================================
# Configuration (centralized in settings/fvg.py)
# =============================================================================

def _get_config(key: str, default):
    """Get config from settings or use default"""
    if FVG_SETTINGS and hasattr(FVG_SETTINGS, key):
        return getattr(FVG_SETTINGS, key)
    return default


# Default configuration
MIN_GAP_ATR_MULT = _get_config("MIN_GAP_ATR_MULT", 0.1)  # Min gap size as ATR multiple
MAX_AGE_BARS = _get_config("MAX_AGE_BARS", 100)  # Max bars to look back
FILL_THRESHOLD_PCT = _get_config("FILL_THRESHOLD_PCT", 0.5)  # 50% fill = partially filled
MITIGATION_THRESHOLD_PCT = _get_config("MITIGATION_THRESHOLD_PCT", 1.0)  # 100% = fully mitigated


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FVGZone:
    """Represents a single Fair Value Gap zone"""

    type: Literal["bullish", "bearish"]
    top: float  # Upper boundary of gap
    bottom: float  # Lower boundary of gap
    midpoint: float  # Center of gap
    size: float  # Gap size in price
    size_pct: float  # Gap size as percentage
    bar_index: int  # When the FVG was created
    timestamp: Optional[str]  # Timestamp of FVG creation
    filled_pct: float  # How much of gap has been filled (0-100)
    is_mitigated: bool  # Fully filled/invalidated
    strength: Literal["strong", "moderate", "weak"]  # Based on gap size

    @property
    def is_valid(self) -> bool:
        """FVG is valid if not fully mitigated"""
        return not self.is_mitigated

    def contains_price(self, price: float) -> bool:
        """Check if price is within the FVG zone"""
        return self.bottom <= price <= self.top

    def distance_from(self, price: float) -> float:
        """Calculate distance from price to nearest edge of FVG"""
        if price < self.bottom:
            return self.bottom - price
        if price > self.top:
            return price - self.top
        return 0.0  # Price is inside FVG


@dataclass
class FVGResult:
    """Result of FVG detection"""

    bullish_fvgs: List[FVGZone]
    bearish_fvgs: List[FVGZone]
    nearest_bullish: Optional[FVGZone]  # Nearest unfilled bullish FVG below price
    nearest_bearish: Optional[FVGZone]  # Nearest unfilled bearish FVG above price
    total_bullish_zones: int
    total_bearish_zones: int
    fvg_bias: Literal["bullish", "bearish", "neutral"]  # Overall FVG bias

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "bullish_fvgs": [
                {
                    "top": z.top,
                    "bottom": z.bottom,
                    "midpoint": z.midpoint,
                    "size": z.size,
                    "size_pct": z.size_pct,
                    "filled_pct": z.filled_pct,
                    "strength": z.strength,
                    "is_valid": z.is_valid,
                }
                for z in self.bullish_fvgs if z.is_valid
            ],
            "bearish_fvgs": [
                {
                    "top": z.top,
                    "bottom": z.bottom,
                    "midpoint": z.midpoint,
                    "size": z.size,
                    "size_pct": z.size_pct,
                    "filled_pct": z.filled_pct,
                    "strength": z.strength,
                    "is_valid": z.is_valid,
                }
                for z in self.bearish_fvgs if z.is_valid
            ],
            "nearest_support": {
                "top": self.nearest_bullish.top,
                "bottom": self.nearest_bullish.bottom,
                "strength": self.nearest_bullish.strength,
            } if self.nearest_bullish else None,
            "nearest_resistance": {
                "top": self.nearest_bearish.top,
                "bottom": self.nearest_bearish.bottom,
                "strength": self.nearest_bearish.strength,
            } if self.nearest_bearish else None,
            "fvg_bias": self.fvg_bias,
            "total_bullish": self.total_bullish_zones,
            "total_bearish": self.total_bearish_zones,
        }


# =============================================================================
# Helper Functions
# =============================================================================

def _ensure_sorted(df: pl.DataFrame, ts_col: str = "timestamp") -> pl.DataFrame:
    """Ensure DataFrame is sorted by timestamp"""
    if ts_col in df.columns:
        return df.sort(ts_col)
    return df


def _calculate_atr(df: pl.DataFrame, period: int = 14) -> pl.Series:
    """Calculate ATR for gap size normalization"""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # True Range calculation
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pl.max_horizontal(tr1, tr2, tr3)

    # ATR as rolling mean
    return tr.rolling_mean(window_size=period)


def _classify_strength(size_pct: float, atr_mult: float) -> Literal["strong", "moderate", "weak"]:
    """Classify FVG strength based on size"""
    if atr_mult >= 1.5 or size_pct >= 1.0:
        return "strong"
    if atr_mult >= 0.75 or size_pct >= 0.5:
        return "moderate"
    return "weak"


def _calculate_fill_percentage(
    fvg_type: str,
    fvg_top: float,
    fvg_bottom: float,
    subsequent_highs: List[float],
    subsequent_lows: List[float],
) -> float:
    """Calculate how much of an FVG has been filled by subsequent price action"""
    fvg_size = fvg_top - fvg_bottom
    if fvg_size <= 0:
        return 100.0

    if fvg_type == "bullish":
        # Bullish FVG gets filled from above (price dropping into it)
        min_low = min(subsequent_lows) if subsequent_lows else fvg_top
        if min_low >= fvg_top:
            return 0.0  # Not touched
        if min_low <= fvg_bottom:
            return 100.0  # Fully filled
        filled = fvg_top - min_low
        return (filled / fvg_size) * 100
    # Bearish FVG gets filled from below (price rising into it)
    max_high = max(subsequent_highs) if subsequent_highs else fvg_bottom
    if max_high <= fvg_bottom:
        return 0.0  # Not touched
    if max_high >= fvg_top:
        return 100.0  # Fully filled
    filled = max_high - fvg_bottom
    return (filled / fvg_size) * 100


# =============================================================================
# Main Detection Functions
# =============================================================================

def detect_fvg(
    df: pl.DataFrame,
    *,
    lookback: int = 50,
    min_gap_atr_mult: float = MIN_GAP_ATR_MULT,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    timestamp_col: str = "timestamp",
) -> FVGResult:
    """Detect Fair Value Gaps in OHLCV data.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV DataFrame with at least high, low, close columns
    lookback : int
        Number of bars to analyze (default 50)
    min_gap_atr_mult : float
        Minimum gap size as multiple of ATR (default 0.1)

    Returns
    -------
    FVGResult
        Contains all detected FVGs and analysis

    Example
    -------
    >>> result = detect_fvg(df, lookback=100)
    >>> print(f"Found {result.total_bullish_zones} bullish FVGs")
    >>> if result.nearest_bullish:
    ...     print(f"Support zone: {result.nearest_bullish.bottom}-{result.nearest_bullish.top}")

    """
    df = _ensure_sorted(df, timestamp_col)

    # Need at least 3 bars for FVG detection
    if len(df) < 3:
        return FVGResult(
            bullish_fvgs=[],
            bearish_fvgs=[],
            nearest_bullish=None,
            nearest_bearish=None,
            total_bullish_zones=0,
            total_bearish_zones=0,
            fvg_bias="neutral",
        )

    # Calculate ATR for normalization
    atr_series = _calculate_atr(df, period=14)

    # Extract arrays for faster processing
    highs = df[high_col].to_list()
    lows = df[low_col].to_list()
    closes = df[close_col].to_list()

    timestamps = None
    if timestamp_col in df.columns:
        timestamps = df[timestamp_col].to_list()

    # Determine analysis range
    start_idx = max(2, len(df) - lookback)
    end_idx = len(df)

    bullish_fvgs: List[FVGZone] = []
    bearish_fvgs: List[FVGZone] = []

    current_price = closes[-1] if closes else 0

    # Scan for FVGs
    for i in range(start_idx, end_idx):
        # Need candles at i-2, i-1, i
        prev2_high = highs[i - 2]
        prev2_low = lows[i - 2]
        # prev1 is the gap candle (i-1) - we don't use it for boundaries
        curr_high = highs[i]
        curr_low = lows[i]

        atr = atr_series[i] if i < len(atr_series) else None
        if atr is None or atr <= 0:
            atr = (curr_high - curr_low) * 2  # Fallback

        # Bullish FVG: Current candle's low > 2-bars-ago candle's high
        # This means price gapped UP leaving an unfilled zone
        if curr_low > prev2_high:
            gap_size = curr_low - prev2_high
            gap_pct = (gap_size / prev2_high) * 100 if prev2_high > 0 else 0
            atr_mult = gap_size / atr if atr > 0 else 0

            if atr_mult >= min_gap_atr_mult:
                # Calculate how much has been filled by subsequent bars
                subsequent_lows = lows[i + 1:] if i + 1 < len(lows) else []
                subsequent_highs = highs[i + 1:] if i + 1 < len(highs) else []

                filled_pct = _calculate_fill_percentage(
                    "bullish", curr_low, prev2_high, subsequent_highs, subsequent_lows
                )

                fvg = FVGZone(
                    type="bullish",
                    top=curr_low,
                    bottom=prev2_high,
                    midpoint=(curr_low + prev2_high) / 2,
                    size=gap_size,
                    size_pct=gap_pct,
                    bar_index=i,
                    timestamp=str(timestamps[i]) if timestamps else None,
                    filled_pct=filled_pct,
                    is_mitigated=filled_pct >= MITIGATION_THRESHOLD_PCT * 100,
                    strength=_classify_strength(gap_pct, atr_mult),
                )
                bullish_fvgs.append(fvg)

        # Bearish FVG: Current candle's high < 2-bars-ago candle's low
        # This means price gapped DOWN leaving an unfilled zone
        if curr_high < prev2_low:
            gap_size = prev2_low - curr_high
            gap_pct = (gap_size / prev2_low) * 100 if prev2_low > 0 else 0
            atr_mult = gap_size / atr if atr > 0 else 0

            if atr_mult >= min_gap_atr_mult:
                subsequent_lows = lows[i + 1:] if i + 1 < len(lows) else []
                subsequent_highs = highs[i + 1:] if i + 1 < len(highs) else []

                filled_pct = _calculate_fill_percentage(
                    "bearish", prev2_low, curr_high, subsequent_highs, subsequent_lows
                )

                fvg = FVGZone(
                    type="bearish",
                    top=prev2_low,
                    bottom=curr_high,
                    midpoint=(prev2_low + curr_high) / 2,
                    size=gap_size,
                    size_pct=gap_pct,
                    bar_index=i,
                    timestamp=str(timestamps[i]) if timestamps else None,
                    filled_pct=filled_pct,
                    is_mitigated=filled_pct >= MITIGATION_THRESHOLD_PCT * 100,
                    strength=_classify_strength(gap_pct, atr_mult),
                )
                bearish_fvgs.append(fvg)

    # Find nearest valid FVGs to current price
    valid_bullish = [f for f in bullish_fvgs if f.is_valid]
    valid_bearish = [f for f in bearish_fvgs if f.is_valid]

    # Nearest bullish FVG below current price (support)
    bullish_below = [f for f in valid_bullish if f.top <= current_price]
    nearest_bullish = max(bullish_below, key=lambda f: f.top) if bullish_below else None

    # Nearest bearish FVG above current price (resistance)
    bearish_above = [f for f in valid_bearish if f.bottom >= current_price]
    nearest_bearish = min(bearish_above, key=lambda f: f.bottom) if bearish_above else None

    # Determine overall FVG bias
    bullish_count = len(valid_bullish)
    bearish_count = len(valid_bearish)

    if bullish_count > bearish_count * 1.5:
        fvg_bias = "bullish"
    elif bearish_count > bullish_count * 1.5:
        fvg_bias = "bearish"
    else:
        fvg_bias = "neutral"

    return FVGResult(
        bullish_fvgs=bullish_fvgs,
        bearish_fvgs=bearish_fvgs,
        nearest_bullish=nearest_bullish,
        nearest_bearish=nearest_bearish,
        total_bullish_zones=len(valid_bullish),
        total_bearish_zones=len(valid_bearish),
        fvg_bias=fvg_bias,
    )


def find_fvg_zones(
    df: pl.DataFrame,
    current_price: float,
    *,
    lookback: int = 50,
    max_zones: int = 3,
) -> dict:
    """Find FVG zones near current price for trading decisions.

    Returns a simplified dict suitable for signal cards:
    {
        "fvg_above": {"start": 1850, "end": 1865, "strength": "moderate"},
        "fvg_below": {"start": 1820, "end": 1835, "strength": "strong"},
        "fvg_bias": "bullish"
    }
    """
    result = detect_fvg(df, lookback=lookback)

    output = {
        "fvg_above": None,
        "fvg_below": None,
        "fvg_bias": result.fvg_bias,
        "bullish_zones": result.total_bullish_zones,
        "bearish_zones": result.total_bearish_zones,
    }

    if result.nearest_bearish:
        output["fvg_above"] = {
            "start": round(result.nearest_bearish.bottom, 2),
            "end": round(result.nearest_bearish.top, 2),
            "strength": result.nearest_bearish.strength,
            "filled_pct": round(result.nearest_bearish.filled_pct, 1),
        }

    if result.nearest_bullish:
        output["fvg_below"] = {
            "start": round(result.nearest_bullish.bottom, 2),
            "end": round(result.nearest_bullish.top, 2),
            "strength": result.nearest_bullish.strength,
            "filled_pct": round(result.nearest_bullish.filled_pct, 1),
        }

    return output


def summarize_fvg(df: pl.DataFrame, lookback: int = 50) -> dict:
    """Generate a summary suitable for indicator display.

    Returns
    -------
    dict with keys:
        - fvg_bias: "bullish" | "bearish" | "neutral"
        - bullish_zones: int
        - bearish_zones: int
        - nearest_support: float | None
        - nearest_resistance: float | None
        - signal: "BULLISH" | "BEARISH" | "NEUTRAL"
        - strength: 0-100

    """
    result = detect_fvg(df, lookback=lookback)

    # Calculate strength based on zone count and proximity
    current_price = df["close"].to_list()[-1] if len(df) > 0 else 0

    strength = 50  # Base
    if result.total_bullish_zones > result.total_bearish_zones:
        strength += min(25, result.total_bullish_zones * 5)
    elif result.total_bearish_zones > result.total_bullish_zones:
        strength -= min(25, result.total_bearish_zones * 5)

    # Adjust for proximity to zones
    if result.nearest_bullish and current_price > 0:
        dist_pct = (current_price - result.nearest_bullish.top) / current_price * 100
        if dist_pct < 1:  # Very close to support
            strength += 10

    if result.nearest_bearish and current_price > 0:
        dist_pct = (result.nearest_bearish.bottom - current_price) / current_price * 100
        if dist_pct < 1:  # Very close to resistance
            strength -= 10

    strength = max(0, min(100, strength))

    signal = "NEUTRAL"
    if result.fvg_bias == "bullish":
        signal = "BULLISH"
    elif result.fvg_bias == "bearish":
        signal = "BEARISH"

    return {
        "name": "FVG",
        "fvg_bias": result.fvg_bias,
        "bullish_zones": result.total_bullish_zones,
        "bearish_zones": result.total_bearish_zones,
        "nearest_support": result.nearest_bullish.midpoint if result.nearest_bullish else None,
        "nearest_resistance": result.nearest_bearish.midpoint if result.nearest_bearish else None,
        "signal": signal,
        "strength": strength,
        "description": f"{result.total_bullish_zones} bullish, {result.total_bearish_zones} bearish FVGs",
    }


# =============================================================================
# Exports for Registry
# =============================================================================

EXPORTS = {
    "fvg": detect_fvg,
    "fvg_zones": find_fvg_zones,
    "fvg_summary": summarize_fvg,
}


# =============================================================================
# CLI for Testing
# =============================================================================

if __name__ == "__main__":
    import numpy as np

    # Create test data with an FVG
    n = 100
    np.random.seed(42)

    # Generate base price series
    returns = np.random.randn(n) * 0.01
    prices = 100 * np.cumprod(1 + returns)

    # Inject a bullish FVG around bar 50
    prices[50] = prices[49] * 1.02  # Gap up
    prices[51] = prices[50] * 1.01

    # Inject a bearish FVG around bar 70
    prices[70] = prices[69] * 0.98  # Gap down
    prices[71] = prices[70] * 0.99

    df = pl.DataFrame({
        "timestamp": list(range(n)),
        "open": prices * (1 + np.random.randn(n) * 0.001),
        "high": prices * (1 + np.abs(np.random.randn(n) * 0.005)),
        "low": prices * (1 - np.abs(np.random.randn(n) * 0.005)),
        "close": prices,
        "volume": np.random.randint(1000, 10000, n),
    })

    result = detect_fvg(df, lookback=100)
    print(f"Bullish FVGs: {result.total_bullish_zones}")
    print(f"Bearish FVGs: {result.total_bearish_zones}")
    print(f"FVG Bias: {result.fvg_bias}")

    if result.nearest_bullish:
        print(f"Nearest Support: {result.nearest_bullish.bottom:.2f} - {result.nearest_bullish.top:.2f}")

    if result.nearest_bearish:
        print(f"Nearest Resistance: {result.nearest_bearish.bottom:.2f} - {result.nearest_bearish.top:.2f}")

    # Test summary
    summary = summarize_fvg(df)
    print(f"\nSummary: {summary}")
