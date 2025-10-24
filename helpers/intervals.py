#!/usr/bin/env python3
# ============================================================
# queen/helpers/intervals.py — v1.0 (Unified Interval Parser)
# ============================================================
"""Queen Interval Helpers
--------------------------
✅ Central place for all interval parsing logic
✅ Harmonizes human-friendly inputs like '5m', 15, '1h', etc.
✅ Exposes both minute-based (router) and API-style (Upstox) utilities
"""

from __future__ import annotations

import re

from queen.helpers.logger import log


# ------------------------------------------------------------
# ⏱️ Parse "5m", "15", 5 → 5 (minutes)
# ------------------------------------------------------------
def parse_minutes(value: str | int | float | None) -> int:
    """Return integer minutes from values like '5m', '15', 5."""
    if value is None:
        return 5
    if isinstance(value, (int, float)):
        return max(1, int(value))
    s = str(value).strip().lower()
    m = re.match(r"(\d+)", s.rstrip("m"))
    return max(1, int(m.group(1))) if m else 5


# ------------------------------------------------------------
# 🧭 Parse Upstox interval parameter for API (as string)
# ------------------------------------------------------------
def parse_upstox_interval(value: str | int | float | None) -> str:
    """Return normalized interval string for Upstox API (e.g., '1', '5')."""
    if value is None:
        return "1"
    if isinstance(value, (int, float)):
        return str(max(1, int(value)))
    s = str(value).strip().lower()
    # accept '5m', '15', '1minute', etc.
    s = s.replace("minute", "").replace("min", "").replace("m", "")
    m = re.match(r"(\d+)", s)
    if not m:
        log.warning(f"[Intervals] Invalid interval input: {value!r}, defaulting to '1'")
        return "1"
    return str(max(1, int(m.group(1))))


# ------------------------------------------------------------
# ⏳ Unit classification helper
# ------------------------------------------------------------
def classify_unit(interval: int) -> str:
    """Return appropriate Upstox unit ('minutes', 'hours', 'days') based on interval size."""
    if interval <= 300:
        return "minutes"
    if interval <= 7200:
        return "hours"
    return "days"


# ------------------------------------------------------------
# 🧪 Self-test
# ------------------------------------------------------------
if __name__ == "__main__":
    for val in ["1m", "15", 30, "2h", None]:
        print(
            f"{val!r} → minutes={parse_minutes(val)} | upstox={parse_upstox_interval(val)}"
        )
