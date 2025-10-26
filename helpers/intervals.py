#!/usr/bin/env python3
# ============================================================
# queen/helpers/intervals.py — v2.0 (Delegates to timeframes)
# ============================================================
"""Queen Interval Helpers (DRY/forward-only)
--------------------------------------------
✅ Single source of truth: queen.settings.timeframes
✅ Human tokens like '5m','1h','1d','1w','1mo' normalized via TF
✅ Exposes:
    - parse_minutes(token_or_num): intraday minutes (raises on non-intraday)
    - to_fetcher_interval(token_or_num): canonical 'minutes:15' / 'days:1' / ...
    - classify_unit(token_or_num): 'minutes' | 'hours' | 'days' | 'weeks' | 'months'
    - to_token(minutes_or_token): coerce legacy minute ints to tokens (e.g., 15 -> '15m')
"""

from __future__ import annotations

from typing import Union

from queen.settings.timeframes import (
    normalize_tf,
    parse_tf,
)
from queen.settings.timeframes import (
    to_fetcher_interval as _tf_to_fetcher_interval,
)

Tokenish = Union[str, int, float, None]


def _coerce_token(v: Tokenish) -> str:
    """Turn legacy minute numbers into tokens; pass tokens through."""
    if v is None:
        return "5m"
    if isinstance(v, (int, float)):
        return f"{max(1, int(v))}m"
    return str(v)


def parse_minutes(value: Tokenish) -> int:
    """Return total minutes for an intraday token/number.

    Raises:
        ValueError: if the token is not minutes/hours (i.e., daily/weekly/monthly).

    """
    tf = normalize_tf(_coerce_token(value))
    unit, n = parse_tf(tf)  # e.g., ('minutes', 15) or ('hours', 1) or ('days', 1)...
    if unit == "minutes":
        return int(n)
    if unit == "hours":
        return int(n) * 60
    raise ValueError(
        f"parse_minutes only supports intraday tokens; got {tf!r} ({unit})"
    )


def to_fetcher_interval(value: Tokenish) -> str:
    """Canonical interval string for fetchers (delegates to TF)."""
    tf = normalize_tf(_coerce_token(value))
    return _tf_to_fetcher_interval(tf)


def classify_unit(value: Tokenish) -> str:
    """Return 'minutes' | 'hours' | 'days' | 'weeks' | 'months'."""
    tf = normalize_tf(_coerce_token(value))
    unit, _ = parse_tf(tf)
    return unit


def to_token(value: Tokenish) -> str:
    """Coerce legacy minute ints into a normalized token string."""
    return normalize_tf(_coerce_token(value))


# ------------------------------------------------------------
# 🧪 Self-test
# ------------------------------------------------------------
if __name__ == "__main__":
    print("token:", to_token(15))
    print("minutes:", parse_minutes("30m"))
    print("fetcher:", to_fetcher_interval("1w"))
    print("unit:", classify_unit("1mo"))
