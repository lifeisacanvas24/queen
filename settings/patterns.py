#!/usr/bin/env python3
# ============================================================
# queen/settings/patterns.py — Pattern Recognition Config (v8.0)
# ============================================================
"""Quant Pattern Recognition Library
-------------------------------------
🕯️ Purpose:
    Defines all Japanese and cumulative chart patterns,
    their minimum candles, contextual lookbacks, and notes.

💡 Usage:
    from queen.settings import patterns
    hammer = patterns.JAPANESE["hammer"]
"""

from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# 🕯️ Japanese Candlestick Patterns
# ------------------------------------------------------------
JAPANESE: Dict[str, Dict[str, Any]] = {
    "hammer": {
        "candles_required": 1,
        "contexts": {
            "intraday_5m": {"timeframe": "5m", "lookback": 40},
            "intraday_15m": {"timeframe": "15m", "lookback": 40},
            "daily": {"timeframe": "1D", "lookback": 15},
        },
        "_note": "Hammer: Bullish reversal; long lower wick; confirms best with volume uptick.",
    },
    "shooting_star": {
        "candles_required": 1,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 40},
            "daily": {"timeframe": "1D", "lookback": 15},
        },
        "_note": "Shooting Star: Bearish reversal; long upper wick; confirms with OBV divergence.",
    },
    "doji": {
        "candles_required": 1,
        "contexts": {
            "intraday_5m": {"timeframe": "5m", "lookback": 25},
            "intraday_15m": {"timeframe": "15m", "lookback": 25},
            "daily": {"timeframe": "1D", "lookback": 10},
        },
        "_note": "Doji: Indecision marker; confirmation needed from next candle body expansion.",
    },
    "engulfing_bullish": {
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 30},
            "hourly_1h": {"timeframe": "1H", "lookback": 25},
            "daily": {"timeframe": "1D", "lookback": 15},
            "weekly": {"timeframe": "1W", "lookback": 8},
        },
        "_note": "Bullish Engulfing: Full-body reversal; OBV uptick strengthens reliability.",
    },
    "engulfing_bearish": {
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 30},
            "hourly_1h": {"timeframe": "1H", "lookback": 25},
            "daily": {"timeframe": "1D", "lookback": 15},
            "weekly": {"timeframe": "1W", "lookback": 8},
        },
        "_note": "Bearish Engulfing: Marks exhaustion after extended rally; OBV contraction confirms.",
    },
    "inside_bar": {
        "candles_required": 2,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 35},
            "daily": {"timeframe": "1D", "lookback": 20},
        },
        "_note": "Inside Bar: Consolidation before expansion; strong precursor for SPS buildup.",
    },
    "morning_star": {
        "candles_required": 3,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 50},
            "daily": {"timeframe": "1D", "lookback": 25},
        },
        "_note": "Morning Star: 3-bar bullish reversal sequence; ideal near lower CPR zone.",
    },
    "evening_star": {
        "candles_required": 3,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 50},
            "daily": {"timeframe": "1D", "lookback": 25},
        },
        "_note": "Evening Star: 3-bar bearish reversal; confirms with RSI > 65 dropping to < 50.",
    },
}


# ------------------------------------------------------------
# 📈 Cumulative / Structural Patterns
# ------------------------------------------------------------
CUMULATIVE: Dict[str, Dict[str, Any]] = {
    "double_bottom": {
        "candles_required": 30,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 120},
            "hourly_1h": {"timeframe": "1H", "lookback": 60},
            "daily": {"timeframe": "1D", "lookback": 50},
            "weekly": {"timeframe": "1W", "lookback": 26},
        },
        "_note": "Double Bottom: Mid/long-term accumulation base; confirms with OBV breakout.",
    },
    "double_top": {
        "candles_required": 30,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 120},
            "hourly_1h": {"timeframe": "1H", "lookback": 60},
            "daily": {"timeframe": "1D", "lookback": 50},
            "weekly": {"timeframe": "1W", "lookback": 26},
        },
        "_note": "Double Top: Distribution zone; matches high RPS readings.",
    },
    "cup_handle": {
        "candles_required": 60,
        "contexts": {
            "hourly_1h": {"timeframe": "1H", "lookback": 90},
            "daily": {"timeframe": "1D", "lookback": 90},
            "weekly": {"timeframe": "1W", "lookback": 52},
        },
        "_note": "Cup & Handle: Classic breakout structure; aligns with SPS > 1.0 and MCS > 0.5.",
    },
    "head_shoulders": {
        "candles_required": 40,
        "contexts": {
            "hourly_1h": {"timeframe": "1H", "lookback": 80},
            "daily": {"timeframe": "1D", "lookback": 60},
            "weekly": {"timeframe": "1W", "lookback": 26},
        },
        "_note": "Head & Shoulders: Bearish reversal; confirm with RPS > 1.0 and RSI divergence.",
    },
    "inverse_head_shoulders": {
        "candles_required": 40,
        "contexts": {
            "hourly_1h": {"timeframe": "1H", "lookback": 80},
            "daily": {"timeframe": "1D", "lookback": 60},
            "weekly": {"timeframe": "1W", "lookback": 26},
        },
        "_note": "Inverse H&S: Bullish reversal; confirm with OBV rising and CPR breakout.",
    },
    "ascending_triangle": {
        "candles_required": 25,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 60},
            "daily": {"timeframe": "1D", "lookback": 30},
            "weekly": {"timeframe": "1W", "lookback": 15},
        },
        "_note": "Ascending Triangle: Bullish continuation; forms during SPS buildup.",
    },
    "descending_triangle": {
        "candles_required": 25,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 60},
            "daily": {"timeframe": "1D", "lookback": 30},
            "weekly": {"timeframe": "1W", "lookback": 15},
        },
        "_note": "Descending Triangle: Bearish continuation; confirms with RPS elevation.",
    },
    "vcp": {
        "candles_required": 40,
        "contexts": {
            "intraday_15m": {"timeframe": "15m", "lookback": 80},
            "daily": {"timeframe": "1D", "lookback": 40},
            "weekly": {"timeframe": "1W", "lookback": 20},
        },
        "_note": "VCP (Volatility Contraction Pattern): Bullish breakout trigger; OBV rising and CPR tightening.",
    },
}


# ------------------------------------------------------------
# 🧠 Helper Functions
# ------------------------------------------------------------
def get_pattern(group: str, name: str) -> Dict[str, Any]:
    """Retrieve pattern definition safely."""
    group_dict = {"japanese": JAPANESE, "cumulative": CUMULATIVE}
    return group_dict.get(group.lower(), {}).get(name.lower(), {})


def list_patterns(group: str = None) -> list[str]:
    """List available patterns."""
    if not group:
        return list(JAPANESE.keys()) + list(CUMULATIVE.keys())
    if group.lower() == "japanese":
        return list(JAPANESE.keys())
    if group.lower() == "cumulative":
        return list(CUMULATIVE.keys())
    return []


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🧩 Queen Pattern Library")
    pprint(list_patterns("japanese"))
    pprint(get_pattern("cumulative", "double_bottom"))
