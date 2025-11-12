#!/usr/bin/env python3
# ============================================================
# queen/helpers/intervals.py — v2.1 (Delegates to timeframes; settings-driven defaults)
# ============================================================
"""Queen Interval Helpers (DRY/forward-only)
--------------------------------------------
✅ Single source of truth: queen.settings.timeframes
✅ Human tokens like '5m','1h','1d','1w','1mo' normalized via TF
✅ Accepts canonical strings like 'minutes:5', 'hours:1' and coerces to tokens
✅ Exposes:
    - parse_minutes(token_or_num)
    - to_fetcher_interval(token_or_num)
    - classify_unit(token_or_num)
    - to_token(minutes_or_token)
    - is_intraday(token_or_num)
"""

from __future__ import annotations

from typing import Union

import queen.settings.settings as S  # settings-driven defaults
from queen.settings.timeframes import (
    normalize_tf,
    parse_tf,
)
from queen.settings.timeframes import (
    to_fetcher_interval as _tf_to_fetcher_interval,
)

Tokenish = Union[str, int, float, None]

# ------------------------------------------------------------
# 🔧 Conversion helpers
# ------------------------------------------------------------
def _coerce_token(v: Tokenish) -> str:
    """Turn legacy minute numbers and canonical 'unit:n' into normalized tokens."""
    if v is None:
        # settings-driven default (falls back to "5m")
        return str(S.SCHEDULER.get("default_interval", "5m")).lower()

    if isinstance(v, (int, float)):
        # legacy: treat numeric as minutes
        return f"{max(1, int(v))}m"

    s = str(v).strip().lower()

    # accept canonical like "minutes:5" / "hours:1" / "days:1" / "weeks:1" / "months:1"
    if ":" in s:
        unit, num = s.split(":", 1)
        num = num.strip()
        if num.isdigit():
            if unit == "minutes":
                return f"{num}m"
            if unit == "hours":
                return f"{num}h"
            if unit == "days":
                return f"{num}d"
            if unit == "weeks":
                return f"{num}w"
            if unit == "months":
                return f"{num}mo"

    return s

# ------------------------------------------------------------
# 🔁 Public helpers
# ------------------------------------------------------------
def parse_minutes(value: Tokenish) -> int:
    """Return total minutes for an intraday token/number."""
    tf = normalize_tf(_coerce_token(value))
    unit, n = parse_tf(tf)
    if unit == "minutes":
        return int(n)
    if unit == "hours":
        return int(n) * 60
    raise ValueError(f"parse_minutes only supports intraday tokens; got {tf!r} ({unit})")

def to_fetcher_interval(value: Tokenish) -> str:
    """Canonical interval string for fetchers (delegates to TF)."""
    tf = normalize_tf(_coerce_token(value))
    return _tf_to_fetcher_interval(tf)

def classify_unit(value: Tokenish) -> str:
    """Return 'minutes' | 'hours' | 'days' | 'weeks' | 'months'."""
    tf = normalize_tf(_coerce_token(value))
    unit, _ = parse_tf(tf)
    return unit

def to_token(minutes: int) -> str:
    """Return canonical timeframe token for a given number of minutes.
    - Multiples of 60 → hours ("1h", "2h", ...)
    - Others → minutes ("5m", "15m", ...)
    """
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    if minutes % 60 == 0:
        h = minutes // 60
        return f"{h}h"
    return f"{int(minutes)}m"

def is_intraday(token: Tokenish) -> bool:
    """Return True if token represents minutes/hours (intraday)."""
    unit = classify_unit(token)
    return unit in {"minutes", "hours"}

# ------------------------------------------------------------
# 📦 Public exports
# ------------------------------------------------------------
__all__ = [
    "parse_minutes",
    "to_fetcher_interval",
    "classify_unit",
    "to_token",
    "is_intraday",
]

# ------------------------------------------------------------
# 🧪 Self-test
# ------------------------------------------------------------
if __name__ == "__main__":
    print("minutes 15  → token:", to_token(15))                 # 15 → "15m"
    print("minutes 60  → token:", to_token(60))                 # 60 → "1h"
    print("fetcher '1w' →", to_fetcher_interval("1w"))          # "weeks:1"
    print("unit    '1mo'→", classify_unit("1mo"))               # "months"
    print("parse   '30m'→", parse_minutes("30m"))               # 30
    print("parse   '1h' →", parse_minutes("1h"))                # 60
    print("is_intraday('4h'):", is_intraday("4h"))              # True
    print("is_intraday('1d'):", is_intraday("1d"))              # False
