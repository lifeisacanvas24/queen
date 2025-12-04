#queen/technicals/indicators/volume_confirmation.py
"""Volume Confirmation Module
==========================
Provides volume-based confirmation for breakouts and signals.
Key indicators:
- RVOL (Relative Volume): Current volume vs average
- Volume Spike Detection: Identifies unusual volume surges
- Volume Trend: Accumulation/Distribution assessment

"A breakout without volume is a fake breakout" - Market wisdom

Usage:
    from queen.technicals.indicators.volume_confirmation import (
        compute_rvol,
        detect_volume_spike,
        summarize_volume_confirmation,
    )

    # Add RVOL column to DataFrame
    df = compute_rvol(df, period=20)

    # Get volume spike detection
    spikes = detect_volume_spike(df, threshold=2.0)

    # Get summary for signal cards
    summary = summarize_volume_confirmation(df)

Settings Integration:
    All thresholds configurable via settings/volume_policy.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

import polars as pl

# ---------------------------------------------------------------------------
# Settings (import from settings when available, fallback to defaults)
# ---------------------------------------------------------------------------
try:
    from queen.settings.volume_policy import VOLUME_SETTINGS
except ImportError:
    # Fallback defaults - move to settings/volume_policy.py
    VOLUME_SETTINGS = {
        # RVOL settings
        "rvol_period": 20,              # Lookback for average volume
        "rvol_high_threshold": 1.5,     # RVOL >= 1.5 = high volume
        "rvol_very_high_threshold": 2.5, # RVOL >= 2.5 = very high
        "rvol_low_threshold": 0.7,      # RVOL < 0.7 = low volume

        # Volume spike settings
        "spike_threshold": 2.0,         # Volume > 2x average = spike
        "spike_lookback": 20,           # Bars to check for spikes

        # Volume trend settings
        "trend_period": 10,             # Bars for volume trend
        "accumulation_threshold": 1.2,  # Avg volume ratio for accumulation

        # Breakout confirmation
        "breakout_min_rvol": 1.5,       # Minimum RVOL for valid breakout
    }


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class VolumeSpike:
    """Represents a detected volume spike"""

    bar_index: int
    timestamp: Optional[str]
    volume: float
    rvol: float                         # Relative volume at spike
    price_change_pct: float             # Price change during spike
    direction: Literal["up", "down"]    # Price direction during spike
    significance: Literal["high", "very_high", "extreme"]


@dataclass
class VolumeConfirmationResult:
    """Complete volume analysis result"""

    current_rvol: float                 # Latest RVOL
    rvol_label: Literal["very_low", "low", "normal", "high", "very_high", "extreme"]
    avg_volume: float                   # Average volume (period)
    current_volume: float               # Latest volume

    # Trend analysis
    volume_trend: Literal["increasing", "decreasing", "stable"]
    volume_trend_strength: float        # 0-100

    # Spike detection
    recent_spikes: List[VolumeSpike]
    spike_count_recent: int             # Spikes in last N bars

    # Accumulation/Distribution
    accumulation_signal: Literal["accumulating", "distributing", "neutral"]

    # Breakout readiness
    breakout_volume_ready: bool         # Is volume sufficient for breakout?

    # Display value (for UI)
    display_value: str                  # e.g., "2.3x"


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------
def compute_rvol(
    df: pl.DataFrame,
    period: int = None,
    volume_col: str = "volume",
) -> pl.DataFrame:
    """Add RVOL (Relative Volume) column to DataFrame.

    RVOL = Current Volume / Average Volume (period)

    Parameters
    ----------
    df : pl.DataFrame
        DataFrame with volume column
    period : int, optional
        Lookback period for average. Default from settings.
    volume_col : str
        Name of volume column

    Returns
    -------
    pl.DataFrame with added columns:
        - rvol: float (relative volume ratio)
        - rvol_label: str (categorical label)
        - volume_avg: float (rolling average)

    """
    period = period or VOLUME_SETTINGS["rvol_period"]

    high_thresh = VOLUME_SETTINGS["rvol_high_threshold"]
    very_high_thresh = VOLUME_SETTINGS["rvol_very_high_threshold"]
    low_thresh = VOLUME_SETTINGS["rvol_low_threshold"]

    df = df.with_columns([
        # Rolling average volume
        pl.col(volume_col).rolling_mean(window_size=period).alias("volume_avg"),
    ])

    df = df.with_columns([
        # RVOL calculation
        (pl.col(volume_col) / pl.col("volume_avg")).alias("rvol"),
    ])

    # Add categorical label
    df = df.with_columns([
        pl.when(pl.col("rvol") >= 4.0)
          .then(pl.lit("extreme"))
          .when(pl.col("rvol") >= very_high_thresh)
          .then(pl.lit("very_high"))
          .when(pl.col("rvol") >= high_thresh)
          .then(pl.lit("high"))
          .when(pl.col("rvol") >= low_thresh)
          .then(pl.lit("normal"))
          .when(pl.col("rvol") >= 0.5)
          .then(pl.lit("low"))
          .otherwise(pl.lit("very_low"))
          .alias("rvol_label"),
    ])

    return df


def detect_volume_spike(
    df: pl.DataFrame,
    threshold: float = None,
    lookback: int = None,
    volume_col: str = "volume",
    close_col: str = "close",
    timestamp_col: str = "timestamp",
) -> List[VolumeSpike]:
    """Detect volume spikes in the data.

    Parameters
    ----------
    df : pl.DataFrame
        DataFrame with volume and price columns
    threshold : float, optional
        Volume spike threshold (multiple of average). Default from settings.
    lookback : int, optional
        How many bars back to scan. Default from settings.

    Returns
    -------
    List[VolumeSpike]
        List of detected volume spikes, most recent first

    """
    threshold = threshold or VOLUME_SETTINGS["spike_threshold"]
    lookback = lookback or VOLUME_SETTINGS["spike_lookback"]

    # Ensure RVOL is calculated
    if "rvol" not in df.columns:
        df = compute_rvol(df, volume_col=volume_col)

    # Get data as lists
    n = len(df)
    volumes = df[volume_col].to_list()
    rvols = df["rvol"].to_list()
    closes = df[close_col].to_list()
    timestamps = df[timestamp_col].to_list() if timestamp_col in df.columns else None

    spikes: List[VolumeSpike] = []

    start_idx = max(1, n - lookback)
    for i in range(start_idx, n):
        rvol = rvols[i]
        if rvol is None:
            continue

        if rvol >= threshold:
            # Calculate price change
            price_change = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
            direction = "up" if price_change > 0 else "down"

            # Determine significance
            if rvol >= 4.0:
                significance = "extreme"
            elif rvol >= VOLUME_SETTINGS["rvol_very_high_threshold"]:
                significance = "very_high"
            else:
                significance = "high"

            spikes.append(VolumeSpike(
                bar_index=i,
                timestamp=str(timestamps[i]) if timestamps else None,
                volume=volumes[i],
                rvol=round(rvol, 2),
                price_change_pct=round(price_change, 2),
                direction=direction,
                significance=significance,
            ))

    # Return most recent first
    return list(reversed(spikes))


def compute_volume_trend(
    df: pl.DataFrame,
    period: int = None,
    volume_col: str = "volume",
) -> dict:
    """Analyze volume trend over recent bars.

    Returns
    -------
    dict with:
        - trend: "increasing" | "decreasing" | "stable"
        - strength: 0-100 (how strong is the trend)
        - slope: float (volume change rate)

    """
    period = period or VOLUME_SETTINGS["trend_period"]

    if len(df) < period:
        return {
            "trend": "stable",
            "strength": 0.0,
            "slope": 0.0,
        }

    volumes = df[volume_col].tail(period).to_list()

    # Simple linear regression slope
    n = len(volumes)
    x_mean = (n - 1) / 2
    y_mean = sum(volumes) / n

    numerator = sum((i - x_mean) * (volumes[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        slope = 0.0
    else:
        slope = numerator / denominator

    # Normalize slope relative to average volume
    avg_vol = y_mean
    if avg_vol > 0:
        normalized_slope = (slope / avg_vol) * 100
    else:
        normalized_slope = 0.0

    # Determine trend
    if normalized_slope > 5:
        trend = "increasing"
        strength = min(100, abs(normalized_slope) * 5)
    elif normalized_slope < -5:
        trend = "decreasing"
        strength = min(100, abs(normalized_slope) * 5)
    else:
        trend = "stable"
        strength = 0.0

    return {
        "trend": trend,
        "strength": round(strength, 1),
        "slope": round(normalized_slope, 2),
    }


def compute_accumulation_distribution(
    df: pl.DataFrame,
    period: int = 10,
) -> Literal["accumulating", "distributing", "neutral"]:
    """Determine if smart money is accumulating or distributing.

    Logic:
    - Accumulating: Price up + Volume up, or Price down + Volume down
    - Distributing: Price up + Volume down, or Price down + Volume up
    """
    if len(df) < period:
        return "neutral"

    recent = df.tail(period)

    closes = recent["close"].to_list()
    volumes = recent["volume"].to_list()

    # Price trend
    price_change = (closes[-1] - closes[0]) / closes[0] * 100

    # Volume trend
    vol_first_half = sum(volumes[:period // 2])
    vol_second_half = sum(volumes[period // 2:])
    vol_trend = "up" if vol_second_half > vol_first_half * 1.1 else (
        "down" if vol_second_half < vol_first_half * 0.9 else "flat"
    )

    # Determine signal
    if price_change > 1:
        if vol_trend == "up":
            return "accumulating"
        if vol_trend == "down":
            return "distributing"
    elif price_change < -1:
        if vol_trend == "down":
            return "accumulating"  # Selling exhaustion
        if vol_trend == "up":
            return "distributing"  # Strong selling

    return "neutral"


def check_breakout_volume_ready(
    df: pl.DataFrame,
    min_rvol: float = None,
) -> bool:
    """Check if current volume is sufficient for a valid breakout.

    Returns True if RVOL >= threshold
    """
    min_rvol = min_rvol or VOLUME_SETTINGS["breakout_min_rvol"]

    if "rvol" not in df.columns:
        df = compute_rvol(df)

    current_rvol = df["rvol"].to_list()[-1]

    return current_rvol is not None and current_rvol >= min_rvol


def summarize_volume_confirmation(
    df: pl.DataFrame,
    **kwargs,
) -> dict:
    """Generate a summary dict suitable for signal cards and API responses.

    Returns
    -------
    dict with keys suitable for UI display and signal scoring

    """
    # Ensure RVOL calculated
    if "rvol" not in df.columns:
        df = compute_rvol(df)

    # Get latest values
    rvol = df["rvol"].to_list()[-1]
    rvol_label = df["rvol_label"].to_list()[-1]
    volume = df["volume"].to_list()[-1]
    volume_avg = df["volume_avg"].to_list()[-1]

    # Detect spikes
    spikes = detect_volume_spike(df, **kwargs)

    # Volume trend
    trend_info = compute_volume_trend(df)

    # Accumulation/Distribution
    accum_signal = compute_accumulation_distribution(df)

    # Breakout readiness
    breakout_ready = check_breakout_volume_ready(df)

    # Display value (for UI cards)
    if rvol is not None:
        display = f"{rvol:.1f}x"
    else:
        display = "N/A"

    return {
        "current_rvol": round(rvol, 2) if rvol else None,
        "rvol_label": rvol_label,
        "display_value": display,
        "current_volume": volume,
        "avg_volume": round(volume_avg, 0) if volume_avg else None,
        "volume_trend": trend_info["trend"],
        "volume_trend_strength": trend_info["strength"],
        "spike_count_recent": len(spikes),
        "recent_spikes": [
            {
                "rvol": s.rvol,
                "direction": s.direction,
                "significance": s.significance,
            }
            for s in spikes[:3]  # Top 3 recent
        ],
        "accumulation_signal": accum_signal,
        "breakout_volume_ready": breakout_ready,
    }


def attach_volume_confirmation(
    df: pl.DataFrame,
    period: int = None,
) -> pl.DataFrame:
    """Attach volume confirmation columns to DataFrame.

    Adds columns:
        - rvol: float
        - rvol_label: str
        - volume_avg: float
        - volume_spike: bool (is current bar a spike?)
        - breakout_vol_ready: bool
    """
    period = period or VOLUME_SETTINGS["rvol_period"]
    threshold = VOLUME_SETTINGS["spike_threshold"]
    min_breakout = VOLUME_SETTINGS["breakout_min_rvol"]

    # Add RVOL
    df = compute_rvol(df, period=period)

    # Add spike detection
    df = df.with_columns([
        (pl.col("rvol") >= threshold).alias("volume_spike"),
        (pl.col("rvol") >= min_breakout).alias("breakout_vol_ready"),
    ])

    return df


# ---------------------------------------------------------------------------
# Breakout Validation Helper
# ---------------------------------------------------------------------------
def validate_breakout_volume(
    df: pl.DataFrame,
    breakout_bar_index: int = -1,
) -> dict:
    """Validate if a breakout has sufficient volume confirmation.

    Parameters
    ----------
    df : pl.DataFrame
        Price data with volume
    breakout_bar_index : int
        Index of the breakout bar (-1 for latest)

    Returns
    -------
    dict with:
        - is_valid: bool
        - rvol: float
        - verdict: str
        - score_adjustment: int (-2 to +2)

    """
    if "rvol" not in df.columns:
        df = compute_rvol(df)

    rvols = df["rvol"].to_list()
    rvol = rvols[breakout_bar_index]

    if rvol is None:
        return {
            "is_valid": False,
            "rvol": None,
            "verdict": "No volume data",
            "score_adjustment": -1,
        }

    # Thresholds
    min_valid = VOLUME_SETTINGS["breakout_min_rvol"]

    if rvol >= 2.5:
        return {
            "is_valid": True,
            "rvol": round(rvol, 2),
            "verdict": "Excellent volume confirmation",
            "score_adjustment": +2,
        }
    if rvol >= min_valid:
        return {
            "is_valid": True,
            "rvol": round(rvol, 2),
            "verdict": "Good volume confirmation",
            "score_adjustment": +1,
        }
    if rvol >= 1.0:
        return {
            "is_valid": False,
            "rvol": round(rvol, 2),
            "verdict": "Weak volume - possible fake breakout",
            "score_adjustment": -1,
        }
    return {
        "is_valid": False,
        "rvol": round(rvol, 2),
        "verdict": "Low volume - likely fake breakout",
        "score_adjustment": -2,
    }


# ---------------------------------------------------------------------------
# Registry Export (for auto-discovery)
# ---------------------------------------------------------------------------
EXPORTS = {
    "rvol": compute_rvol,
    "volume_spike": detect_volume_spike,
    "volume_trend": compute_volume_trend,
    "volume_confirmation": summarize_volume_confirmation,
    "volume_attach": attach_volume_confirmation,
    "validate_breakout_volume": validate_breakout_volume,
}

NAME = "volume_confirmation"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    # Create sample data
    np.random.seed(42)
    n = 100

    # Base volume with some spikes
    base_volume = 10000
    volumes = []
    for i in range(n):
        if i in [25, 50, 75, 95]:  # Spike bars
            volumes.append(base_volume * np.random.uniform(2.5, 4.0))
        else:
            volumes.append(base_volume * np.random.uniform(0.7, 1.3))

    # Price data
    prices = [100.0]
    for i in range(1, n):
        change = np.random.uniform(-1, 1)
        if i in [25, 50, 75, 95]:  # Big moves on spike bars
            change = np.random.uniform(1, 3) * (1 if np.random.random() > 0.5 else -1)
        prices.append(prices[-1] + change)

    df = pl.DataFrame({
        "timestamp": list(range(n)),
        "open": prices,
        "high": [p + np.random.uniform(0.5, 1.5) for p in prices],
        "low": [p - np.random.uniform(0.5, 1.5) for p in prices],
        "close": [p + np.random.uniform(-0.3, 0.3) for p in prices],
        "volume": volumes,
    })

    # Test RVOL
    df = compute_rvol(df)
    print("RVOL Column Added:")
    print(df.select(["timestamp", "volume", "rvol", "rvol_label"]).tail(10))

    # Test spike detection
    spikes = detect_volume_spike(df)
    print(f"\nVolume Spikes Found: {len(spikes)}")
    for spike in spikes[:5]:
        print(f"  Bar {spike.bar_index}: RVOL={spike.rvol}, Direction={spike.direction}")

    # Test summary
    summary = summarize_volume_confirmation(df)
    print("\nSummary:")
    print(f"  Current RVOL: {summary['display_value']}")
    print(f"  Label: {summary['rvol_label']}")
    print(f"  Trend: {summary['volume_trend']}")
    print(f"  Accumulation: {summary['accumulation_signal']}")
    print(f"  Breakout Ready: {summary['breakout_volume_ready']}")

    # Test breakout validation
    validation = validate_breakout_volume(df)
    print("\nBreakout Validation:")
    print(f"  Valid: {validation['is_valid']}")
    print(f"  Verdict: {validation['verdict']}")
    print(f"  Score Adjustment: {validation['score_adjustment']}")
