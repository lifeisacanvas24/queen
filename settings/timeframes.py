#!/usr/bin/env python3
# ============================================================
# queen/settings/timeframes.py — Quant Timeframe Configuration (v8.0)
# ============================================================
"""Quant Timeframe Configuration
--------------------------------
🕒 Purpose:
    Defines standard timeframes, intervals, and lookback windows
    for all Quant Engine operations (fetchers, indicators, and strategy loops).

💡 Usage:
    from queen.settings import timeframes
    intraday_tf = timeframes.TIMEFRAMES["intraday"]
"""

from __future__ import annotations

from typing import Any, Dict

# ------------------------------------------------------------
# 🕒 Timeframe Configuration
# ------------------------------------------------------------
TIMEFRAMES: Dict[str, Dict[str, Any]] = {
    "intraday": {
        "unit": "minutes",
        "interval": 5,
        "lookback": 200,
        "sessions": 250,
        "_note": "Used for intraday scans; ensures sufficient ATR/RSI reliability.",
    },
    "daily": {
        "unit": "days",
        "interval": 1,
        "lookback": 250,
        "sessions": 250,
        "_note": "Standard daily timeframe; ensures full trading year coverage.",
    },
    "weekly": {
        "unit": "weeks",
        "interval": 1,
        "lookback": 52,
        "sessions": 52,
        "_note": "Weekly timeframe for swing and structure-level confirmation.",
    },
    "monthly": {
        "unit": "months",
        "interval": 1,
        "lookback": 120,
        "sessions": 120,
        "_note": "Monthly timeframe for macro bias and trend stability scans.",
    },
}


# ------------------------------------------------------------
# 🧠 Helper Functions
# ------------------------------------------------------------
def get_timeframe(name: str) -> Dict[str, Any]:
    """Retrieve configuration block for a given timeframe."""
    return TIMEFRAMES.get(name.lower(), {})


def list_timeframes() -> list[str]:
    """List all supported timeframe keys."""
    return list(TIMEFRAMES.keys())


# ------------------------------------------------------------
# ✅ Self-Test
# ------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    print("🕒 Queen Timeframe Configuration")
    pprint(list_timeframes())
    pprint(get_timeframe("daily"))
