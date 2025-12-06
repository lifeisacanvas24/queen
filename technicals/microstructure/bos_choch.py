# queen/technicals/microstructure/bos_choch.py
"""
BOS & CHoCH Detection Module
============================
Detects Break of Structure (BOS) and Change of Character (CHoCH) patterns.

Definitions:
- BOS (Break of Structure): Price breaks a swing high/low in the SAME direction
  as the trend, confirming continuation.
- CHoCH (Change of Character): Price breaks a swing high/low in the OPPOSITE
  direction of the trend, signaling potential reversal.

Usage:
    from queen.technicals.microstructure.bos_choch import (
        detect_bos,
        detect_choch,
        analyze_market_structure,
    )

    result = analyze_market_structure(df)
    if result.choch_detected:
        print(f"CHoCH detected - potential reversal!")
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
    from queen.settings.breakout_settings import BOS_CHOCH_SETTINGS
except ImportError:
    BOS_CHOCH_SETTINGS = {
        "bos_min_break_pct": 0.001,
        "bos_confirmation_close": True,
        "choch_requires_impulse": True,
        "choch_min_impulse_atr": 1.0,
        "structure_lookback": 50,
        "swing_lookback": 20,
    }


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"


@dataclass
class BOSSignal:
    """Break of Structure signal."""
    direction: TrendDirection
    level: float
    break_price: float
    bar_index: int
    confirmation: bool
    strength: float
    timestamp: Optional[str] = None


@dataclass
class CHoCHSignal:
    """Change of Character signal."""
    from_trend: TrendDirection
    to_trend: TrendDirection
    level: float
    break_price: float
    bar_index: int
    impulse_confirmed: bool
    strength: float
    timestamp: Optional[str] = None


@dataclass
class MarketStructureResult:
    """Complete market structure analysis result."""
    current_trend: TrendDirection
    bos_signals: List[BOSSignal]
    choch_signals: List[CHoCHSignal]
    last_bos: Optional[BOSSignal]
    last_choch: Optional[CHoCHSignal]
    bos_detected: bool
    choch_detected: bool
    swing_highs: List[float]
    swing_lows: List[float]
    structure_bias: Literal["bullish", "bearish", "neutral"]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _get_swing_points(df: pl.DataFrame, lookback: int = 20):
    """Get swing points with price and index."""
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


def _determine_trend(swing_highs: List[dict], swing_lows: List[dict]) -> TrendDirection:
    """Determine trend based on swing structure."""
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return TrendDirection.SIDEWAYS

    recent_highs = sorted(swing_highs, key=lambda x: x["index"])[-3:]
    recent_lows = sorted(swing_lows, key=lambda x: x["index"])[-3:]

    hh = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i]["price"] > recent_highs[i-1]["price"])
    hl = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i]["price"] > recent_lows[i-1]["price"])
    ll = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i]["price"] < recent_lows[i-1]["price"])
    lh = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i]["price"] < recent_highs[i-1]["price"])

    if hh >= 1 and hl >= 1:
        return TrendDirection.UP
    elif ll >= 1 and lh >= 1:
        return TrendDirection.DOWN
    return TrendDirection.SIDEWAYS


# ---------------------------------------------------------------------------
# Main Detection Functions
# ---------------------------------------------------------------------------
def detect_bos(df: pl.DataFrame, trend: Optional[TrendDirection] = None, lookback: int = 20) -> List[BOSSignal]:
    """Detect Break of Structure (trend continuation) signals."""
    if df is None or df.is_empty() or df.height < 5:
        return []

    swing_highs, swing_lows = _get_swing_points(df, lookback)
    if trend is None:
        trend = _determine_trend(swing_highs, swing_lows)

    if trend == TrendDirection.SIDEWAYS:
        return []

    min_break = BOS_CHOCH_SETTINGS["bos_min_break_pct"]
    need_close = BOS_CHOCH_SETTINGS["bos_confirmation_close"]

    n = df.height
    closes, highs, lows = df["close"].to_list(), df["high"].to_list(), df["low"].to_list()
    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None

    bos_signals = []

    if trend == TrendDirection.UP:
        for sh in swing_highs:
            level, idx = sh["price"], sh["index"]
            for i in range(idx + 1, n):
                if highs[i] > level * (1 + min_break):
                    confirmed = closes[i] > level if need_close else True
                    bos_signals.append(BOSSignal(
                        direction=TrendDirection.UP, level=level, break_price=highs[i],
                        bar_index=i, confirmation=confirmed, strength=70 if confirmed else 50,
                        timestamp=timestamps[i] if timestamps else None,
                    ))
                    break
    else:
        for sl in swing_lows:
            level, idx = sl["price"], sl["index"]
            for i in range(idx + 1, n):
                if lows[i] < level * (1 - min_break):
                    confirmed = closes[i] < level if need_close else True
                    bos_signals.append(BOSSignal(
                        direction=TrendDirection.DOWN, level=level, break_price=lows[i],
                        bar_index=i, confirmation=confirmed, strength=70 if confirmed else 50,
                        timestamp=timestamps[i] if timestamps else None,
                    ))
                    break

    return bos_signals


def detect_choch(df: pl.DataFrame, trend: Optional[TrendDirection] = None, lookback: int = 20) -> List[CHoCHSignal]:
    """Detect Change of Character (trend reversal) signals."""
    if df is None or df.is_empty() or df.height < 5:
        return []

    swing_highs, swing_lows = _get_swing_points(df, lookback)
    if trend is None:
        trend = _determine_trend(swing_highs, swing_lows)

    if trend == TrendDirection.SIDEWAYS:
        return []

    min_break = BOS_CHOCH_SETTINGS["bos_min_break_pct"]
    need_impulse = BOS_CHOCH_SETTINGS["choch_requires_impulse"]
    min_impulse = BOS_CHOCH_SETTINGS["choch_min_impulse_atr"]
    atr = _calculate_atr(df)

    n = df.height
    closes, highs, lows = df["close"].to_list(), df["high"].to_list(), df["low"].to_list()
    timestamps = df["timestamp"].cast(pl.Utf8).to_list() if "timestamp" in df.columns else None

    choch_signals = []

    if trend == TrendDirection.UP:
        # In uptrend, CHoCH = break below swing low
        for sl in swing_lows:
            level, idx = sl["price"], sl["index"]
            for i in range(idx + 1, n):
                if lows[i] < level * (1 - min_break) and closes[i] < level:
                    impulse_ok = True
                    if need_impulse and i + 2 < n:
                        impulse = level - min(lows[i:i+3])
                        impulse_ok = impulse >= min_impulse * atr

                    choch_signals.append(CHoCHSignal(
                        from_trend=TrendDirection.UP, to_trend=TrendDirection.DOWN,
                        level=level, break_price=lows[i], bar_index=i,
                        impulse_confirmed=impulse_ok, strength=80 if impulse_ok else 55,
                        timestamp=timestamps[i] if timestamps else None,
                    ))
                    break
    else:
        # In downtrend, CHoCH = break above swing high
        for sh in swing_highs:
            level, idx = sh["price"], sh["index"]
            for i in range(idx + 1, n):
                if highs[i] > level * (1 + min_break) and closes[i] > level:
                    impulse_ok = True
                    if need_impulse and i + 2 < n:
                        impulse = max(highs[i:i+3]) - level
                        impulse_ok = impulse >= min_impulse * atr

                    choch_signals.append(CHoCHSignal(
                        from_trend=TrendDirection.DOWN, to_trend=TrendDirection.UP,
                        level=level, break_price=highs[i], bar_index=i,
                        impulse_confirmed=impulse_ok, strength=80 if impulse_ok else 55,
                        timestamp=timestamps[i] if timestamps else None,
                    ))
                    break

    return choch_signals


def analyze_market_structure(df: pl.DataFrame, lookback: int = 50) -> MarketStructureResult:
    """Complete market structure analysis including BOS and CHoCH."""
    if df is None or df.is_empty() or df.height < 5:
        return MarketStructureResult(
            current_trend=TrendDirection.SIDEWAYS, bos_signals=[], choch_signals=[],
            last_bos=None, last_choch=None, bos_detected=False, choch_detected=False,
            swing_highs=[], swing_lows=[], structure_bias="neutral",
        )

    swing_highs, swing_lows = _get_swing_points(df, lookback)
    current_trend = _determine_trend(swing_highs, swing_lows)

    bos_signals = detect_bos(df, current_trend, lookback)
    choch_signals = detect_choch(df, current_trend, lookback)

    n = df.height
    recent_window = 10

    recent_bos = [s for s in bos_signals if s.bar_index >= n - recent_window]
    recent_choch = [s for s in choch_signals if s.bar_index >= n - recent_window]

    last_bos = max(bos_signals, key=lambda x: x.bar_index) if bos_signals else None
    last_choch = max(choch_signals, key=lambda x: x.bar_index) if choch_signals else None

    if current_trend == TrendDirection.UP:
        structure_bias = "bullish"
    elif current_trend == TrendDirection.DOWN:
        structure_bias = "bearish"
    else:
        structure_bias = "neutral"

    if recent_choch:
        structure_bias = "bullish" if recent_choch[-1].to_trend == TrendDirection.UP else "bearish"

    return MarketStructureResult(
        current_trend=current_trend,
        bos_signals=bos_signals,
        choch_signals=choch_signals,
        last_bos=last_bos,
        last_choch=last_choch,
        bos_detected=len(recent_bos) > 0,
        choch_detected=len(recent_choch) > 0,
        swing_highs=[sh["price"] for sh in swing_highs],
        swing_lows=[sl["price"] for sl in swing_lows],
        structure_bias=structure_bias,
    )


def summarize_bos_choch(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary dict for signal cards."""
    result = analyze_market_structure(df)

    return {
        "current_trend": result.current_trend.value,
        "bos_detected": result.bos_detected,
        "choch_detected": result.choch_detected,
        "last_bos_level": result.last_bos.level if result.last_bos else None,
        "last_choch_level": result.last_choch.level if result.last_choch else None,
        "choch_direction": result.last_choch.to_trend.value if result.last_choch else None,
        "structure_bias": result.structure_bias,
        "swing_high_count": len(result.swing_highs),
        "swing_low_count": len(result.swing_lows),
    }


# ---------------------------------------------------------------------------
# Registry Export
# ---------------------------------------------------------------------------
EXPORTS = {
    "bos": detect_bos,
    "choch": detect_choch,
    "market_structure": analyze_market_structure,
    "bos_choch_summary": summarize_bos_choch,
}

NAME = "bos_choch"


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import numpy as np

    print("=" * 60)
    print("BOS / CHoCH TEST")
    print("=" * 60)
    print(f"Using shared swing helper: {_USE_SHARED_SWING}")

    np.random.seed(42)
    n = 60

    # Create uptrend then reversal pattern
    prices = [100.0]
    for i in range(1, n):
        if i < 30:
            change = np.random.uniform(0.0, 0.8)  # Uptrend
        elif i == 30:
            change = -2.0  # CHoCH break
        else:
            change = np.random.uniform(-0.8, 0.2)  # Downtrend
        prices.append(prices[-1] + change)

    df = pl.DataFrame({
        "timestamp": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
        "open": prices,
        "high": [p + np.random.uniform(0.3, 0.8) for p in prices],
        "low": [p - np.random.uniform(0.3, 0.8) for p in prices],
        "close": [prices[i] + np.random.uniform(-0.2, 0.2) for i in range(n)],
        "volume": [10000 + np.random.randint(-2000, 2000) for _ in range(n)],
    })

    result = analyze_market_structure(df)

    print(f"\n📊 MARKET STRUCTURE:")
    print(f"   Current Trend: {result.current_trend.value}")
    print(f"   Structure Bias: {result.structure_bias}")
    print(f"   Swing Highs: {len(result.swing_highs)}")
    print(f"   Swing Lows: {len(result.swing_lows)}")

    print(f"\n📊 BOS SIGNALS: {len(result.bos_signals)}")
    for bos in result.bos_signals[-3:]:
        print(f"   {bos.direction.value} @ {bos.level:.2f} | Bar {bos.bar_index}")

    print(f"\n📊 CHOCH SIGNALS: {len(result.choch_signals)}")
    for choch in result.choch_signals[-3:]:
        print(f"   {choch.from_trend.value}→{choch.to_trend.value} @ {choch.level:.2f}")

    print(f"\n📊 RECENT:")
    print(f"   BOS Detected: {result.bos_detected}")
    print(f"   CHoCH Detected: {result.choch_detected}")

    print(f"\n📊 SUMMARY:")
    summary = summarize_bos_choch(df)
    for k, v in summary.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("✅ BOS/CHoCH test complete!")
