#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_schema_adapter.py — v1.0
# ============================================================
from __future__ import annotations

import polars as pl

from queen.helpers.schema_adapter import (
    SCHEMA,
    finalize_candle_df,
    get_supported_intervals,
    to_candle_df,
    validate_interval,
)


def run_all():
    # schema presence
    assert isinstance(SCHEMA, dict), "SCHEMA should be a dict"

    intr = get_supported_intervals(intraday=True)
    hist = get_supported_intervals(intraday=False)
    assert "minutes" in intr or "hours" in intr, "intraday table should exist"
    assert "days" in hist or "weeks" in hist or "months" in hist, "historical table should exist"

    # validate a few common ranges if present
    if "minutes" in intr:
        assert validate_interval("minutes", 1, intraday=True) is True
    if "hours" in intr:
        assert validate_interval("hours", 1, intraday=True) is True
    if "days" in hist:
        assert validate_interval("days", 1, intraday=False) is True

    # frame build + finalize
    sample = [
        ["2025-01-01T09:15:00+05:30", 100, 110, 90, 105, 5000, 12],
        ["2025-01-01T09:20:00+05:30", 106, 108, 104, 107, 3200, 9],
    ]
    df = to_candle_df(sample, "DEMO")
    assert isinstance(df, pl.DataFrame) and df.height == 2
    out = finalize_candle_df(df, "DEMO", "ISIN123")
    assert "symbol" in out.columns and "isin" in out.columns
    print("✅ smoke_schema_adapter: passed")

if __name__ == "__main__":
    run_all()
