#!/usr/bin/env python3
# queen/cli/signal_summary.py
"""Light-weight script to print signal summary by sim_effective_decision (if present)."""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
from queen.helpers.logger import log


def main() -> None:
    parser = argparse.ArgumentParser(description="Signal summary (by sim_effective_decision).")
    parser.add_argument("--parquet", type=str, required=True)
    args = parser.parse_args()
    p = Path(args.parquet).expanduser().resolve()

    if not p.exists():
        print(f"[SignalSummary] Parquet not found: {p}")
        return

    df = pl.read_parquet(p)
    if "sim_effective_decision" not in df.columns:
        print("[SignalSummary] sim_effective_decision column not found in parquet.")
        return

    summ = (
        df.groupby(["symbol", "sim_effective_decision"])
        .agg(pl.len().alias("len"))
        .sort(["symbol", "sim_effective_decision"])
    )
    print("=== Signal Summary (by sim_effective_decision) ===")
    print(summ)
    print("================================")
