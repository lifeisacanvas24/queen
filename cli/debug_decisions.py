#!/usr/bin/env python3
# ============================================================
# queen/cli/debug_decisions.py — v0.1
# ------------------------------------------------------------
# Bar-by-bar decision vs action_tag vs context for a symbol.
# Example:
#   python -m queen.cli.debug_decisions --symbol FORCEMOT --interval 15
# ============================================================
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
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Intraday interval in minutes (default: 15).",
    )
    parser.add_argument(
        "--book",
        type=str,
        default="all",
        help="Book name (default: all).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warmup bars before emitting rows (default: 1).",
    )
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

    log.info(
        f"[DebugDecisions] Replaying {sym} @ {args.interval}m "
        f"(book={args.book}, warmup={args.warmup})"
    )

    payload: Dict[str, Any] = {}
    try:
        payload = asyncio.run(replay_actionable(cfg))  # type: ignore[name-defined]
    except NameError:
        # Lazy import to avoid circulars if needed
        import asyncio  # noqa: WPS433

        payload = asyncio.run(replay_actionable(cfg))

    rows = payload.get("rows") or []
    if not rows:
        print("[DebugDecisions] No rows returned.")
        return

    df = pl.DataFrame(rows)

    if "timestamp" in df.columns:
        df = df.sort("timestamp")

    wanted = [
        "timestamp",
        "decision",
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
