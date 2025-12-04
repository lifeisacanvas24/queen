#!/usr/bin/env python3
# queen/cli/debug_decisions.py — v0.2 (updated)
from __future__ import annotations

import argparse
from typing import Any, Dict

import polars as pl

from queen.cli.replay_actionable import ReplayConfig, replay_actionable
from queen.helpers.logger import log


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug decision/action_tag stream for a symbol."
    )
    parser.add_argument("--symbol", required=True, help="Symbol, e.g. FORCEMOT")
    parser.add_argument("--interval", type=int, default=15, help="Interval in minutes")
    parser.add_argument("--book", type=str, default="all", help="Book name (default: all).")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup bars (default:1).")
    args = parser.parse_args()

    sym = args.symbol.upper()
    cfg = ReplayConfig(
        symbol=sym,
        date_from=None,
        date_to=None,
        interval_min=args.interval,
        book=args.book,
        warmup=args.warmup,
        final_only=False,
        pos_mode="auto",
        auto_side="long",
    )

    log.info(f"[DebugDecisions] Replaying {sym} @ {args.interval}m (book={args.book})")

    payload: Dict[str, Any] = {}
    try:
        import asyncio  # lazy import
        payload = asyncio.run(replay_actionable(cfg))  # type: ignore
    except Exception as e:
        log.exception(f"[DebugDecisions] replay failed: {e}")
        print("[DebugDecisions] replay failed.")
        return

    rows = payload.get("rows") or []
    if not rows:
        print("[DebugDecisions] No rows returned.")
        return

    df = pl.DataFrame(rows)
    if "timestamp" in df.columns:
        df = df.sort("timestamp")

    # Updated wanted list (includes sim fields you requested)
    wanted = [
        "timestamp",
        "decision",
        "sim_effective_decision",
        "sim_ignored_signal",
        "sim_trade_id",
        "sim_trail_stop",
        "action_tag",
        "playbook",
        "time_bucket",
        "trend_bias",
        "trend_score",
        "vwap_zone",
        "cmp",
        "entry",
        "sim_side",
        "sim_qty",
        "sim_avg",
        "sim_pnl",
        "sim_total_pnl",
    ]
    cols = [c for c in wanted if c in df.columns]
    df = df.select(cols)

    print("\n=== Decision Stream Debug ===")
    print(df)
    print("================================\n")


if __name__ == "__main__":
    main()
