# queen/technicals/indicators/delta_volume.py
"""
Delta Volume Analysis Module
============================
Analyzes buy vs sell pressure using price-volume relationships.

Key Concepts:
- Delta: Difference between buying and selling volume
- Cumulative Delta: Running total of delta
- Positive Delta: Buyers in control (bullish)
- Negative Delta: Sellers in control (bearish)
- Delta Divergence: Price vs Delta disagreement (reversal signal)

Without tick data, we estimate delta using:
- Close vs Open: If close > open, assume more buying
- Close position in range: Where close is relative to H-L

Usage:
    from queen.technicals.indicators.delta_volume import (
        calculate_delta,
        calculate_cumulative_delta,
        detect_delta_divergence,
        DeltaResult,
    )

    result = calculate_delta(df)
    if result.cumulative_delta > 0:
        print("Buyers in control")

Note: This is an approximation without actual tick/trade data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Literal, Dict, Any
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
# Settings
# ---------------------------------------------------------------------------
DELTA_SETTINGS = {
    "lookback_default": 20,
    "divergence_threshold": 0.7,    # Delta vs price correlation threshold
    "strong_delta_threshold": 1.5,  # Strong delta = > 1.5x average
    "weak_delta_threshold": 0.5,    # Weak delta = < 0.5x average
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
@dataclass
class DeltaBar:
    """Delta information for a single bar."""
    bar_index: int
    delta: float           # Estimated delta (positive = buying)
    buy_volume: float      # Estimated buying volume
    sell_volume: float     # Estimated selling volume
    delta_pct: float       # Delta as percentage of total volume
    is_bullish: bool       # Positive delta
    strength: str          # "strong", "normal", "weak"


@dataclass
class DeltaResult:
    """
    Complete Delta Volume analysis result.

    Attributes:
        bars: Delta information per bar
        cumulative_delta: Running total of delta
        avg_delta: Average delta over period
        delta_trend: Overall delta trend
        last_delta: Most recent bar's delta
        divergence_detected: Price vs delta divergence
        divergence_type: Type of divergence if detected
        buyers_in_control: Whether buyers dominate
        bias: Trading bias based on delta
    """
    bars: List[DeltaBar]
    cumulative_delta: float
    avg_delta: float
    delta_trend: Literal["rising", "falling", "flat"]
    last_delta: float
    divergence_detected: bool
    divergence_type: Optional[str]
    buyers_in_control: bool
    bias: Literal["bullish", "bearish", "neutral"]


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------
def _estimate_delta(
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> tuple[float, float, float]:
    """
    Estimate buying and selling volume from OHLC.

    Method: Use close position in range to estimate buy/sell ratio.
    - Close at high = 100% buying
    - Close at low = 100% selling
    - Close at mid = 50/50

    Returns: (delta, buy_volume, sell_volume)
    """
    if volume <= 0:
        return 0.0, 0.0, 0.0

    bar_range = high - low
    if bar_range <= 0:
        # No range = neutral
        return 0.0, volume / 2, volume / 2

    # Calculate close position (0 = low, 1 = high)
    close_position = (close - low) / bar_range

    # Adjust for open (if close > open, more bullish bias)
    open_position = (open_price - low) / bar_range

    # Weight close position more but consider open too
    buy_pct = close_position * 0.7 + (1 if close > open_price else 0) * 0.3
    buy_pct = max(0, min(1, buy_pct))

    buy_volume = volume * buy_pct
    sell_volume = volume * (1 - buy_pct)
    delta = buy_volume - sell_volume

    return delta, buy_volume, sell_volume


def _determine_strength(delta: float, avg_delta: float) -> str:
    """Determine delta strength relative to average."""
    if avg_delta == 0:
        return "normal"

    ratio = abs(delta) / abs(avg_delta) if avg_delta != 0 else 1

    if ratio >= DELTA_SETTINGS["strong_delta_threshold"]:
        return "strong"
    elif ratio <= DELTA_SETTINGS["weak_delta_threshold"]:
        return "weak"
    return "normal"


def _detect_divergence(
    df: pl.DataFrame,
    deltas: List[float],
    lookback: int = 10,
) -> tuple[bool, Optional[str]]:
    """
    Detect price vs delta divergence.

    Bullish divergence: Price making lower lows, delta making higher lows
    Bearish divergence: Price making higher highs, delta making lower highs
    """
    if len(deltas) < lookback or df.height < lookback:
        return False, None

    closes = df["close"].tail(lookback).to_list()
    recent_deltas = deltas[-lookback:]

    # Calculate trends
    price_change = closes[-1] - closes[0]
    delta_change = sum(recent_deltas[-5:]) - sum(recent_deltas[:5])

    # Cumulative delta over period
    cum_delta = sum(recent_deltas)

    # Bullish divergence: Price down but delta positive/rising
    if price_change < 0 and cum_delta > 0:
        return True, "bullish_divergence"

    # Bearish divergence: Price up but delta negative/falling
    if price_change > 0 and cum_delta < 0:
        return True, "bearish_divergence"

    return False, None


# ---------------------------------------------------------------------------
# Main Analysis Functions
# ---------------------------------------------------------------------------
def calculate_delta(
    df: pl.DataFrame,
    lookback: int = 20,
) -> DeltaResult:
    """
    Calculate Delta Volume analysis.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    lookback : int
        Number of bars to analyze

    Returns
    -------
    DeltaResult
        Complete delta analysis

    Example
    -------
    >>> result = calculate_delta(df, lookback=20)
    >>> if result.buyers_in_control:
    ...     print("Bullish pressure!")
    """
    if df is None or df.is_empty() or df.height < 5:
        return DeltaResult(
            bars=[], cumulative_delta=0, avg_delta=0, delta_trend="flat",
            last_delta=0, divergence_detected=False, divergence_type=None,
            buyers_in_control=False, bias="neutral",
        )

    # Get window
    window = df.tail(lookback) if df.height > lookback else df

    opens = window["open"].to_list()
    highs = window["high"].to_list()
    lows = window["low"].to_list()
    closes = window["close"].to_list()
    volumes = window["volume"].to_list() if "volume" in window.columns else [1.0] * len(opens)

    # Calculate delta for each bar
    bars: List[DeltaBar] = []
    deltas: List[float] = []
    cumulative = 0.0

    for i, (o, h, l, c, v) in enumerate(zip(opens, highs, lows, closes, volumes)):
        delta, buy_vol, sell_vol = _estimate_delta(o, h, l, c, v)
        deltas.append(delta)
        cumulative += delta

        bars.append(DeltaBar(
            bar_index=i,
            delta=delta,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            delta_pct=(delta / v * 100) if v > 0 else 0,
            is_bullish=delta > 0,
            strength="normal",  # Will update after calculating average
        ))

    # Calculate average and update strength
    avg_delta = sum(abs(d) for d in deltas) / len(deltas) if deltas else 0

    for bar in bars:
        bar.strength = _determine_strength(bar.delta, avg_delta)

    # Delta trend
    if len(deltas) >= 5:
        recent_sum = sum(deltas[-5:])
        earlier_sum = sum(deltas[:5])
        if recent_sum > earlier_sum * 1.2:
            delta_trend = "rising"
        elif recent_sum < earlier_sum * 0.8:
            delta_trend = "falling"
        else:
            delta_trend = "flat"
    else:
        delta_trend = "flat"

    # Divergence
    divergence, div_type = _detect_divergence(df, deltas, min(lookback, 10))

    # Overall bias
    last_delta = deltas[-1] if deltas else 0
    buyers_in_control = cumulative > 0

    if cumulative > avg_delta * 2:
        bias = "bullish"
    elif cumulative < -avg_delta * 2:
        bias = "bearish"
    elif buyers_in_control:
        bias = "bullish"
    elif cumulative < 0:
        bias = "bearish"
    else:
        bias = "neutral"

    return DeltaResult(
        bars=bars,
        cumulative_delta=cumulative,
        avg_delta=avg_delta,
        delta_trend=delta_trend,
        last_delta=last_delta,
        divergence_detected=divergence,
        divergence_type=div_type,
        buyers_in_control=buyers_in_control,
        bias=bias,
    )


def calculate_cumulative_delta(df: pl.DataFrame, lookback: int = 50) -> float:
    """Get cumulative delta over period."""
    result = calculate_delta(df, lookback)
    return result.cumulative_delta


def detect_delta_divergence(df: pl.DataFrame) -> tuple[bool, Optional[str]]:
    """Check for price vs delta divergence."""
    result = calculate_delta(df)
    return result.divergence_detected, result.divergence_type


def summarize_delta(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary dict for signal cards."""
    result = calculate_delta(df)

    # Count bullish vs bearish bars
    bullish_bars = sum(1 for b in result.bars if b.is_bullish)
    bearish_bars = len(result.bars) - bullish_bars

    return {
        "cumulative_delta": round(result.cumulative_delta, 0),
        "avg_delta": round(result.avg_delta, 0),
        "last_delta": round(result.last_delta, 0),
        "delta_trend": result.delta_trend,
        "buyers_in_control": result.buyers_in_control,
        "delta_bias": result.bias,
        "divergence_detected": result.divergence_detected,
        "divergence_type": result.divergence_type,
        "bullish_bars": bullish_bars,
        "bearish_bars": bearish_bars,
        "bullish_pct": round(bullish_bars / len(result.bars) * 100, 1) if result.bars else 0,
    }


def attach_delta_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Attach delta columns to DataFrame."""
    result = calculate_delta(df)

    # Calculate delta for each row
    delta_values = []
    cum_delta = 0

    for i in range(df.height):
        o = float(df["open"][i])
        h = float(df["high"][i])
        l = float(df["low"][i])
        c = float(df["close"][i])
        v = float(df["volume"][i]) if "volume" in df.columns else 1.0

        d, _, _ = _estimate_delta(o, h, l, c, v)
        cum_delta += d
        delta_values.append(cum_delta)

    return df.with_columns([
        pl.Series("delta_cumulative", delta_values),
        pl.lit(result.buyers_in_control).alias("buyers_in_control"),
        pl.lit(result.bias).alias("delta_bias"),
    ])


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "delta": calculate_delta,
    "cumulative_delta": calculate_cumulative_delta,
    "delta_divergence": detect_delta_divergence,
    "delta_summary": summarize_delta,
    "delta_attach": attach_delta_signals,
}

NAME = "delta_volume"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("DELTA VOLUME TEST")
    print("=" * 60)

    np.random.seed(42)
    n = 40

    # Create trending data with volume
    prices = [100.0]
    for i in range(1, n):
        # Uptrend with pullbacks
        if i < 25:
            change = np.random.uniform(0.0, 0.6)  # Bullish
        else:
            change = np.random.uniform(-0.4, 0.2)  # Pullback
        prices.append(prices[-1] + change)

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.3, 0.8) for p in prices],
        "low": [p - np.random.uniform(0.2, 0.5) for p in prices],
        "close": [prices[i] + np.random.uniform(-0.1, 0.3) for i in range(n)],
        "volume": [15000 + np.random.randint(-5000, 5000) for _ in range(n)],
    })

    result = calculate_delta(df, lookback=30)

    print(f"\n📊 DELTA ANALYSIS:")
    print(f"   Cumulative Delta: {result.cumulative_delta:,.0f}")
    print(f"   Average Delta: {result.avg_delta:,.0f}")
    print(f"   Last Delta: {result.last_delta:,.0f}")
    print(f"   Delta Trend: {result.delta_trend}")

    print(f"\n📊 CONTROL:")
    print(f"   Buyers in Control: {result.buyers_in_control}")
    print(f"   Bias: {result.bias}")

    print(f"\n📊 DIVERGENCE:")
    print(f"   Detected: {result.divergence_detected}")
    print(f"   Type: {result.divergence_type}")

    print(f"\n📊 BAR BREAKDOWN:")
    bullish = sum(1 for b in result.bars if b.is_bullish)
    print(f"   Bullish Bars: {bullish}")
    print(f"   Bearish Bars: {len(result.bars) - bullish}")

    print(f"\n📊 SUMMARY:")
    summary = summarize_delta(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ Delta Volume test complete!")
