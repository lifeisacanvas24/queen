#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_intervals.py — v1.2 (TF normalization sanity)
# ============================================================

from __future__ import annotations

from queen.helpers.intervals import (
    classify_unit,
    is_intraday,
    parse_minutes,
    to_fetcher_interval,
    to_token,
)
from queen.settings.timeframes import TIMEFRAME_MAP, normalize_tf, parse_tf

INTRADAY_TOKENS = ["1m", "3m", "5m", "10m", "15m", "30m", "1h", "2h", "4h"]
DAILY_PLUS_TOKENS = ["1d", "1w", "1mo"]
ALL_TOKENS = INTRADAY_TOKENS + DAILY_PLUS_TOKENS

def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)

def test_intraday_roundtrip_minutes_to_token() -> None:
    cases = [(1, "1m"), (3, "3m"), (5, "5m"), (10, "10m"), (15, "15m"),
             (30, "30m"), (60, "1h"), (120, "2h")]
    for minutes, expected in cases:
        got = to_token(minutes)
        _assert(got == expected, f"{minutes} → {got} (expected {expected})")
        mins = parse_minutes(got)
        _assert(mins == minutes, f"parse_minutes({got}) → {mins} (expected {minutes})")

def test_parse_minutes_intraday_only() -> None:
    for t in INTRADAY_TOKENS:
        _assert(isinstance(parse_minutes(t), int), f"{t} should parse to int")
    for t in DAILY_PLUS_TOKENS:
        try:
            parse_minutes(t)
            raise AssertionError(f"parse_minutes({t}) should fail")
        except ValueError:
            pass

def test_fetcher_interval_canonical() -> None:
    for t in ALL_TOKENS:
        tf = normalize_tf(t)
        unit, n = parse_tf(tf)
        expected = TIMEFRAME_MAP.get(tf, f"{unit}:{n}")
        got = to_fetcher_interval(tf)
        _assert(got == expected, f"{t} → {got} (expected {expected})")

def test_classify_unit_consistency() -> None:
    for t in ALL_TOKENS:
        unit_from_classify = classify_unit(t)
        unit_from_parse, _ = parse_tf(normalize_tf(t))
        _assert(unit_from_classify == unit_from_parse, f"{t}: {unit_from_classify} != {unit_from_parse}")

def test_is_intraday_flag() -> None:
    for t in INTRADAY_TOKENS:
        _assert(is_intraday(t) is True, f"{t} should be intraday")
    for t in DAILY_PLUS_TOKENS:
        _assert(is_intraday(t) is False, f"{t} should NOT be intraday")

def run_all():
    test_intraday_roundtrip_minutes_to_token()
    test_parse_minutes_intraday_only()
    test_fetcher_interval_canonical()
    test_classify_unit_consistency()
    test_is_intraday_flag()
    print("✅ smoke_intervals: passed")

if __name__ == "__main__":
    run_all()
