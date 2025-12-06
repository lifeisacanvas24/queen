#!/usr/bin/env python3
# ============================================================
# queen/cli/test_guardrails.py — v1.0
# ------------------------------------------------------------
# Offline test harness to see how ladder guardrails behave on
# an existing scan_signals parquet (like /tmp/test.parquet).
#
# Usage:
#   python -m queen.cli.test_guardrails \
#       --parquet /tmp/test.parquet \
#       --symbol VOLTAMP
# ============================================================
from __future__ import annotations

import argparse

import polars as pl

from queen.helpers.io import read_parquet
from queen.services.ladder_guardrails import apply_ladder_guardrails
from queen.services.trade_state import update_trade_state_from_row


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test ladder guardrails on existing scan_signals parquet."
    )
    parser.add_argument("--parquet", required=True, help="Path to parquet file.")
    parser.add_argument("--symbol", required=True, help="Symbol to inspect (e.g. VOLTAMP).")
    parser.add_argument(
        "--interval",
        default=None,
        help="Optional interval filter (e.g. 15m). If omitted, uses all.",
    )
    args = parser.parse_args()

    df = read_parquet(args.parquet)
    if df.is_empty():
        print(f"[TestGuardrails] No data in parquet: {args.parquet}")
        return

    # Filter symbol / interval / sort by timestamp or row index
    sym = args.symbol.upper()
    df = df.filter(pl.col("symbol").str.to_uppercase() == sym)

    if args.interval:
        df = df.filter(pl.col("interval") == args.interval)

    if "timestamp" in df.columns:
        df = df.sort("timestamp")
    else:
        df = df.with_row_index("_idx").sort("_idx")

    if df.is_empty():
        print(f"[TestGuardrails] No rows for symbol={sym} in {args.parquet}")
        return

    print(f"[TestGuardrails] {df.height} rows for symbol={sym}")

    rows = df.to_dicts()

    print(
        "\n ts  | raw_dec | guarded | qty | sim_pnl | open_R | peak_R "
        "| adds | heat_R | note"
    )
    print("-" * 100)

    for r in rows:
        # raw decision & side from parquet
        raw_decision = (r.get("decision") or "").upper()
        sim_side = (r.get("sim_side") or "FLAT").upper()

        # 1) update trade state
        state = update_trade_state_from_row(r)

        # 2) apply guardrails
        guarded_decision, note = apply_ladder_guardrails(
            decision=raw_decision,
            side=sim_side,
            state=state,
        )

        ts = r.get("timestamp", "NA")
        qty = r.get("sim_qty", 0.0)
        sim_pnl = r.get("sim_pnl", 0.0)

        print(
            f"{ts!s:>4} | {raw_decision:7} | {guarded_decision:7} | "
            f"{qty:4.0f} | {sim_pnl:8.1f} | {state.open_R:6.2f} | "
            f"{state.peak_open_R:6.2f} | {state.ladder_adds_count:4d} | "
            f"{state.heat_R:6.2f} | {note or ''}"
        )


if __name__ == "__main__":
    main()
