#!/usr/bin/env python3
# ============================================================
# queen/cli/debug_fetch_unified.py — v1.0
# ------------------------------------------------------------
# Tiny sanity runner for fetch_unified:
#   1) Live intraday (no from/to)  → smart intraday
#   2) Intraday range              → historical intraday
#   3) Daily range                 → historical daily
#
# Usage:
#   python -m queen.cli.debug_fetch_unified --symbol VOLTAMP --date 2025-11-28 --interval 15
# ============================================================

from __future__ import annotations

import argparse
import asyncio
from datetime import date, timedelta
from typing import Optional

import polars as pl

from queen.fetchers.upstox_fetcher import fetch_unified
from queen.helpers.logger import log


def _summarize(label: str, df: pl.DataFrame) -> None:
    if df.is_empty():
        print(f"\n[{label}] rows=0 (empty)")
        return
    first = df["timestamp"][0]
    last = df["timestamp"][-1]
    print(
        f"\n[{label}] rows={df.height} | "
        f"first={first} | last={last} | cols={df.columns}"
    )


async def _run(
    symbol: str,
    day: str,
    interval_min: int,
    daily_lookback: int,
) -> None:
    interval_token = f"{interval_min}m"

    # 1) Live intraday (no from/to) → smart intraday
    log.info(
        f"[Debug] 1) Live intraday: {symbol} @ {interval_token} (no from/to → smart)"
    )
    df_live = await fetch_unified(
        symbol,
        mode="intraday",
        from_date=None,
        to_date=None,
        interval=interval_token,
    )
    _summarize("LIVE_INTRADAY", df_live)

    # 2) Intraday range (single day) → historical intraday window
    log.info(
        f"[Debug] 2) Intraday range: {symbol} {day}→{day} @ {interval_token} "
        "(→ historical minutes)"
    )
    df_intraday_range = await fetch_unified(
        symbol,
        mode="intraday",
        from_date=day,
        to_date=day,
        interval=interval_token,
    )
    _summarize("INTRADAY_RANGE", df_intraday_range)

    # 3) Daily range (N-day window) → historical daily candles
    end_d = date.fromisoformat(day)
    start_d = end_d - timedelta(days=daily_lookback)
    from_d = start_d.isoformat()
    to_d = end_d.isoformat()

    log.info(
        f"[Debug] 3) Daily range: {symbol} {from_d}→{to_d} @ 1d "
        "(→ historical daily)"
    )
    df_daily = await fetch_unified(
        symbol,
        mode="daily",
        from_date=from_d,
        to_date=to_d,
        interval="1d",
    )
    _summarize("DAILY_RANGE", df_daily)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sanity checker for fetch_unified (intraday live/range + daily)."
    )
    parser.add_argument(
        "--symbol",
        default="VOLTAMP",
        help="Symbol to test (default: VOLTAMP)",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Reference date (YYYY-MM-DD) for intraday/daily tests.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Intraday interval in minutes (default: 15).",
    )
    parser.add_argument(
        "--daily-lookback",
        type=int,
        default=20,
        help="Days lookback for daily-range test (default: 20).",
    )

    args = parser.parse_args()

    asyncio.run(
        _run(
            symbol=args.symbol,
            day=args.date,
            interval_min=args.interval,
            daily_lookback=args.daily_lookback,
        )
    )


if __name__ == "__main__":
    main()
