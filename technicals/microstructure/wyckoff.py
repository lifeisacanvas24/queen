# queen/technicals/microstructure/wyckoff.py
"""
Wyckoff Pattern Detection Module
================================
Detects key Wyckoff patterns that signal potential reversals and continuations.

Patterns Detected:
- Spring: False breakdown below support with immediate reversal (bullish)
- Upthrust: False breakout above resistance with immediate reversal (bearish)
- Selling Climax: High volume, wide range, close off lows (end of downtrend)
- Buying Climax: High volume, wide range, close off highs (end of uptrend)
- Sign of Strength (SOS): Strong move up on increasing volume
- Sign of Weakness (SOW): Strong move down on increasing volume

Usage:
    from queen.technicals.microstructure.wyckoff import (
        detect_spring,
        detect_upthrust,
        detect_selling_climax,
        detect_buying_climax,
        analyze_wyckoff,
    )

    result = analyze_wyckoff(df)
    if result.spring_detected:
        print("Bullish Spring detected - potential long entry!")

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
try:
    from queen.settings.breakout_settings import WYCKOFF_SETTINGS
except ImportError:
    WYCKOFF_SETTINGS = {
        "spring_wick_min_atr": 0.3,
        "spring_close_above": True,
        "upthrust_wick_min_atr": 0.3,
        "upthrust_close_below": True,
        "climax_volume_multiple": 2.5,
        "climax_range_atr_ratio": 1.5,
        "climax_close_off_extreme": 0.3,
        "accumulation_min_bars": 20,
        "distribution_min_bars": 20,
        "sos_volume_increase": 1.5,
        "sow_volume_increase": 1.5,
    }


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class WyckoffPhase(str, Enum):
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"


class WyckoffSignalType(str, Enum):
    SPRING = "spring"
    UPTHRUST = "upthrust"
    SELLING_CLIMAX = "selling_climax"
    BUYING_CLIMAX = "buying_climax"
    SOS = "sign_of_strength"
    SOW = "sign_of_weakness"
    AUTOMATIC_RALLY = "automatic_rally"
    SECONDARY_TEST = "secondary_test"


@dataclass
class WyckoffSignal:
    """Represents a Wyckoff pattern signal."""
    signal_type: WyckoffSignalType
    direction: Literal["bullish", "bearish"]
    level: float
    bar_index: int
    volume_confirmation: bool
    strength: float  # 0-100
    timestamp: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def __repr__(self) -> str:
        vol = "✓vol" if self.volume_confirmation else ""
        return f"Wyckoff({self.signal_type.value}, {self.direction}, str={self.strength:.0f} {vol})"


@dataclass
class WyckoffResult:
    """Complete Wyckoff analysis result."""
    signals: List[WyckoffSignal]
    spring_detected: bool
    upthrust_detected: bool
    climax_detected: bool
    sos_detected: bool
    sow_detected: bool
    estimated_phase: WyckoffPhase
    primary_signal: Optional[WyckoffSignal]
    bias: Literal["bullish", "bearish", "neutral"]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _get_swing_points(df: pl.DataFrame, lookback: int = 20):
    """Get swing points."""
    if _USE_SHARED_SWING:
        try:
            points = find_swing_points(df, max_points=lookback)
            highs = [{"price": p.price, "index": p.bar_index} for p in points if p.type == SwingType.HIGH]
            lows = [{"price": p.price, "index": p.bar_index} for p in points if p.type == SwingType.LOW]
            return highs, lows
        except Exception:
            pass

    n = df.height
    if n < 3:
        return [], []

    high_list = df["high"].to_list()
    low_list = df["low"].to_list()

    highs, lows = [], []
    start = max(1, n - lookback)

    for i in range(start, n - 1):
        if high_list[i] > high_list[i-1] and high_list[i] > high_list[i+1]:
            highs.append({"price": high_list[i], "index": i})
        if low_list[i] < low_list[i-1] and low_list[i] < low_list[i+1]:
            lows.append({"price": low_list[i], "index": i})

    return highs, lows


def _calculate_atr(df: pl.DataFrame, period: int = 14) -> float:
    """Get latest ATR value."""
    if _USE_EXISTING_ATR:
        try:
            atr_arr = atr_wilder(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), period)
            for v in reversed(atr_arr):
                if v is not None and v == v:
                    return float(v)
        except Exception:
            pass

    df_atr = df.with_columns([
        pl.max_horizontal(
            (pl.col("high") - pl.col("low")).abs(),
            (pl.col("high") - pl.col("close").shift(1)).abs(),
            (pl.col("low") - pl.col("close").shift(1)).abs(),
        ).rolling_mean(window_size=period).alias("_atr")
    ])

    for v in reversed(df_atr["_atr"].to_list()):
        if v is not None:
            return v
    return 1.0


def _get_avg_volume(df: pl.DataFrame, period: int = 20) -> float:
    """Get average volume."""
    if "volume" not in df.columns:
        return 0.0
    vol = df["volume"].tail(period).mean()
    return float(vol) if vol is not None else 0.0


# ---------------------------------------------------------------------------
# Detection Functions
# ---------------------------------------------------------------------------
def detect_spring(df: pl.DataFrame, lookback: int = 20) -> Optional[WyckoffSignal]:
    """
    Detect Spring pattern - false breakdown below support.

    A Spring occurs when:
    1. Price breaks below a swing low (support)
    2. The wick extends significantly below
    3. Price closes back above the support
    4. Often accompanied by decreasing volume on break, increasing on reversal
    """
    if df is None or df.is_empty() or df.height < 5:
        return None

    swing_highs, swing_lows = _get_swing_points(df, lookback)
    if not swing_lows:
        return None

    atr = _calculate_atr(df)
    min_wick = WYCKOFF_SETTINGS["spring_wick_min_atr"]
    need_close_above = WYCKOFF_SETTINGS["spring_close_above"]

    n = df.height
    last_high = float(df["high"].tail(1).item())
    last_low = float(df["low"].tail(1).item())
    last_close = float(df["close"].tail(1).item())
    last_open = float(df["open"].tail(1).item())

    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None
    volumes = df["volume"].to_list() if "volume" in df.columns else None
    avg_vol = _get_avg_volume(df)

    for sl in swing_lows:
        support = sl["price"]

        # Check if wick went below support
        if last_low < support:
            wick_below = support - last_low

            if wick_below >= min_wick * atr:
                # Check if closed above
                close_above = last_close > support if need_close_above else True
                body_above = min(last_open, last_close) > support

                if close_above and body_above:
                    # Volume confirmation
                    vol_confirm = False
                    if volumes and avg_vol > 0:
                        vol_confirm = volumes[-1] >= avg_vol * 0.8

                    strength = 60
                    if vol_confirm:
                        strength += 20
                    if wick_below >= min_wick * atr * 2:
                        strength += 10

                    return WyckoffSignal(
                        signal_type=WyckoffSignalType.SPRING,
                        direction="bullish",
                        level=support,
                        bar_index=n - 1,
                        volume_confirmation=vol_confirm,
                        strength=min(100, strength),
                        timestamp=timestamps[-1] if timestamps else None,
                        details={
                            "support_level": round(support, 2),
                            "wick_low": round(last_low, 2),
                            "wick_depth": round(wick_below, 2),
                            "close": round(last_close, 2),
                        }
                    )

    return None


def detect_upthrust(df: pl.DataFrame, lookback: int = 20) -> Optional[WyckoffSignal]:
    """
    Detect Upthrust pattern - false breakout above resistance.

    An Upthrust occurs when:
    1. Price breaks above a swing high (resistance)
    2. The wick extends significantly above
    3. Price closes back below the resistance
    4. Often accompanied by high volume followed by rejection
    """
    if df is None or df.is_empty() or df.height < 5:
        return None

    swing_highs, swing_lows = _get_swing_points(df, lookback)
    if not swing_highs:
        return None

    atr = _calculate_atr(df)
    min_wick = WYCKOFF_SETTINGS["upthrust_wick_min_atr"]
    need_close_below = WYCKOFF_SETTINGS["upthrust_close_below"]

    n = df.height
    last_high = float(df["high"].tail(1).item())
    last_low = float(df["low"].tail(1).item())
    last_close = float(df["close"].tail(1).item())
    last_open = float(df["open"].tail(1).item())

    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None
    volumes = df["volume"].to_list() if "volume" in df.columns else None
    avg_vol = _get_avg_volume(df)

    for sh in swing_highs:
        resistance = sh["price"]

        if last_high > resistance:
            wick_above = last_high - resistance

            if wick_above >= min_wick * atr:
                close_below = last_close < resistance if need_close_below else True
                body_below = max(last_open, last_close) < resistance

                if close_below and body_below:
                    vol_confirm = False
                    if volumes and avg_vol > 0:
                        vol_confirm = volumes[-1] >= avg_vol * 1.2

                    strength = 60
                    if vol_confirm:
                        strength += 20
                    if wick_above >= min_wick * atr * 2:
                        strength += 10

                    return WyckoffSignal(
                        signal_type=WyckoffSignalType.UPTHRUST,
                        direction="bearish",
                        level=resistance,
                        bar_index=n - 1,
                        volume_confirmation=vol_confirm,
                        strength=min(100, strength),
                        timestamp=timestamps[-1] if timestamps else None,
                        details={
                            "resistance_level": round(resistance, 2),
                            "wick_high": round(last_high, 2),
                            "wick_depth": round(wick_above, 2),
                            "close": round(last_close, 2),
                        }
                    )

    return None


def detect_selling_climax(df: pl.DataFrame, lookback: int = 10) -> Optional[WyckoffSignal]:
    """
    Detect Selling Climax - exhaustion of selling pressure.

    Characteristics:
    1. High volume (> 2.5x average)
    2. Wide range bar (> 1.5x ATR)
    3. Close in upper portion of bar (> 30% off low)
    """
    if df is None or df.is_empty() or df.height < lookback:
        return None

    if "volume" not in df.columns:
        return None

    atr = _calculate_atr(df)
    vol_mult = WYCKOFF_SETTINGS["climax_volume_multiple"]
    range_ratio = WYCKOFF_SETTINGS["climax_range_atr_ratio"]
    close_off = WYCKOFF_SETTINGS["climax_close_off_extreme"]

    avg_vol = _get_avg_volume(df)

    n = df.height
    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None

    # Check recent bars
    for i in range(n - lookback, n):
        h = float(df["high"][i])
        l = float(df["low"][i])
        c = float(df["close"][i])
        v = float(df["volume"][i])

        bar_range = h - l

        # High volume?
        if avg_vol > 0 and v >= avg_vol * vol_mult:
            # Wide range?
            if bar_range >= range_ratio * atr:
                # Close in upper portion?
                if bar_range > 0:
                    close_position = (c - l) / bar_range
                    if close_position >= close_off:
                        strength = 70
                        if v >= avg_vol * 3:
                            strength += 15
                        if close_position >= 0.5:
                            strength += 10

                        return WyckoffSignal(
                            signal_type=WyckoffSignalType.SELLING_CLIMAX,
                            direction="bullish",
                            level=l,
                            bar_index=i,
                            volume_confirmation=True,
                            strength=min(100, strength),
                            timestamp=timestamps[i] if timestamps else None,
                            details={
                                "volume_ratio": round(v / avg_vol, 2),
                                "range_atr_ratio": round(bar_range / atr, 2),
                                "close_position": round(close_position, 2),
                            }
                        )

    return None


def detect_buying_climax(df: pl.DataFrame, lookback: int = 10) -> Optional[WyckoffSignal]:
    """
    Detect Buying Climax - exhaustion of buying pressure.

    Characteristics:
    1. High volume (> 2.5x average)
    2. Wide range bar (> 1.5x ATR)
    3. Close in lower portion of bar (< 30% from high)
    """
    if df is None or df.is_empty() or df.height < lookback:
        return None

    if "volume" not in df.columns:
        return None

    atr = _calculate_atr(df)
    vol_mult = WYCKOFF_SETTINGS["climax_volume_multiple"]
    range_ratio = WYCKOFF_SETTINGS["climax_range_atr_ratio"]
    close_off = WYCKOFF_SETTINGS["climax_close_off_extreme"]

    avg_vol = _get_avg_volume(df)

    n = df.height
    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None

    for i in range(n - lookback, n):
        h = float(df["high"][i])
        l = float(df["low"][i])
        c = float(df["close"][i])
        v = float(df["volume"][i])

        bar_range = h - l

        if avg_vol > 0 and v >= avg_vol * vol_mult:
            if bar_range >= range_ratio * atr:
                if bar_range > 0:
                    close_position = (h - c) / bar_range  # Distance from high
                    if close_position >= close_off:
                        strength = 70
                        if v >= avg_vol * 3:
                            strength += 15
                        if close_position >= 0.5:
                            strength += 10

                        return WyckoffSignal(
                            signal_type=WyckoffSignalType.BUYING_CLIMAX,
                            direction="bearish",
                            level=h,
                            bar_index=i,
                            volume_confirmation=True,
                            strength=min(100, strength),
                            timestamp=timestamps[i] if timestamps else None,
                            details={
                                "volume_ratio": round(v / avg_vol, 2),
                                "range_atr_ratio": round(bar_range / atr, 2),
                                "close_position": round(1 - close_position, 2),
                            }
                        )

    return None


def analyze_wyckoff(df: pl.DataFrame) -> WyckoffResult:
    """Complete Wyckoff analysis."""
    if df is None or df.is_empty() or df.height < 10:
        return WyckoffResult(
            signals=[], spring_detected=False, upthrust_detected=False,
            climax_detected=False, sos_detected=False, sow_detected=False,
            estimated_phase=WyckoffPhase.UNKNOWN, primary_signal=None, bias="neutral",
        )

    signals = []

    spring = detect_spring(df)
    if spring:
        signals.append(spring)

    upthrust = detect_upthrust(df)
    if upthrust:
        signals.append(upthrust)

    selling_climax = detect_selling_climax(df)
    if selling_climax:
        signals.append(selling_climax)

    buying_climax = detect_buying_climax(df)
    if buying_climax:
        signals.append(buying_climax)

    spring_detected = spring is not None
    upthrust_detected = upthrust is not None
    climax_detected = selling_climax is not None or buying_climax is not None

    # Estimate phase
    if spring_detected or selling_climax is not None:
        estimated_phase = WyckoffPhase.ACCUMULATION
    elif upthrust_detected or buying_climax is not None:
        estimated_phase = WyckoffPhase.DISTRIBUTION
    else:
        estimated_phase = WyckoffPhase.UNKNOWN

    primary_signal = max(signals, key=lambda x: x.strength) if signals else None

    bullish_count = sum(1 for s in signals if s.direction == "bullish")
    bearish_count = sum(1 for s in signals if s.direction == "bearish")

    if bullish_count > bearish_count:
        bias = "bullish"
    elif bearish_count > bullish_count:
        bias = "bearish"
    else:
        bias = "neutral"

    return WyckoffResult(
        signals=signals,
        spring_detected=spring_detected,
        upthrust_detected=upthrust_detected,
        climax_detected=climax_detected,
        sos_detected=False,  # TODO: implement
        sow_detected=False,  # TODO: implement
        estimated_phase=estimated_phase,
        primary_signal=primary_signal,
        bias=bias,
    )


def summarize_wyckoff(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary dict for signal cards."""
    result = analyze_wyckoff(df)

    return {
        "spring_detected": result.spring_detected,
        "upthrust_detected": result.upthrust_detected,
        "climax_detected": result.climax_detected,
        "wyckoff_phase": result.estimated_phase.value,
        "wyckoff_bias": result.bias,
        "signal_count": len(result.signals),
        "primary_signal": result.primary_signal.signal_type.value if result.primary_signal else None,
        "primary_strength": result.primary_signal.strength if result.primary_signal else None,
    }


# ---------------------------------------------------------------------------
# Automatic Rally / Secondary Test Detection
# ---------------------------------------------------------------------------
def detect_automatic_rally(df: pl.DataFrame, lookback: int = 30) -> Optional[WyckoffSignal]:
    """
    Detect Automatic Rally (AR) - sharp bounce after Selling Climax.

    Characteristics:
    1. Follows a selling climax or significant low
    2. Strong upward move (> 1.5x ATR)
    3. Often on diminishing volume
    4. Marks the top of the initial trading range

    AR sets the upper boundary of the accumulation range.
    """
    if df is None or df.is_empty() or df.height < lookback:
        return None

    atr = _calculate_atr(df)
    n = df.height
    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None

    # Look for selling climax first
    selling_climax = detect_selling_climax(df, lookback=10)
    if not selling_climax:
        return None

    climax_bar = selling_climax.bar_index

    # Check bars after climax for rally
    if climax_bar + 3 >= n:
        return None

    climax_low = float(df["low"][climax_bar])

    # Find the rally high after climax
    rally_high = climax_low
    rally_bar = climax_bar

    for i in range(climax_bar + 1, min(climax_bar + 10, n)):
        h = float(df["high"][i])
        if h > rally_high:
            rally_high = h
            rally_bar = i

    rally_size = rally_high - climax_low

    # AR should be significant (> 1.5x ATR)
    if rally_size < atr * 1.5:
        return None

    # Check volume diminishing (optional but confirms AR)
    vol_confirm = True
    if "volume" in df.columns:
        climax_vol = float(df["volume"][climax_bar])
        rally_vol = float(df["volume"][rally_bar])
        vol_confirm = rally_vol < climax_vol * 0.8

    strength = 65
    if rally_size >= atr * 2.5:
        strength += 15
    if vol_confirm:
        strength += 10

    return WyckoffSignal(
        signal_type=WyckoffSignalType.AUTOMATIC_RALLY,
        direction="bullish",
        level=rally_high,
        bar_index=rally_bar,
        volume_confirmation=vol_confirm,
        strength=min(100, strength),
        timestamp=timestamps[rally_bar] if timestamps else None,
        details={
            "climax_low": round(climax_low, 2),
            "rally_high": round(rally_high, 2),
            "rally_size": round(rally_size, 2),
            "rally_atr_ratio": round(rally_size / atr, 2),
        }
    )


def detect_secondary_test(df: pl.DataFrame, lookback: int = 30) -> Optional[WyckoffSignal]:
    """
    Detect Secondary Test (ST) - retest of the selling climax low.

    Characteristics:
    1. Price returns to test the selling climax area
    2. Lower volume than the selling climax
    3. Smaller price range than climax
    4. Often doesn't make a new low (or only slightly)

    ST confirms demand is overcoming supply - bullish.
    """
    if df is None or df.is_empty() or df.height < lookback:
        return None

    atr = _calculate_atr(df)
    avg_vol = _get_avg_volume(df)
    n = df.height
    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None

    # Need selling climax first
    selling_climax = detect_selling_climax(df, lookback=20)
    if not selling_climax:
        return None

    climax_bar = selling_climax.bar_index
    climax_low = float(df["low"][climax_bar])
    climax_vol = float(df["volume"][climax_bar]) if "volume" in df.columns else 0
    climax_range = float(df["high"][climax_bar]) - climax_low

    # Look for ST in bars after AR (skip a few bars)
    start_search = climax_bar + 5
    if start_search >= n:
        return None

    for i in range(start_search, n):
        l = float(df["low"][i])
        h = float(df["high"][i])
        c = float(df["close"][i])
        bar_range = h - l

        # Price should be near the climax low (within 0.5% or 0.5 ATR)
        tolerance = max(climax_low * 0.005, atr * 0.5)

        if l <= climax_low + tolerance:
            # Check volume is lower
            vol_confirm = True
            if "volume" in df.columns and climax_vol > 0:
                st_vol = float(df["volume"][i])
                vol_confirm = st_vol < climax_vol * 0.7

            # Check range is smaller
            range_confirm = bar_range < climax_range * 0.8 if climax_range > 0 else True

            # Check close is above low (showing buying)
            close_confirm = (c - l) / bar_range > 0.4 if bar_range > 0 else True

            if vol_confirm and (range_confirm or close_confirm):
                strength = 60
                if vol_confirm:
                    strength += 15
                if range_confirm:
                    strength += 10
                if l > climax_low:  # Didn't make new low = stronger
                    strength += 10

                return WyckoffSignal(
                    signal_type=WyckoffSignalType.SECONDARY_TEST,
                    direction="bullish",
                    level=l,
                    bar_index=i,
                    volume_confirmation=vol_confirm,
                    strength=min(100, strength),
                    timestamp=timestamps[i] if timestamps else None,
                    details={
                        "climax_low": round(climax_low, 2),
                        "test_low": round(l, 2),
                        "made_new_low": l < climax_low,
                        "volume_ratio": round(float(df["volume"][i]) / climax_vol, 2) if climax_vol > 0 and "volume" in df.columns else None,
                    }
                )

    return None


# ---------------------------------------------------------------------------
# SOS / SOW Detection (Sign of Strength / Sign of Weakness)
# ---------------------------------------------------------------------------
def detect_sos(df: pl.DataFrame, lookback: int = 20) -> Optional[WyckoffSignal]:
    """
    Detect Sign of Strength (SOS) - strong move up confirming accumulation.

    Characteristics:
    1. Strong bullish bar (close near high)
    2. Increasing volume (> 1.5x average)
    3. Breaks above recent resistance
    4. Often follows a Spring
    """
    if df is None or df.is_empty() or df.height < lookback:
        return None

    if "volume" not in df.columns:
        return None

    vol_increase = WYCKOFF_SETTINGS["sos_volume_increase"]
    avg_vol = _get_avg_volume(df)

    n = df.height
    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None

    # Check last few bars for SOS
    for i in range(n - 5, n):
        if i < 0:
            continue

        h = float(df["high"][i])
        l = float(df["low"][i])
        o = float(df["open"][i])
        c = float(df["close"][i])
        v = float(df["volume"][i])

        bar_range = h - l
        if bar_range <= 0:
            continue

        # Bullish bar (close in upper 70%)
        close_position = (c - l) / bar_range
        if close_position < 0.7:
            continue

        # Volume confirmation
        if avg_vol > 0 and v < avg_vol * vol_increase:
            continue

        # Check if breaking above recent highs
        recent_highs = df["high"].to_list()[max(0, i-lookback):i]
        if recent_highs and h > max(recent_highs) * 0.998:
            strength = 65
            if v >= avg_vol * 2:
                strength += 15
            if close_position >= 0.85:
                strength += 10

            return WyckoffSignal(
                signal_type=WyckoffSignalType.SOS,
                direction="bullish",
                level=h,
                bar_index=i,
                volume_confirmation=True,
                strength=min(100, strength),
                timestamp=timestamps[i] if timestamps else None,
                details={
                    "close_position": round(close_position, 2),
                    "volume_ratio": round(v / avg_vol, 2) if avg_vol > 0 else 0,
                    "high": round(h, 2),
                }
            )

    return None


def detect_sow(df: pl.DataFrame, lookback: int = 20) -> Optional[WyckoffSignal]:
    """
    Detect Sign of Weakness (SOW) - strong move down confirming distribution.

    Characteristics:
    1. Strong bearish bar (close near low)
    2. Increasing volume (> 1.5x average)
    3. Breaks below recent support
    4. Often follows an Upthrust
    """
    if df is None or df.is_empty() or df.height < lookback:
        return None

    if "volume" not in df.columns:
        return None

    vol_increase = WYCKOFF_SETTINGS["sow_volume_increase"]
    avg_vol = _get_avg_volume(df)

    n = df.height
    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None

    for i in range(n - 5, n):
        if i < 0:
            continue

        h = float(df["high"][i])
        l = float(df["low"][i])
        o = float(df["open"][i])
        c = float(df["close"][i])
        v = float(df["volume"][i])

        bar_range = h - l
        if bar_range <= 0:
            continue

        # Bearish bar (close in lower 30%)
        close_position = (c - l) / bar_range
        if close_position > 0.3:
            continue

        # Volume confirmation
        if avg_vol > 0 and v < avg_vol * vol_increase:
            continue

        # Check if breaking below recent lows
        recent_lows = df["low"].to_list()[max(0, i-lookback):i]
        if recent_lows and l < min(recent_lows) * 1.002:
            strength = 65
            if v >= avg_vol * 2:
                strength += 15
            if close_position <= 0.15:
                strength += 10

            return WyckoffSignal(
                signal_type=WyckoffSignalType.SOW,
                direction="bearish",
                level=l,
                bar_index=i,
                volume_confirmation=True,
                strength=min(100, strength),
                timestamp=timestamps[i] if timestamps else None,
                details={
                    "close_position": round(close_position, 2),
                    "volume_ratio": round(v / avg_vol, 2) if avg_vol > 0 else 0,
                    "low": round(l, 2),
                }
            )

    return None


def identify_wyckoff_phase(df: pl.DataFrame, lookback: int = 50) -> WyckoffPhase:
    """
    Identify the current Wyckoff market phase.

    Phases:
    - ACCUMULATION: After downtrend, building base, smart money buying
    - MARKUP: Uptrend after accumulation
    - DISTRIBUTION: After uptrend, smart money selling
    - MARKDOWN: Downtrend after distribution

    Uses multiple signals to determine phase.
    """
    if df is None or df.is_empty() or df.height < lookback:
        return WyckoffPhase.UNKNOWN

    # Calculate trend
    closes = df["close"].to_list()
    first_half_avg = sum(closes[:lookback//2]) / (lookback//2) if lookback >= 2 else closes[0]
    second_half_avg = sum(closes[lookback//2:]) / (lookback//2) if lookback >= 2 else closes[-1]

    trend_pct = (second_half_avg - first_half_avg) / first_half_avg if first_half_avg > 0 else 0

    # Check for Wyckoff signals
    spring = detect_spring(df)
    upthrust = detect_upthrust(df)
    selling_climax = detect_selling_climax(df)
    buying_climax = detect_buying_climax(df)
    sos = detect_sos(df)
    sow = detect_sow(df)

    # Score each phase
    accumulation_score = 0
    distribution_score = 0

    if spring:
        accumulation_score += 30
    if selling_climax:
        accumulation_score += 25
    if sos:
        accumulation_score += 20

    if upthrust:
        distribution_score += 30
    if buying_climax:
        distribution_score += 25
    if sow:
        distribution_score += 20

    # Trend influence
    if trend_pct < -0.02:  # Downtrend
        if accumulation_score > distribution_score:
            return WyckoffPhase.ACCUMULATION
        return WyckoffPhase.MARKDOWN
    elif trend_pct > 0.02:  # Uptrend
        if distribution_score > accumulation_score:
            return WyckoffPhase.DISTRIBUTION
        return WyckoffPhase.MARKUP
    else:  # Sideways
        if accumulation_score > distribution_score:
            return WyckoffPhase.ACCUMULATION
        elif distribution_score > accumulation_score:
            return WyckoffPhase.DISTRIBUTION
        return WyckoffPhase.UNKNOWN


# ---------------------------------------------------------------------------
# Updated Analysis Function
# ---------------------------------------------------------------------------
def analyze_wyckoff_full(df: pl.DataFrame) -> WyckoffResult:
    """Complete Wyckoff analysis including all signals and phase."""
    if df is None or df.is_empty() or df.height < 10:
        return WyckoffResult(
            signals=[], spring_detected=False, upthrust_detected=False,
            climax_detected=False, sos_detected=False, sow_detected=False,
            estimated_phase=WyckoffPhase.UNKNOWN, primary_signal=None, bias="neutral",
        )

    signals = []

    spring = detect_spring(df)
    if spring:
        signals.append(spring)

    upthrust = detect_upthrust(df)
    if upthrust:
        signals.append(upthrust)

    selling_climax = detect_selling_climax(df)
    if selling_climax:
        signals.append(selling_climax)

    buying_climax = detect_buying_climax(df)
    if buying_climax:
        signals.append(buying_climax)

    sos = detect_sos(df)
    if sos:
        signals.append(sos)

    sow = detect_sow(df)
    if sow:
        signals.append(sow)

    # New: Automatic Rally and Secondary Test
    ar = detect_automatic_rally(df)
    if ar:
        signals.append(ar)

    st = detect_secondary_test(df)
    if st:
        signals.append(st)

    # Identify phase
    estimated_phase = identify_wyckoff_phase(df)

    # Determine bias
    bullish_count = sum(1 for s in signals if s.direction == "bullish")
    bearish_count = sum(1 for s in signals if s.direction == "bearish")

    if bullish_count > bearish_count:
        bias = "bullish"
    elif bearish_count > bullish_count:
        bias = "bearish"
    else:
        bias = "neutral"

    primary_signal = max(signals, key=lambda x: x.strength) if signals else None

    return WyckoffResult(
        signals=signals,
        spring_detected=spring is not None,
        upthrust_detected=upthrust is not None,
        climax_detected=selling_climax is not None or buying_climax is not None,
        sos_detected=sos is not None,
        sow_detected=sow is not None,
        estimated_phase=estimated_phase,
        primary_signal=primary_signal,
        bias=bias,
    )


# Override the basic analyze_wyckoff with full version
analyze_wyckoff = analyze_wyckoff_full


def summarize_wyckoff(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary dict for signal cards."""
    result = analyze_wyckoff(df)

    return {
        "spring_detected": result.spring_detected,
        "upthrust_detected": result.upthrust_detected,
        "climax_detected": result.climax_detected,
        "sos_detected": result.sos_detected,
        "sow_detected": result.sow_detected,
        "wyckoff_phase": result.estimated_phase.value,
        "wyckoff_bias": result.bias,
        "signal_count": len(result.signals),
        "primary_signal": result.primary_signal.signal_type.value if result.primary_signal else None,
        "primary_strength": result.primary_signal.strength if result.primary_signal else None,
    }


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "spring": detect_spring,
    "upthrust": detect_upthrust,
    "selling_climax": detect_selling_climax,
    "buying_climax": detect_buying_climax,
    "sos": detect_sos,
    "sow": detect_sow,
    "automatic_rally": detect_automatic_rally,
    "secondary_test": detect_secondary_test,
    "wyckoff_phase": identify_wyckoff_phase,
    "wyckoff_analysis": analyze_wyckoff,
    "wyckoff_summary": summarize_wyckoff,
}

NAME = "wyckoff"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("WYCKOFF TEST")
    print("=" * 60)
    print(f"Using shared swing helper: {_USE_SHARED_SWING}")

    np.random.seed(42)
    n = 50

    # Create Spring pattern
    prices = [100.0]
    for i in range(1, n):
        if i < 30:
            change = np.random.uniform(-0.3, 0.3)
        elif i == 30:
            change = -2.0  # Break down
        elif i == 31:
            change = 2.5   # Spring reversal
        else:
            change = np.random.uniform(0.0, 0.5)
        prices.append(prices[-1] + change)

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.5, 1.5) for p in prices],
        "low": [p - np.random.uniform(0.5, 1.5) for p in prices],
        "close": [prices[i] + np.random.uniform(-0.3, 0.3) for i in range(n)],
        "volume": [10000 * (3 if i in [30, 31] else 1) + np.random.randint(-2000, 2000) for i in range(n)],
    })

    result = analyze_wyckoff(df)

    print(f"\n📊 WYCKOFF ANALYSIS:")
    print(f"   Spring Detected: {result.spring_detected}")
    print(f"   Upthrust Detected: {result.upthrust_detected}")
    print(f"   Climax Detected: {result.climax_detected}")
    print(f"   Estimated Phase: {result.estimated_phase.value}")
    print(f"   Bias: {result.bias}")

    print(f"\n📊 SIGNALS: {len(result.signals)}")
    for sig in result.signals:
        print(f"   {sig}")

    print(f"\n📊 SUMMARY:")
    summary = summarize_wyckoff(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ Wyckoff test complete!")
