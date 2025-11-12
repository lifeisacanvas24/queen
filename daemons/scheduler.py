#!/usr/bin/env python3
# ============================================================
# queen/daemons/scheduler.py — v3.0 (Async-Aware Market Daemon + Time-based Universe Refresh)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from queen.fetchers.fetch_router import run_router
from queen.helpers.instruments import load_instruments_df
from queen.helpers.logger import log
from queen.helpers.market import MarketClock, get_market_state, market_gate
from queen.settings import settings as SETTINGS

# ---------------- settings-driven defaults with safe fallbacks ----------------
_SCHED = getattr(SETTINGS, "SCHEDULER", {}) or {}

DEFAULT_INTERVAL_MINUTES = int(_SCHED.get("INTERVAL_MINUTES", 5))
DEFAULT_MODE = str(_SCHED.get("DEFAULT_MODE", "intraday")).lower()
DEFAULT_MAX_SYMBOLS = int(_SCHED.get("MAX_SYMBOLS", 250))
DEFAULT_REFRESH_MINUTES = int(_SCHED.get("UNIVERSE_REFRESH_MINUTES", 60))
DEFAULT_LOG_UNIVERSE_STATS = bool(_SCHED.get("LOG_UNIVERSE_STATS", True))


async def _load_symbols(mode: str, max_symbols: int, *, log_stats: bool = True) -> List[str]:
    df = load_instruments_df("INTRADAY" if mode == "intraday" else "MONTHLY")
    symbols = df["symbol"].head(max_symbols).to_list() if not df.is_empty() else []
    if log_stats:
        log.info(f"[Scheduler] universe size={len(symbols)} (mode={mode}, max={max_symbols})")
    return symbols


async def scheduler_loop(
    mode: str = DEFAULT_MODE,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
    *,
    refresh_minutes: int = DEFAULT_REFRESH_MINUTES,
    log_universe_stats: bool = DEFAULT_LOG_UNIVERSE_STATS,
) -> None:
    mode = (mode or "intraday").lower()
    interval_minutes = int(interval_minutes)
    max_symbols = int(max_symbols)
    refresh_minutes = int(refresh_minutes)

    log.info(
        f"[Scheduler] start | mode={mode} | interval={interval_minutes}m | "
        f"max={max_symbols} | refresh={refresh_minutes}m"
    )

    symbols: List[str] = await _load_symbols(mode, max_symbols, log_stats=log_universe_stats)

    clock = MarketClock(interval=interval_minutes, name="QueenClock", verbose=True)
    queue = clock.subscribe("Scheduler")

    last_refresh_at: Optional[datetime] = datetime.now()

    async with market_gate():
        log.info("[Scheduler] market open — entering active cycle")
        asyncio.create_task(clock.start())
        try:
            while True:
                tick = await queue.get()
                state = get_market_state()
                if not state.get("is_open"):
                    log.info(f"[Scheduler] market closed (gate={state['gate']}) — waiting")
                    queue.task_done()
                    continue

                # time-based universe refresh
                if refresh_minutes > 0 and last_refresh_at:
                    if datetime.now() - last_refresh_at >= timedelta(minutes=refresh_minutes):
                        try:
                            new_symbols = await _load_symbols(mode, max_symbols, log_stats=log_universe_stats)
                            if new_symbols != symbols:
                                added = [s for s in new_symbols if s not in symbols]
                                removed = [s for s in symbols if s not in new_symbols]
                                symbols = new_symbols
                                if log_universe_stats:
                                    log.info(
                                        f"[Scheduler] 🔄 universe refreshed: {len(symbols)} symbols "
                                        f"(+{len(added)}/-{len(removed)})"
                                    )
                            else:
                                if log_universe_stats:
                                    log.info("[Scheduler] universe refresh: no changes")
                        except Exception as e:
                            log.warning(f"[Scheduler] universe refresh failed → {e}")
                        finally:
                            last_refresh_at = datetime.now()

                today = datetime.now().strftime("%Y-%m-%d")
                interval_token = f"{interval_minutes}m" if mode == "intraday" else None
                log.info(
                    f"[Scheduler] run fetch_router | tick={tick} | {len(symbols)} syms | {interval_token}"
                )

                try:
                    await run_router(
                        symbols, mode=mode, from_date=today, to_date=today, interval=interval_token
                    )
                except Exception as e:
                    log.error(f"[Scheduler] fetch_router failed → {e}")
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            log.warning("[Scheduler] stopped by cancellation")
        except KeyboardInterrupt:
            log.info("[Scheduler] interrupted manually")


async def run_once(
    mode: str = DEFAULT_MODE,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
) -> None:
    mode = (mode or "intraday").lower()
    async with market_gate():
        symbols = await _load_symbols(mode, max_symbols, log_stats=True)
        today = datetime.now().strftime("%Y-%m-%d")
        interval_token = f"{interval_minutes}m" if mode == "intraday" else None
        log.info(f"[Scheduler] single cycle | {len(symbols)} syms | {interval_token}")
        await run_router(symbols, mode=mode, from_date=today, to_date=today, interval=interval_token)


def run_cli(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Queen Async Scheduler Daemon")
    p.add_argument("--mode", choices=["intraday", "daily"], default=DEFAULT_MODE)
    p.add_argument("--interval-minutes", type=int, default=DEFAULT_INTERVAL_MINUTES)
    p.add_argument("--max-symbols", type=int, default=DEFAULT_MAX_SYMBOLS)
    p.add_argument("--refresh-minutes", type=int, default=DEFAULT_REFRESH_MINUTES,
                   help="Reload universe every N minutes (0 to disable)")
    p.add_argument("--no-universe-stats", action="store_true",
                   help="Silence universe size/refresh logs")
    p.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = p.parse_args(argv)

    async def main():
        if args.once:
            await run_once(args.mode, args.interval_minutes, args.max_symbols)
        else:
            await scheduler_loop(
                args.mode,
                args.interval_minutes,
                args.max_symbols,
                refresh_minutes=args.refresh_minutes,
                log_universe_stats=(not args.no_universe_stats),
            )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    run_cli()
