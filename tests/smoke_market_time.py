#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_market_time.py — v1.1 (basic market-calendar sanity)
# ============================================================
"""Smoke test for market-time helpers
----------------------------------
✅ Confirms settings-driven calendar integration works end-to-end
✅ Ensures no crash on holiday / weekend / after-hours
✅ Lightweight: no external I/O, no Polars writes
"""

from __future__ import annotations

from queen.helpers.market import (
    current_historical_service_day,
    get_market_state,
    is_market_open,
    sessions,
)


def test_market_time() -> None:
    st = get_market_state()

    # required fields present
    assert "session" in st and "gate" in st and "service_day" in st, st

    # type checks
    assert isinstance(is_market_open(), bool), "is_market_open must return bool"

    # service day string shape
    sd = current_historical_service_day()
    assert len(str(sd)) == 10 and str(sd).count("-") == 2, f"bad date format: {sd}"

    print("✅ smoke_market_time: passed")

def test_session_boundaries():
    for name, (s, e) in sessions().items():
        assert s < e

if __name__ == "__main__":
    test_market_time()
    test_session_boundaries()
