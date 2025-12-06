#!/usr/bin/env python3
# ============================================================
# queen/cli/signal_summary.py — v1.0
# ------------------------------------------------------------
# Summarise scan_signals parquet by:
#   • (symbol × decision)
#   • (symbol × playbook × action_tag)
#   • (symbol × sim_effective_decision) if sim columns exist.
#
# Example:
#   python -m queen.cli.signal_summary --parquet /tmp/scan_15m.parquet
# ============================================================
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import polars as pl

from queen.helpers.logger import log


def _load_df(parquet_path: Path) -> pl.DataFrame:
    log.info(f"[SignalSummary] Loading parquet → {parquet_path}")
    df = pl.read_parquet(parquet_path)
    if "symbol" in df.columns:
        df = df.with_columns(pl.col("symbol").cast(pl.Utf8, strict=False))
    return df


def _print_decision_summary(df: pl.DataFrame) -> None:
    if "decision" not in df.columns:
        print("[SignalSummary] Column 'decision' not found; skipping raw summary.")
        return

    summary = (
        df.filter(pl.col("decision").is_not_null())
        .group_by(["symbol", "decision"])
        .agg(pl.len().alias("len"))
        .sort(["symbol", "decision"])
    )

    print("\n=== Signal Summary (symbol × decision × len) ===")
    print(summary)
    print("===============================================")


def _print_playbook_summary(df: pl.DataFrame) -> None:
    if not {"playbook", "action_tag"}.issubset(set(df.columns)):
        print("[SignalSummary] Columns 'playbook'/'action_tag' missing; skipping playbook summary.")
        return

    summary = (
        df.filter(pl.col("playbook").is_not_null())
        .group_by(["symbol", "playbook", "action_tag"])
        .agg(pl.len().alias("len"))
        .sort(["symbol", "playbook", "action_tag"])
    )

    print("\n=== Playbook Summary (symbol × playbook × action_tag × len) ===")
    print(summary)
    print("================================================================")


def _print_effective_summary(df: pl.DataFrame) -> None:
    if "sim_effective_decision" not in df.columns:
        print(
            "[SignalSummary] Column 'sim_effective_decision' not found; "
            "skipping sim-effective summary."
        )
        return

    summary = (
        df.filter(pl.col("sim_effective_decision").is_not_null())
        .group_by(["symbol", "sim_effective_decision"])
        .agg(pl.len().alias("len"))
        .sort(["symbol", "sim_effective_decision"])
    )

    print("\n=== Signal Summary (by sim_effective_decision) ===")
    print(summary)
    print("================================")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarise scan_signals parquet by decisions / playbooks."
    )
    parser.add_argument(
        "--parquet",
        type=str,
        required=True,
        help="Path to scan_signals parquet.",
    )

    args: Any = parser.parse_args()
    p = Path(args.parquet).expanduser().resolve()

    if not p.exists():
        print(f"[SignalSummary] Parquet not found: {p}")
        return

    df = _load_df(p)
    if df.is_empty():
        print("[SignalSummary] Parquet has no rows; nothing to summarise.")
        return

    _print_decision_summary(df)
    _print_playbook_summary(df)
    _print_effective_summary(df)


if __name__ == "__main__":
    main()
