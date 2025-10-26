#!/usr/bin/env python3
# ============================================================
# queen/settings/timeframes.py — v8.4 (Single Owner: map + parsing + conversions)
# ============================================================
from __future__ import annotations

import math
from typing import Any, Dict, Tuple

# Friendly → fetcher-canonical
TIMEFRAME_MAP: Dict[str, str] = {
    "1m": "minutes:1",
    "3m": "minutes:3",
    "5m": "minutes:5",
    "10m": "minutes:10",
    "15m": "minutes:15",
    "30m": "minutes:30",
    "1h": "hours:1",
    "2h": "hours:2",
    "4h": "hours:4",
    "1d": "days:1",
    "1w": "weeks:1",
    "1mo": "months:1",
}

# Optional semantic presets for strategies
TIMEFRAMES: Dict[str, Dict[str, Any]] = {
    "intraday": {"unit": "minutes", "interval": 5, "lookback": 200, "sessions": 250},
    "daily": {"unit": "days", "interval": 1, "lookback": 250, "sessions": 250},
    "weekly": {"unit": "weeks", "interval": 1, "lookback": 52, "sessions": 52},
    "monthly": {"unit": "months", "interval": 1, "lookback": 120, "sessions": 120},
}


def normalize_tf(token: str) -> str:
    return (token or "").strip().lower()


def is_intraday(token: str) -> bool:
    s = normalize_tf(token)
    return s.endswith("m") or s.endswith("h")


def parse_tf(token: str) -> Tuple[str, int]:
    """'5m' → ('minutes', 5), '1mo' → ('months', 1)"""
    s = normalize_tf(token)
    if not s:
        raise ValueError("Empty timeframe token")

    if s.endswith("mo"):
        num = s[:-2]
        unit = "months"
    else:
        num, suf = s[:-1], s[-1:]
        unit = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}.get(suf)

    if unit is None or not num.isdigit() or int(num) <= 0:
        raise ValueError(f"Bad timeframe token: {token}")
    return unit, int(num)


def to_fetcher_interval(token: str) -> str:
    s = normalize_tf(token)
    if s in TIMEFRAME_MAP:
        return TIMEFRAME_MAP[s]
    unit, n = parse_tf(s)
    return f"{unit}:{n}"


def tf_to_minutes(token: str) -> int:
    unit, n = parse_tf(token)
    return (
        n
        if unit == "minutes"
        else n * 60
        if unit == "hours"
        else n * 60 * 24
        if unit == "days"
        else n * 60 * 24 * 7
        if unit == "weeks"
        else n * 60 * 24 * 30  # months (coarse)
    )


def validate_token(token: str) -> None:
    """Raise if token is not a valid timeframe string."""
    _ = parse_tf(token)  # will raise if invalid


def bars_for_days(token: str, days: int) -> int:
    """How many bars cover `days` of history at `token` (e.g., '5m','1d')."""
    validate_token(token)
    minutes = tf_to_minutes(token)
    return max(1, int(math.ceil(max(0, int(days)) * 1440 / minutes)))


def window_days_for_tf(token: str, bars: int) -> int:
    """Translate 'bars needed' into an approximate calendar-day window.

    Heuristic:
      - 1d:      bars + 20 (min 120)
      - 1w:      (bars + 6) * 7 (min 365)
      - 1mo:     (bars + 3) * 30 (min 720)
      - intraday: bars + 20 (min 120)
    """
    unit, n = parse_tf(token)
    if unit == "days":
        return max(bars + 20, 120)
    if unit == "weeks":
        return max((bars + 6) * 7, 365)
    if unit == "months":
        return max((bars + 3) * 30, 720)
    # minutes/hours → treat like intraday
    return max(bars + 20, 120)


def get_timeframe(name: str) -> Dict[str, Any]:
    return dict(TIMEFRAMES.get(name.lower(), {}))


def list_timeframes() -> list[str]:
    return list(TIMEFRAMES.keys())


if __name__ == "__main__":
    print("OK:", to_fetcher_interval("5m"), window_days_for_tf("1w", 60))
