# queen/technicals/patterns/false_breakout.py
"""
False Breakout Pattern Detection Module
=======================================
Detects patterns that indicate a breakout is likely to fail:
- Swing Failure Pattern (SFP): Price exceeds level but closes back inside
- Fakeout Candle: Long wick beyond level with body inside
- Bull/Bear Trap: False breakout that reverses sharply
- Stop Hunt Reversal: Liquidity grab followed by reversal

These patterns help filter out 70-80% of false breakout signals.

**UPDATED**: Now uses shared `helpers/swing_detection.py` for swing detection
to maintain DRY principles across the codebase.

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
    All thresholds configurable via settings/breakout_settings.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal, List, Tuple
import polars as pl

# ---------------------------------------------------------------------------
# Try to use existing helpers (DRY)
# ---------------------------------------------------------------------------
try:
    from queen.helpers.ta_math import atr_wilder
    _USE_EXISTING_ATR = True
except ImportError:
    _USE_EXISTING_ATR = False

# Try to use shared swing detection helper (DRY)
try:
    from queen.helpers.swing_detection import (
        find_swing_points,
        SwingPoint as SharedSwingPoint,
        SwingType,
    )
    _USE_SHARED_SWING = True
except ImportError:
    _USE_SHARED_SWING = False

# ---------------------------------------------------------------------------
# Settings (import from settings when available, fallback to defaults)
# ---------------------------------------------------------------------------
try:
    from queen.settings.breakout_settings import FALSE_BREAKOUT_SETTINGS
except ImportError:
    FALSE_BREAKOUT_SETTINGS = {
        "sfp_lookback": 20,
        "sfp_wick_min_pct": 0.3,
        "sfp_body_inside_pct": 0.8,
        "sfp_confidence_base": 50,
        "sfp_confidence_max": 90,
        "fakeout_wick_ratio": 2.0,
        "fakeout_body_max_pct": 0.3,
        "fakeout_confidence_base": 50,
        "fakeout_confidence_max": 85,
        "trap_reversal_min_pct": 0.5,
        "trap_lookback": 5,
        "trap_confirmation_bars": 2,
        "trap_confidence_base": 50,
        "trap_confidence_max": 80,
        "stop_hunt_wick_atr_ratio": 0.5,
        "stop_hunt_close_inside": True,
        "stop_hunt_confidence_base": 60,
        "stop_hunt_confidence_max": 85,
        "level_tolerance_pct": 0.1,
    }


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class SwingPoint:
    """Represents a swing high or swing low (local definition for fallback)"""
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
def _find_swing_points_local(
    df: pl.DataFrame,
    lookback: int = 20,
    high_col: str = "high",
    low_col: str = "low",
    timestamp_col: str = "timestamp",
) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Local swing detection - used only if shared helper not available.

    Returns (swing_highs, swing_lows)
    """
    n = len(df)
    if n < 3:
        return [], []

    highs = df[high_col].to_list()
    lows = df[low_col].to_list()
    timestamps = df[timestamp_col].to_list() if timestamp_col in df.columns else None

    swing_highs: List[SwingPoint] = []
    swing_lows: List[SwingPoint] = []

    start_idx = max(1, n - lookback)

    for i in range(start_idx, n - 1):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            swing_highs.append(SwingPoint(
                type="high",
                price=highs[i],
                bar_index=i,
                timestamp=str(timestamps[i]) if timestamps else None,
            ))

        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            swing_lows.append(SwingPoint(
                type="low",
                price=lows[i],
                bar_index=i,
                timestamp=str(timestamps[i]) if timestamps else None,
            ))

    return swing_highs, swing_lows


def _find_swing_points(
    df: pl.DataFrame,
    lookback: int = 20,
    high_col: str = "high",
    low_col: str = "low",
    timestamp_col: str = "timestamp",
) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Find swing highs and swing lows in price data.

    Uses shared helper if available, otherwise falls back to local.
    Returns (swing_highs, swing_lows)
    """
    if _USE_SHARED_SWING:
        try:
            # Use shared helper
            points = find_swing_points(
                df,
                high_col=high_col,
                low_col=low_col,
                timestamp_col=timestamp_col,
                max_points=lookback,
            )

            # Convert to local SwingPoint format
            swing_highs = [
                SwingPoint(
                    type="high",
                    price=p.price,
                    bar_index=p.bar_index,
                    timestamp=p.timestamp,
                )
                for p in points if p.type == SwingType.HIGH
            ]
            swing_lows = [
                SwingPoint(
                    type="low",
                    price=p.price,
                    bar_index=p.bar_index,
                    timestamp=p.timestamp,
                )
                for p in points if p.type == SwingType.LOW
            ]
            return swing_highs, swing_lows
        except Exception:
            pass

    # Fallback to local implementation
    return _find_swing_points_local(df, lookback, high_col, low_col, timestamp_col)


def _calculate_atr(df: pl.DataFrame, period: int = 14) -> float:
    """Get latest ATR value"""
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

    atr_list = df_with_atr["_atr"].to_list()
    for v in reversed(atr_list):
        if v is not None:
            return v
    return 1.0


# ---------------------------------------------------------------------------
# Pattern Detection Functions
# ---------------------------------------------------------------------------
def detect_swing_failure(
    df: pl.DataFrame,
    level: Optional[float] = None,
    direction: Optional[Literal["bullish", "bearish"]] = None,
    lookback: int = None,
) -> Optional[FalseBreakoutSignal]:
    """
    Detect Swing Failure Pattern (SFP).

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
    FalseBreakoutSignal or None
    """
    if df is None or df.is_empty() or df.height < 5:
        return None

    lookback = lookback or FALSE_BREAKOUT_SETTINGS["sfp_lookback"]
    atr = _calculate_atr(df)

    n = df.height
    last_high = float(df["high"].tail(1).item())
    last_low = float(df["low"].tail(1).item())
    last_close = float(df["close"].tail(1).item())
    last_open = float(df["open"].tail(1).item())

    timestamps = df["timestamp"].to_list() if "timestamp" in df.columns else None

    swing_highs, swing_lows = _find_swing_points(df, lookback=lookback)

    # Bearish SFP: Price wicks above swing high but closes below
    if direction is None or direction == "bearish":
        for sh in swing_highs:
            if sh.bar_index >= n - 2:
                continue

            if level and abs(sh.price - level) > level * 0.01:
                continue

            if last_high > sh.price:
                if last_close < sh.price and last_open < sh.price:
                    wick_size = last_high - sh.price
                    if wick_size >= atr * FALSE_BREAKOUT_SETTINGS["sfp_wick_min_pct"]:
                        confidence = min(
                            FALSE_BREAKOUT_SETTINGS.get("sfp_confidence_max", 90),
                            FALSE_BREAKOUT_SETTINGS.get("sfp_confidence_base", 50) + (wick_size / atr) * 30
                        )
                        return FalseBreakoutSignal(
                            pattern_type="sfp",
                            direction="bearish",
                            level=sh.price,
                            confidence=round(confidence, 1),
                            bar_index=n - 1,
                            timestamp=str(timestamps[-1]) if timestamps else None,
                            details={
                                "swing_level": round(sh.price, 2),
                                "wick_high": round(last_high, 2),
                                "close": round(last_close, 2),
                                "wick_beyond": round(wick_size, 2),
                            }
                        )

    # Bullish SFP: Price wicks below swing low but closes above
    if direction is None or direction == "bullish":
        for sl in swing_lows:
            if sl.bar_index >= n - 2:
                continue

            if level and abs(sl.price - level) > level * 0.01:
                continue

            if last_low < sl.price:
                if last_close > sl.price and last_open > sl.price:
                    wick_size = sl.price - last_low
                    if wick_size >= atr * FALSE_BREAKOUT_SETTINGS["sfp_wick_min_pct"]:
                        confidence = min(
                            FALSE_BREAKOUT_SETTINGS.get("sfp_confidence_max", 90),
                            FALSE_BREAKOUT_SETTINGS.get("sfp_confidence_base", 50) + (wick_size / atr) * 30
                        )
                        return FalseBreakoutSignal(
                            pattern_type="sfp",
                            direction="bullish",
                            level=sl.price,
                            confidence=round(confidence, 1),
                            bar_index=n - 1,
                            timestamp=str(timestamps[-1]) if timestamps else None,
                            details={
                                "swing_level": round(sl.price, 2),
                                "wick_low": round(last_low, 2),
                                "close": round(last_close, 2),
                                "wick_beyond": round(wick_size, 2),
                            }
                        )

    return None


def detect_fakeout_candle(
    df: pl.DataFrame,
    level: float,
    direction: Literal["up", "down"],
) -> Optional[FalseBreakoutSignal]:
    """
    Detect Fakeout Candle pattern.

    A fakeout candle has a long wick that exceeds the level but body stays inside.
    """
    if df is None or df.is_empty():
        return None

    n = df.height
    last_high = float(df["high"].tail(1).item())
    last_low = float(df["low"].tail(1).item())
    last_close = float(df["close"].tail(1).item())
    last_open = float(df["open"].tail(1).item())

    timestamps = df["timestamp"].to_list() if "timestamp" in df.columns else None

    body_top = max(last_open, last_close)
    body_bottom = min(last_open, last_close)
    body_size = body_top - body_bottom
    total_range = last_high - last_low

    if total_range <= 0:
        return None

    wick_ratio_threshold = FALSE_BREAKOUT_SETTINGS["fakeout_wick_ratio"]
    body_max_pct = FALSE_BREAKOUT_SETTINGS["fakeout_body_max_pct"]

    # Bearish fakeout: Wick above level, body below
    if direction == "up":
        upper_wick = last_high - body_top
        if last_high > level and body_top < level:
            if body_size > 0 and upper_wick / body_size >= wick_ratio_threshold:
                if body_size / total_range <= body_max_pct:
                    confidence = min(
                        FALSE_BREAKOUT_SETTINGS.get("fakeout_confidence_max", 85),
                        FALSE_BREAKOUT_SETTINGS.get("fakeout_confidence_base", 50) + (upper_wick / body_size) * 10
                    )
                    return FalseBreakoutSignal(
                        pattern_type="fakeout",
                        direction="bearish",
                        level=level,
                        confidence=round(confidence, 1),
                        bar_index=n - 1,
                        timestamp=str(timestamps[-1]) if timestamps else None,
                        details={
                            "level": round(level, 2),
                            "wick_high": round(last_high, 2),
                            "body_top": round(body_top, 2),
                            "wick_ratio": round(upper_wick / body_size, 2) if body_size > 0 else 0,
                        }
                    )

    # Bullish fakeout: Wick below level, body above
    if direction == "down":
        lower_wick = body_bottom - last_low
        if last_low < level and body_bottom > level:
            if body_size > 0 and lower_wick / body_size >= wick_ratio_threshold:
                if body_size / total_range <= body_max_pct:
                    confidence = min(
                        FALSE_BREAKOUT_SETTINGS.get("fakeout_confidence_max", 85),
                        FALSE_BREAKOUT_SETTINGS.get("fakeout_confidence_base", 50) + (lower_wick / body_size) * 10
                    )
                    return FalseBreakoutSignal(
                        pattern_type="fakeout",
                        direction="bullish",
                        level=level,
                        confidence=round(confidence, 1),
                        bar_index=n - 1,
                        timestamp=str(timestamps[-1]) if timestamps else None,
                        details={
                            "level": round(level, 2),
                            "wick_low": round(last_low, 2),
                            "body_bottom": round(body_bottom, 2),
                            "wick_ratio": round(lower_wick / body_size, 2) if body_size > 0 else 0,
                        }
                    )

    return None


def detect_trap_pattern(
    df: pl.DataFrame,
    lookback: int = None,
) -> Optional[FalseBreakoutSignal]:
    """
    Detect Bull/Bear Trap pattern.

    A trap occurs when price makes a new high/low, then reverses sharply.
    """
    if df is None or df.is_empty() or df.height < 10:
        return None

    lookback = lookback or FALSE_BREAKOUT_SETTINGS["trap_lookback"]
    trap_lookback = min(lookback, df.height - 5)

    if trap_lookback < 3:
        return None

    atr = _calculate_atr(df)
    min_reversal = atr * FALSE_BREAKOUT_SETTINGS["trap_reversal_min_pct"]

    closes = df["close"].to_list()
    highs = df["high"].to_list()
    lows = df["low"].to_list()
    timestamps = df["timestamp"].to_list() if "timestamp" in df.columns else None

    n = df.height
    recent_closes = closes[-trap_lookback:]
    recent_highs = highs[-trap_lookback:]
    recent_lows = lows[-trap_lookback:]

    # Bull trap: New high followed by reversal down
    max_high_idx = recent_highs.index(max(recent_highs))
    if max_high_idx < len(recent_highs) - 2:
        peak_high = recent_highs[max_high_idx]
        subsequent_close = recent_closes[-1]

        if peak_high - subsequent_close >= min_reversal:
            reversal_pct = (peak_high - subsequent_close) / atr * 100
            confidence = min(
                FALSE_BREAKOUT_SETTINGS.get("trap_confidence_max", 80),
                FALSE_BREAKOUT_SETTINGS.get("trap_confidence_base", 50) + reversal_pct * 0.3
            )
            return FalseBreakoutSignal(
                pattern_type="bull_trap",
                direction="bearish",
                level=peak_high,
                confidence=round(confidence, 1),
                bar_index=n - 1,
                timestamp=str(timestamps[-1]) if timestamps else None,
                details={
                    "trap_high": round(peak_high, 2),
                    "current_close": round(subsequent_close, 2),
                    "reversal_size": round(peak_high - subsequent_close, 2),
                    "reversal_atr_pct": round(reversal_pct, 1),
                }
            )

    # Bear trap: New low followed by reversal up
    min_low_idx = recent_lows.index(min(recent_lows))
    if min_low_idx < len(recent_lows) - 2:
        trough_low = recent_lows[min_low_idx]
        subsequent_close = recent_closes[-1]

        if subsequent_close - trough_low >= min_reversal:
            reversal_pct = (subsequent_close - trough_low) / atr * 100
            confidence = min(
                FALSE_BREAKOUT_SETTINGS.get("trap_confidence_max", 80),
                FALSE_BREAKOUT_SETTINGS.get("trap_confidence_base", 50) + reversal_pct * 0.3
            )
            return FalseBreakoutSignal(
                pattern_type="bear_trap",
                direction="bullish",
                level=trough_low,
                confidence=round(confidence, 1),
                bar_index=n - 1,
                timestamp=str(timestamps[-1]) if timestamps else None,
                details={
                    "trap_low": round(trough_low, 2),
                    "current_close": round(subsequent_close, 2),
                    "reversal_size": round(subsequent_close - trough_low, 2),
                    "reversal_atr_pct": round(reversal_pct, 1),
                }
            )

    return None


def detect_stop_hunt(
    df: pl.DataFrame,
    lookback: int = None,
) -> Optional[FalseBreakoutSignal]:
    """
    Detect Stop Hunt Reversal pattern.

    Stop hunt occurs when price spikes beyond a level to trigger stops,
    then immediately reverses.
    """
    if df is None or df.is_empty() or df.height < 5:
        return None

    lookback = lookback or FALSE_BREAKOUT_SETTINGS["sfp_lookback"]
    atr = _calculate_atr(df)
    wick_threshold = atr * FALSE_BREAKOUT_SETTINGS["stop_hunt_wick_atr_ratio"]

    n = df.height
    last_high = float(df["high"].tail(1).item())
    last_low = float(df["low"].tail(1).item())
    last_close = float(df["close"].tail(1).item())
    last_open = float(df["open"].tail(1).item())

    timestamps = df["timestamp"].to_list() if "timestamp" in df.columns else None

    swing_highs, swing_lows = _find_swing_points(df, lookback=lookback)

    # Bearish stop hunt: Spike above swing highs, close back inside
    for sh in swing_highs:
        if sh.bar_index >= n - 2:
            continue

        if last_high > sh.price + wick_threshold:
            if last_close < sh.price and last_open < sh.price:
                confidence = min(
                    FALSE_BREAKOUT_SETTINGS.get("stop_hunt_confidence_max", 85),
                    FALSE_BREAKOUT_SETTINGS.get("stop_hunt_confidence_base", 60) + ((last_high - sh.price) / atr) * 20
                )
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
        if sl.bar_index >= n - 2:
            continue

        if last_low < sl.price - wick_threshold:
            if last_close > sl.price and last_open > sl.price:
                confidence = min(
                    FALSE_BREAKOUT_SETTINGS.get("stop_hunt_confidence_max", 85),
                    FALSE_BREAKOUT_SETTINGS.get("stop_hunt_confidence_base", 60) + ((sl.price - last_low) / atr) * 20
                )
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
    """
    Comprehensive false breakout risk assessment.

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
    """
    Attach false breakout detection columns to DataFrame.

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

    print("=" * 60)
    print("FALSE BREAKOUT DETECTION TEST")
    print("=" * 60)
    print(f"Using shared swing helper: {_USE_SHARED_SWING}")
    print(f"Using shared ATR helper: {_USE_EXISTING_ATR}")

    # Create sample data with false breakout patterns
    np.random.seed(42)
    n = 50

    prices = [100.0]
    for i in range(1, n):
        prices.append(prices[-1] + np.random.uniform(-0.5, 0.5))

    # Create a bull trap scenario
    prices[35] = 105.0
    prices[36] = 106.0
    prices[37] = 104.0
    prices[38] = 102.0
    prices[39] = 101.0

    highs = [p + np.random.uniform(0.3, 1.0) for p in prices]
    lows = [p - np.random.uniform(0.3, 1.0) for p in prices]
    closes = prices.copy()
    opens = [p - np.random.uniform(-0.3, 0.3) for p in prices]

    # Make last bar an SFP
    highs[-1] = 108.0
    lows[-1] = 100.5
    opens[-1] = 101.0
    closes[-1] = 100.8

    df = pl.DataFrame({
        "timestamp": list(range(n)),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [10000 + np.random.randint(-2000, 2000) for _ in range(n)],
    })

    # Test SFP
    print("\n📊 SFP DETECTION:")
    sfp = detect_swing_failure(df)
    if sfp:
        print(f"   Pattern: {sfp.pattern_type} @ {sfp.level:.2f}")
        print(f"   Direction: {sfp.direction}, Confidence: {sfp.confidence}%")
    else:
        print("   No SFP detected")

    # Test Trap
    print("\n📊 TRAP DETECTION:")
    trap = detect_trap_pattern(df)
    if trap:
        print(f"   Pattern: {trap.pattern_type}")
        print(f"   Direction: {trap.direction}, Confidence: {trap.confidence}%")
    else:
        print("   No Trap detected")

    # Test comprehensive risk
    print("\n📊 OVERALL RISK ASSESSMENT:")
    risk = summarize_false_breakout_risk(df)
    print(f"   Risk Level: {risk.risk_level}")
    print(f"   Risk Score: {risk.risk_score}")
    print(f"   Score Penalty: -{risk.score_penalty}")
    print(f"   Signals: {len(risk.signals_detected)}")
    print(f"   Verdict: {risk.verdict}")

    print("\n" + "=" * 60)
    print("✅ False Breakout test complete!")
