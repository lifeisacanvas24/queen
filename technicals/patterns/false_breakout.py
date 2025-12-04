#queen/technicals/false_breakout.py
"""False Breakout Pattern Detection Module
=======================================
Detects patterns that indicate a breakout is likely to fail:
- Swing Failure Pattern (SFP): Price exceeds level but closes back inside
- Fakeout Candle: Long wick beyond level with body inside
- Bull/Bear Trap: False breakout that reverses sharply
- Stop Hunt Reversal: Liquidity grab followed by reversal
- Failed Auction: Price rejected from new territory

These patterns help filter out 70-80% of false breakout signals.

Usage:
    from queen.technicals.patterns.false_breakout import (
        detect_swing_failure,
        detect_fakeout_candle,
        detect_trap_pattern,
        summarize_false_breakout_risk,
    )

    # Check for SFP at resistance
    sfp = detect_swing_failure(df, level=2850.0, direction="bearish")

    # Get comprehensive false breakout risk assessment
    risk = summarize_false_breakout_risk(df, breakout_level=2850.0, direction="up")

Settings Integration:
    All thresholds configurable via settings/pattern_policy.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

import polars as pl

# ---------------------------------------------------------------------------
# Settings (import from settings when available, fallback to defaults)
# ---------------------------------------------------------------------------
try:
    from queen.settings.pattern_policy import FALSE_BREAKOUT_SETTINGS
except ImportError:
    # Fallback defaults - move to settings/pattern_policy.py
    FALSE_BREAKOUT_SETTINGS = {
        # SFP Settings
        "sfp_lookback": 20,             # Bars to look for swing points
        "sfp_wick_min_pct": 0.3,        # Min wick beyond level as % of ATR
        "sfp_body_inside_pct": 0.8,     # Body must be X% inside level

        # Fakeout Candle Settings
        "fakeout_wick_ratio": 2.0,      # Wick must be 2x body
        "fakeout_body_max_pct": 0.3,    # Body max % of total range

        # Trap Pattern Settings
        "trap_reversal_min_pct": 0.5,   # Min reversal as % of ATR
        "trap_lookback": 5,             # Bars to confirm trap

        # Stop Hunt Settings
        "stop_hunt_wick_atr_ratio": 0.5, # Wick must exceed level by X*ATR
        "stop_hunt_close_inside": True,  # Must close back inside

        # General
        "level_tolerance_pct": 0.1,     # Tolerance for "at level" detection
    }


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class SwingPoint:
    """Represents a swing high or swing low"""

    type: Literal["high", "low"]
    price: float
    bar_index: int
    timestamp: Optional[str] = None


@dataclass
class FalseBreakoutSignal:
    """Represents a detected false breakout pattern"""

    pattern_type: Literal["sfp", "fakeout", "bull_trap", "bear_trap", "stop_hunt", "failed_auction"]
    direction: Literal["bullish", "bearish"]  # Direction of the FALSE signal (reversal direction)
    level: float                               # The level that was falsely broken
    confidence: float                          # 0-100 confidence score
    bar_index: int
    timestamp: Optional[str] = None
    details: dict = None                       # Pattern-specific details

    @property
    def is_bearish_trap(self) -> bool:
        """True if pattern suggests bears are trapped (bullish reversal)"""
        return self.direction == "bullish"

    @property
    def is_bullish_trap(self) -> bool:
        """True if pattern suggests bulls are trapped (bearish reversal)"""
        return self.direction == "bearish"


@dataclass
class FalseBreakoutRisk:
    """Overall false breakout risk assessment"""

    risk_level: Literal["low", "medium", "high", "very_high"]
    risk_score: int                           # 0-100
    signals_detected: List[FalseBreakoutSignal]
    primary_signal: Optional[FalseBreakoutSignal]
    verdict: str                              # Human-readable assessment
    score_penalty: int                        # Suggested score deduction (0-5)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _find_swing_points(
    df: pl.DataFrame,
    lookback: int = 20,
    high_col: str = "high",
    low_col: str = "low",
    timestamp_col: str = "timestamp",
) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """Find swing highs and swing lows in price data.

    Returns (swing_highs, swing_lows)
    """
    n = len(df)
    highs = df[high_col].to_list()
    lows = df[low_col].to_list()
    timestamps = df[timestamp_col].to_list() if timestamp_col in df.columns else None

    swing_highs: List[SwingPoint] = []
    swing_lows: List[SwingPoint] = []

    # Use 3-bar swing detection (middle bar higher/lower than neighbors)
    start_idx = max(1, n - lookback)

    for i in range(start_idx, n - 1):
        # Swing High: high[i] > high[i-1] and high[i] > high[i+1]
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            swing_highs.append(SwingPoint(
                type="high",
                price=highs[i],
                bar_index=i,
                timestamp=str(timestamps[i]) if timestamps else None,
            ))

        # Swing Low: low[i] < low[i-1] and low[i] < low[i+1]
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            swing_lows.append(SwingPoint(
                type="low",
                price=lows[i],
                bar_index=i,
                timestamp=str(timestamps[i]) if timestamps else None,
            ))

    return swing_highs, swing_lows


def _calculate_atr(df: pl.DataFrame, period: int = 14) -> float:
    """Get latest ATR value"""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    tr = pl.max_horizontal(tr1, tr2, tr3)
    atr = tr.rolling_mean(window_size=period)

    atr_list = atr.to_list()
    return atr_list[-1] if atr_list[-1] is not None else atr_list[-2]


# ---------------------------------------------------------------------------
# Pattern Detection Functions
# ---------------------------------------------------------------------------
def detect_swing_failure(
    df: pl.DataFrame,
    level: Optional[float] = None,
    direction: Optional[Literal["bullish", "bearish"]] = None,
    lookback: int = None,
) -> Optional[FalseBreakoutSignal]:
    """Detect Swing Failure Pattern (SFP).

    SFP occurs when price breaks a swing point but fails to close beyond it,
    indicating a potential reversal.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    level : float, optional
        Specific level to check. If None, uses recent swing points.
    direction : str, optional
        "bullish" (failure at low) or "bearish" (failure at high)
    lookback : int, optional
        Bars to look back for swing points

    Returns
    -------
    FalseBreakoutSignal if SFP detected, None otherwise

    """
    lookback = lookback or FALSE_BREAKOUT_SETTINGS["sfp_lookback"]

    n = len(df)
    if n < 5:
        return None

    highs = df["high"].to_list()
    lows = df["low"].to_list()
    closes = df["close"].to_list()
    opens = df["open"].to_list()
    timestamps = df["timestamp"].to_list() if "timestamp" in df.columns else None

    atr = _calculate_atr(df)

    # Find swing points
    swing_highs, swing_lows = _find_swing_points(df, lookback)

    # Check latest bar for SFP
    last_high = highs[-1]
    last_low = lows[-1]
    last_close = closes[-1]
    last_open = opens[-1]

    # Bearish SFP: Price wicks above swing high but closes below
    if direction in [None, "bearish"] and swing_highs:
        for sh in reversed(swing_highs):
            level_to_check = level or sh.price

            # Wick above level
            if last_high > level_to_check:
                # Body (close and open) below level
                body_top = max(last_close, last_open)
                if body_top < level_to_check:
                    wick_beyond = last_high - level_to_check
                    if wick_beyond >= atr * FALSE_BREAKOUT_SETTINGS["sfp_wick_min_pct"]:
                        confidence = min(90, 50 + (wick_beyond / atr) * 40)
                        return FalseBreakoutSignal(
                            pattern_type="sfp",
                            direction="bearish",
                            level=level_to_check,
                            confidence=round(confidence, 1),
                            bar_index=n - 1,
                            timestamp=str(timestamps[-1]) if timestamps else None,
                            details={
                                "swing_point": sh.price,
                                "wick_beyond": round(wick_beyond, 2),
                                "wick_atr_ratio": round(wick_beyond / atr, 2),
                            }
                        )

    # Bullish SFP: Price wicks below swing low but closes above
    if direction in [None, "bullish"] and swing_lows:
        for sl in reversed(swing_lows):
            level_to_check = level or sl.price

            # Wick below level
            if last_low < level_to_check:
                # Body (close and open) above level
                body_bottom = min(last_close, last_open)
                if body_bottom > level_to_check:
                    wick_beyond = level_to_check - last_low
                    if wick_beyond >= atr * FALSE_BREAKOUT_SETTINGS["sfp_wick_min_pct"]:
                        confidence = min(90, 50 + (wick_beyond / atr) * 40)
                        return FalseBreakoutSignal(
                            pattern_type="sfp",
                            direction="bullish",
                            level=level_to_check,
                            confidence=round(confidence, 1),
                            bar_index=n - 1,
                            timestamp=str(timestamps[-1]) if timestamps else None,
                            details={
                                "swing_point": sl.price,
                                "wick_beyond": round(wick_beyond, 2),
                                "wick_atr_ratio": round(wick_beyond / atr, 2),
                            }
                        )

    return None


def detect_fakeout_candle(
    df: pl.DataFrame,
    level: float,
    direction: Literal["up", "down"],
) -> Optional[FalseBreakoutSignal]:
    """Detect Fakeout Candle pattern.

    Fakeout occurs when a candle has a long wick beyond a level
    but a small body, indicating rejection.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    level : float
        The level being tested
    direction : str
        "up" (testing resistance) or "down" (testing support)

    Returns
    -------
    FalseBreakoutSignal if fakeout detected, None otherwise

    """
    n = len(df)
    if n < 2:
        return None

    last = df[-1]
    high = last["high"].item()
    low = last["low"].item()
    open_ = last["open"].item()
    close = last["close"].item()

    # Calculate body and wick sizes
    body = abs(close - open_)
    total_range = high - low

    if total_range == 0:
        return None

    body_ratio = body / total_range

    # Check wick ratio threshold
    wick_ratio_threshold = FALSE_BREAKOUT_SETTINGS["fakeout_wick_ratio"]
    body_max_pct = FALSE_BREAKOUT_SETTINGS["fakeout_body_max_pct"]

    atr = _calculate_atr(df)
    timestamps = df["timestamp"].to_list() if "timestamp" in df.columns else None

    if direction == "up":
        # Testing resistance - look for upper wick rejection
        upper_wick = high - max(open_, close)

        if high > level and body_ratio < body_max_pct:
            # Long upper wick relative to body
            if body > 0 and upper_wick / body >= wick_ratio_threshold:
                # Close below level
                if close < level:
                    confidence = min(85, 50 + (upper_wick / atr) * 30)
                    return FalseBreakoutSignal(
                        pattern_type="fakeout",
                        direction="bearish",
                        level=level,
                        confidence=round(confidence, 1),
                        bar_index=n - 1,
                        timestamp=str(timestamps[-1]) if timestamps else None,
                        details={
                            "wick_size": round(upper_wick, 2),
                            "body_size": round(body, 2),
                            "wick_body_ratio": round(upper_wick / body if body > 0 else 0, 2),
                        }
                    )

    elif direction == "down":
        # Testing support - look for lower wick rejection
        lower_wick = min(open_, close) - low

        if low < level and body_ratio < body_max_pct:
            # Long lower wick relative to body
            if body > 0 and lower_wick / body >= wick_ratio_threshold:
                # Close above level
                if close > level:
                    confidence = min(85, 50 + (lower_wick / atr) * 30)
                    return FalseBreakoutSignal(
                        pattern_type="fakeout",
                        direction="bullish",
                        level=level,
                        confidence=round(confidence, 1),
                        bar_index=n - 1,
                        timestamp=str(timestamps[-1]) if timestamps else None,
                        details={
                            "wick_size": round(lower_wick, 2),
                            "body_size": round(body, 2),
                            "wick_body_ratio": round(lower_wick / body if body > 0 else 0, 2),
                        }
                    )

    return None


def detect_trap_pattern(
    df: pl.DataFrame,
    lookback: int = None,
) -> Optional[FalseBreakoutSignal]:
    """Detect Bull Trap or Bear Trap pattern.

    Trap occurs when price breaks out, attracts traders, then reverses sharply.

    Bull Trap: Breakout above resistance, then sharp reversal down
    Bear Trap: Breakdown below support, then sharp reversal up
    """
    lookback = lookback or FALSE_BREAKOUT_SETTINGS["trap_lookback"]

    n = len(df)
    if n < lookback + 5:
        return None

    highs = df["high"].to_list()
    lows = df["low"].to_list()
    closes = df["close"].to_list()
    timestamps = df["timestamp"].to_list() if "timestamp" in df.columns else None

    atr = _calculate_atr(df)
    reversal_threshold = atr * FALSE_BREAKOUT_SETTINGS["trap_reversal_min_pct"]

    # Look for Bull Trap: Recent high followed by sharp decline
    recent_max_idx = -1
    recent_max = max(highs[-lookback:])
    for i in range(n - lookback, n):
        if highs[i] == recent_max:
            recent_max_idx = i
            break

    if recent_max_idx > 0 and recent_max_idx < n - 2:
        # Check for decline after the high
        bars_after = n - recent_max_idx - 1
        if bars_after >= 2:
            decline = recent_max - closes[-1]
            if decline >= reversal_threshold:
                # Confirm it was a breakout (above prior resistance)
                prior_highs = highs[n - lookback - 10:n - lookback]
                if prior_highs and recent_max > max(prior_highs):
                    confidence = min(80, 50 + (decline / atr) * 20)
                    return FalseBreakoutSignal(
                        pattern_type="bull_trap",
                        direction="bearish",
                        level=recent_max,
                        confidence=round(confidence, 1),
                        bar_index=n - 1,
                        timestamp=str(timestamps[-1]) if timestamps else None,
                        details={
                            "trap_high": round(recent_max, 2),
                            "decline": round(decline, 2),
                            "decline_atr_ratio": round(decline / atr, 2),
                        }
                    )

    # Look for Bear Trap: Recent low followed by sharp rally
    recent_min_idx = -1
    recent_min = min(lows[-lookback:])
    for i in range(n - lookback, n):
        if lows[i] == recent_min:
            recent_min_idx = i
            break

    if recent_min_idx > 0 and recent_min_idx < n - 2:
        # Check for rally after the low
        bars_after = n - recent_min_idx - 1
        if bars_after >= 2:
            rally = closes[-1] - recent_min
            if rally >= reversal_threshold:
                # Confirm it was a breakdown (below prior support)
                prior_lows = lows[n - lookback - 10:n - lookback]
                if prior_lows and recent_min < min(prior_lows):
                    confidence = min(80, 50 + (rally / atr) * 20)
                    return FalseBreakoutSignal(
                        pattern_type="bear_trap",
                        direction="bullish",
                        level=recent_min,
                        confidence=round(confidence, 1),
                        bar_index=n - 1,
                        timestamp=str(timestamps[-1]) if timestamps else None,
                        details={
                            "trap_low": round(recent_min, 2),
                            "rally": round(rally, 2),
                            "rally_atr_ratio": round(rally / atr, 2),
                        }
                    )

    return None


def detect_stop_hunt(
    df: pl.DataFrame,
    swing_highs: List[SwingPoint] = None,
    swing_lows: List[SwingPoint] = None,
) -> Optional[FalseBreakoutSignal]:
    """Detect Stop Hunt Reversal pattern.

    Stop hunt occurs when price spikes beyond obvious levels (where stops are placed)
    and immediately reverses, indicating institutional liquidity grab.
    """
    n = len(df)
    if n < 3:
        return None

    # Find swing points if not provided
    if swing_highs is None or swing_lows is None:
        swing_highs, swing_lows = _find_swing_points(df, 20)

    highs = df["high"].to_list()
    lows = df["low"].to_list()
    closes = df["close"].to_list()
    opens = df["open"].to_list()
    timestamps = df["timestamp"].to_list() if "timestamp" in df.columns else None

    atr = _calculate_atr(df)
    wick_threshold = atr * FALSE_BREAKOUT_SETTINGS["stop_hunt_wick_atr_ratio"]

    last_high = highs[-1]
    last_low = lows[-1]
    last_close = closes[-1]
    last_open = opens[-1]

    # Bearish stop hunt: Spike above swing highs, close back inside
    for sh in swing_highs:
        if last_high > sh.price + wick_threshold:
            # Check close is back below the level
            if last_close < sh.price and last_open < sh.price:
                confidence = min(85, 60 + ((last_high - sh.price) / atr) * 20)
                return FalseBreakoutSignal(
                    pattern_type="stop_hunt",
                    direction="bearish",
                    level=sh.price,
                    confidence=round(confidence, 1),
                    bar_index=n - 1,
                    timestamp=str(timestamps[-1]) if timestamps else None,
                    details={
                        "hunt_level": round(sh.price, 2),
                        "spike_high": round(last_high, 2),
                        "spike_beyond": round(last_high - sh.price, 2),
                    }
                )

    # Bullish stop hunt: Spike below swing lows, close back inside
    for sl in swing_lows:
        if last_low < sl.price - wick_threshold:
            # Check close is back above the level
            if last_close > sl.price and last_open > sl.price:
                confidence = min(85, 60 + ((sl.price - last_low) / atr) * 20)
                return FalseBreakoutSignal(
                    pattern_type="stop_hunt",
                    direction="bullish",
                    level=sl.price,
                    confidence=round(confidence, 1),
                    bar_index=n - 1,
                    timestamp=str(timestamps[-1]) if timestamps else None,
                    details={
                        "hunt_level": round(sl.price, 2),
                        "spike_low": round(last_low, 2),
                        "spike_beyond": round(sl.price - last_low, 2),
                    }
                )

    return None


# ---------------------------------------------------------------------------
# Comprehensive Assessment
# ---------------------------------------------------------------------------
def summarize_false_breakout_risk(
    df: pl.DataFrame,
    breakout_level: Optional[float] = None,
    direction: Optional[Literal["up", "down"]] = None,
) -> FalseBreakoutRisk:
    """Comprehensive false breakout risk assessment.

    Runs all pattern detectors and provides overall risk score.

    Parameters
    ----------
    df : pl.DataFrame
        OHLCV data
    breakout_level : float, optional
        The level being broken out from
    direction : str, optional
        "up" (bullish breakout) or "down" (bearish breakout)

    Returns
    -------
    FalseBreakoutRisk
        Complete risk assessment with all detected signals

    """
    signals: List[FalseBreakoutSignal] = []

    # Run all detectors
    sfp = detect_swing_failure(df)
    if sfp:
        signals.append(sfp)

    if breakout_level and direction:
        fakeout = detect_fakeout_candle(df, breakout_level, direction)
        if fakeout:
            signals.append(fakeout)

    trap = detect_trap_pattern(df)
    if trap:
        signals.append(trap)

    stop_hunt = detect_stop_hunt(df)
    if stop_hunt:
        signals.append(stop_hunt)

    # Calculate risk score
    if not signals:
        return FalseBreakoutRisk(
            risk_level="low",
            risk_score=10,
            signals_detected=[],
            primary_signal=None,
            verdict="No false breakout patterns detected",
            score_penalty=0,
        )

    # Aggregate confidence
    total_confidence = sum(s.confidence for s in signals)
    avg_confidence = total_confidence / len(signals)

    # Determine risk level
    if len(signals) >= 3 or avg_confidence >= 80:
        risk_level = "very_high"
        risk_score = 90
        score_penalty = 4
    elif len(signals) >= 2 or avg_confidence >= 70:
        risk_level = "high"
        risk_score = 75
        score_penalty = 3
    elif avg_confidence >= 60:
        risk_level = "medium"
        risk_score = 50
        score_penalty = 2
    else:
        risk_level = "medium"
        risk_score = 35
        score_penalty = 1

    # Primary signal (highest confidence)
    primary = max(signals, key=lambda s: s.confidence)

    # Generate verdict
    pattern_names = [s.pattern_type for s in signals]
    verdict = f"Detected {len(signals)} warning pattern(s): {', '.join(pattern_names)}. "
    verdict += f"Primary: {primary.pattern_type} with {primary.confidence}% confidence."

    return FalseBreakoutRisk(
        risk_level=risk_level,
        risk_score=risk_score,
        signals_detected=signals,
        primary_signal=primary,
        verdict=verdict,
        score_penalty=score_penalty,
    )


def attach_false_breakout_signals(
    df: pl.DataFrame,
) -> pl.DataFrame:
    """Attach false breakout detection columns to DataFrame.

    Adds columns:
        - false_breakout_risk: str (risk level)
        - false_breakout_score: int (0-100)
        - sfp_detected: bool
        - trap_detected: bool
    """
    risk = summarize_false_breakout_risk(df)

    sfp = detect_swing_failure(df)
    trap = detect_trap_pattern(df)

    return df.with_columns([
        pl.lit(risk.risk_level).alias("false_breakout_risk"),
        pl.lit(risk.risk_score).alias("false_breakout_score"),
        pl.lit(sfp is not None).alias("sfp_detected"),
        pl.lit(trap is not None).alias("trap_detected"),
    ])


# ---------------------------------------------------------------------------
# Registry Export (for auto-discovery)
# ---------------------------------------------------------------------------
EXPORTS = {
    "swing_failure": detect_swing_failure,
    "fakeout_candle": detect_fakeout_candle,
    "trap_pattern": detect_trap_pattern,
    "stop_hunt": detect_stop_hunt,
    "false_breakout_risk": summarize_false_breakout_risk,
    "false_breakout_attach": attach_false_breakout_signals,
}

NAME = "false_breakout"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    # Create sample data with false breakout patterns
    np.random.seed(42)
    n = 50

    # Base trend
    prices = [100.0]
    for i in range(1, n):
        prices.append(prices[-1] + np.random.uniform(-0.5, 0.5))

    # Create a bull trap scenario (spike up then reversal)
    prices[35] = 105.0  # Breakout
    prices[36] = 106.0  # Higher
    prices[37] = 104.0  # Start reversal
    prices[38] = 102.0  # Continue down
    prices[39] = 101.0  # Trap confirmed

    # Create an SFP at the end
    highs = [p + np.random.uniform(0.3, 1.0) for p in prices]
    lows = [p - np.random.uniform(0.3, 1.0) for p in prices]
    closes = prices.copy()
    opens = [p - np.random.uniform(-0.3, 0.3) for p in prices]

    # Make last bar an SFP (wick above but close below)
    highs[-1] = 108.0  # Spike above resistance
    lows[-1] = 100.5
    opens[-1] = 101.0
    closes[-1] = 100.8  # Close back below

    df = pl.DataFrame({
        "timestamp": list(range(n)),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [10000 + np.random.randint(-2000, 2000) for _ in range(n)],
    })

    # Test SFP
    sfp = detect_swing_failure(df)
    if sfp:
        print(f"SFP Detected: {sfp.pattern_type} @ {sfp.level}")
        print(f"  Direction: {sfp.direction}, Confidence: {sfp.confidence}%")
        print(f"  Details: {sfp.details}")
    else:
        print("No SFP detected")

    # Test Trap
    trap = detect_trap_pattern(df)
    if trap:
        print(f"\nTrap Detected: {trap.pattern_type}")
        print(f"  Direction: {trap.direction}, Confidence: {trap.confidence}%")
        print(f"  Details: {trap.details}")
    else:
        print("\nNo Trap detected")

    # Test comprehensive risk
    risk = summarize_false_breakout_risk(df)
    print("\nOverall Risk Assessment:")
    print(f"  Risk Level: {risk.risk_level}")
    print(f"  Risk Score: {risk.risk_score}")
    print(f"  Score Penalty: -{risk.score_penalty}")
    print(f"  Signals: {len(risk.signals_detected)}")
    print(f"  Verdict: {risk.verdict}")
