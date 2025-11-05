#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_meta_strategy_cycle.py
# ============================================================
from __future__ import annotations

from pathlib import Path

import polars as pl
from queen.strategies.meta_strategy_cycle import run_meta_cycle
from queen.settings import settings as SETTINGS


def test():
    # Use two demo symbols to ensure multiple rows
    parquet_path, jsonl_path, df = run_meta_cycle(["DEMO", "TEST"])

    assert (
        isinstance(parquet_path, Path) and parquet_path.exists()
    ), "Parquet not written"
    assert isinstance(jsonl_path, Path) and jsonl_path.exists(), "JSONL not written"

    # DF sanity
    assert not df.is_empty(), "Empty snapshot frame"
    required = {
        "timestamp",
        "symbol",
        "timeframe",
        "Tactical_Index",
        "Regime_State",
        "strategy_score",
        "entry_ok",
        "exit_ok",
        "risk_band",
    }
    assert required.issubset(
        set(df.columns)
    ), f"Missing columns: {required - set(df.columns)}"
    # Score ranges
    assert float(df["strategy_score"].min()) >= 0.0
    assert float(df["strategy_score"].max()) <= 1.0

    # Reload Parquet to ensure integrity
    df2 = pl.read_parquet(parquet_path)
    assert df2.shape[0] == df.shape[0], "Parquet row count mismatch"

    print("✅ smoke_meta_strategy_cycle: passed")


if __name__ == "__main__":
    test()
