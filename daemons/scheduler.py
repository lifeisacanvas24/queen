#!/usr/bin/env python3
# ============================================================
# queen/daemons/scheduler.py — v2.4 (Async-Aware Market Daemon)
# ============================================================
"""Queen Scheduler Daemon

✅ Runs timed fetch cycles (intraday/daily)
✅ Market-gate aware (blocks until open)
✅ Uses MarketClock ticks to align runs to bar closes
✅ settings.py-driven universe via instruments loader
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from typing import List

from queen.fetchers.fetch_router import run_router
from queen.helpers.instruments import load_instruments_df
from queen.helpers.logger import log
from queen.helpers.market import (
    MarketClock,
    get_market_state,
    market_gate,
)

DEFAULT_INTERVAL_MINUTES = 5
DEFAULT_MODE = "intraday"
DEFAULT_MAX_SYMBOLS = 250


async def scheduler_loop(
    mode: str = DEFAULT_MODE,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
) -> None:
    mode = (mode or "intraday").lower()
    log.info(
        f"[Scheduler] start | mode={mode} | interval={interval_minutes}m | max={max_symbols}"
    )

    df = load_instruments_df("INTRADAY" if mode == "intraday" else "MONTHLY")
    symbols: List[str] = (
        df["symbol"].head(max_symbols).to_list() if not df.is_empty() else []
    )
    log.info(f"[Scheduler] universe size={len(symbols)}")

    clock = MarketClock(interval=interval_minutes, name="QueenClock", verbose=True)
    queue = clock.subscribe("Scheduler")

    async with market_gate():
        log.info("[Scheduler] market open — entering active cycle")
        asyncio.create_task(clock.start())

        while True:
            tick = await queue.get()
            try:
                state = get_market_state()
                if not state["is_open"]:
                    log.info(
                        f"[Scheduler] market closed (gate={state['gate']}) — waiting"
                    )
                    continue

                today = datetime.now().strftime("%Y-%m-%d")
                from_date = to_date = today

                if mode == "daily":
                    log.info(
                        "[Scheduler] daily mode during session — EOD may not be available yet"
                    )

                # IMPORTANT: pass intraday interval to router so fetcher uses it
                interval_token = f"{interval_minutes}m" if mode == "intraday" else None

                log.info(
                    f"[Scheduler] run fetch_router | tick={tick} | n={len(symbols)} | mode={mode} | date={today} | interval={interval_token or 'default'}"
                )
                try:
                    await run_router(
                        symbols,
                        mode=mode,
                        from_date=from_date,
                        to_date=to_date,
                        interval=interval_token,
                    )
                except Exception as e:
                    log.error(f"[Scheduler] fetch_router failed → {e}")
            finally:
                queue.task_done()


async def run_once(
    mode: str = DEFAULT_MODE,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
):
    mode = (mode or "intraday").lower()
    async with market_gate():
        df = load_instruments_df("INTRADAY" if mode == "intraday" else "MONTHLY")
        symbols = df["symbol"].head(max_symbols).to_list() if not df.is_empty() else []
        today = datetime.now().strftime("%Y-%m-%d")
        interval_token = f"{interval_minutes}m" if mode == "intraday" else None
        log.info(
            f"[Scheduler] single cycle | n={len(symbols)} | mode={mode} | date={today} | interval={interval_token or 'default'}"
        )
        await run_router(
            symbols, mode=mode, from_date=today, to_date=today, interval=interval_token
        )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Queen Async Scheduler Daemon")
    p.add_argument("--mode", choices=["intraday", "daily"], default=DEFAULT_MODE)
    p.add_argument("--interval-minutes", type=int, default=DEFAULT_INTERVAL_MINUTES)
    p.add_argument("--max-symbols", type=int, default=DEFAULT_MAX_SYMBOLS)
    p.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    return p


def run_cli(argv: list[str] | None = None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    async def _main():
        if args.once:
            await run_once(args.mode, args.interval_minutes, args.max_symbols)
        else:
            await scheduler_loop(args.mode, args.interval_minutes, args.max_symbols)

    asyncio.run(_main())


if __name__ == "__main__":
    run_cli()
