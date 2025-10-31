#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_master_index.py
# Asserts master index is non-empty and has core kinds.
# ============================================================

from __future__ import annotations

import polars as pl
from queen.technicals.master_index import master_index


def test():
    df = master_index()
    assert isinstance(df, pl.DataFrame), "master_index() must return a Polars DataFrame"
    assert not df.is_empty(), "master index should not be empty"

    # basic schema
    assert set(df.columns) == {
        "kind",
        "name",
        "module",
    }, f"Unexpected columns: {df.columns}"

    kinds = set(map(str.lower, df["kind"].to_list()))
    assert {"indicator", "signal"}.issubset(kinds), f"Missing core kinds in: {kinds}"

    print("✅ smoke_master_index: passed")


if __name__ == "__main__":
    test()
