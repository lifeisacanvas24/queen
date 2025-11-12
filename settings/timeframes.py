#!/usr/bin/env python3
# ============================================================
# queen/settings/timeframes.py — v8.5 (Canonical TF definitions)
# ============================================================
from __future__ import annotations

import math
from typing import Any

# ------------------------------------------------------------
# 🕓 Canonical map: human-friendly → fetcher-canonical
# ------------------------------------------------------------
TIMEFRAME_MAP: dict[str, str] = {
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

# ------------------------------------------------------------
# 📊 Semantic presets (per strategy level)
# ------------------------------------------------------------
TIMEFRAMES: dict[str, dict[str, Any]] = {
    "intraday": {"unit": "minutes", "interval": 5, "lookback": 200, "sessions": 250},
    "daily":    {"unit": "days", "interval": 1, "lookback": 250, "sessions": 250},
    "weekly":   {"unit": "weeks", "interval": 1, "lookback": 52,  "sessions": 52},
    "monthly":  {"unit": "months", "interval": 1, "lookback": 120, "sessions": 120},
}

# ------------------------------------------------------------
# 🧠 Auto-backfill thresholds
# ------------------------------------------------------------
# How many rows we’d like before we stop “auto backfilling”.
# Tune per timeframe; keep this conservative so mornings don’t stall.
MIN_ROWS_AUTO_BACKFILL = {
    # minutes
    1:   180,  # ultra-short stream
    3:   140,
    5:   120,  # ~ first hour
    10:  100,
    15:  80,   # ~ yesterday+today lite
    30:  60,
    # hours (minutes form)
    60:  40,   # 1h
    120: 30,   # 2h
    240: 20,   # 4h
}

# If caller doesn’t specify a window, use this for the intraday historical bridge
DEFAULT_BACKFILL_DAYS_INTRADAY = 2

# ------------------------------------------------------------
# 🧩 Token parsing + conversions
# ------------------------------------------------------------
def normalize_tf(token: str) -> str:
    """Normalize timeframe tokens (e.g., '60m'→'1h', '15M'→'15m')."""
    t = (token or "").strip().lower()
    if not t:
        return t
    # unify "60m", "120m", etc. → hours
    if t.endswith("m"):
        try:
            n = int(t[:-1])
            if n % 60 == 0 and n >= 60:
                return f"{n // 60}h"
        except ValueError:
            pass
    return t

def is_intraday(token: str) -> bool:
    s = normalize_tf(token)
    return s.endswith("m") or s.endswith("h")

def parse_tf(token: str) -> tuple[str, int]:
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
    """Translate 'bars needed' into an approximate calendar-day window."""
    unit, _ = parse_tf(token)
    if unit == "days":
        return max(bars + 20, 120)
    if unit == "weeks":
        return max((bars + 6) * 7, 365)
    if unit == "months":
        return max((bars + 3) * 30, 720)
    # minutes/hours → treat like intraday
    return max(bars + 20, 120)

def get_timeframe(name: str) -> dict[str, Any]:
    return dict(TIMEFRAMES.get(name.lower(), {}))

def list_timeframes() -> list[str]:
    return list(TIMEFRAMES.keys())

# ------------------------------------------------------------
# 📦 Public exports
# ------------------------------------------------------------
__all__ = [
    "TIMEFRAME_MAP",
    "TIMEFRAMES",
    "MIN_ROWS_AUTO_BACKFILL",
    "DEFAULT_BACKFILL_DAYS_INTRADAY",
    "normalize_tf",
    "is_intraday",
    "parse_tf",
    "to_fetcher_interval",
    "tf_to_minutes",
    "validate_token",
    "bars_for_days",
    "window_days_for_tf",
    "get_timeframe",
    "list_timeframes",
]

if __name__ == "__main__":
    print("OK:", to_fetcher_interval("5m"), window_days_for_tf("1w", 60))
