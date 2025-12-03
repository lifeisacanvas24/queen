#!/usr/bin/env python3
# ============================================================
# queen/fetchers/fetch_router.py — v9.8 (DRY Intraday Routing)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import polars as pl

from queen.fetchers.upstox_fetcher import fetch_unified
from queen.helpers import io
from queen.helpers.fetch_utils import warn_if_same_day_eod
from queen.helpers.instruments import load_instruments_df
from queen.helpers.intervals import parse_minutes
from queen.helpers.logger import log
from queen.helpers.market import (
    current_historical_service_day,
    get_market_state,
    sleep_until_next_candle,
)
from queen.settings import settings as SETTINGS

# ============================================================
# ⚙️ Settings-driven config
# ============================================================
PATHS = SETTINGS.PATHS
EXPORT_DIR: Path = PATHS["EXPORTS"]
FETCH_CFG = SETTINGS.FETCH
SCHED_CFG = SETTINGS.SCHEDULER
DEFAULTS = SETTINGS.DEFAULTS

MAX_CONCURRENCY = int(FETCH_CFG.get("MAX_WORKERS", 8))
BATCH_SIZE = int(FETCH_CFG.get("BATCH_SIZE", 50))
EXPORT_FORMAT = (DEFAULTS.get("EXPORT_FORMAT") or "parquet").lower()
DEFAULT_INTERVAL_MIN = parse_minutes(SCHED_CFG.get("DEFAULT_INTERVAL", "5m"))

# ============================================================
# 🧱 Utility Helpers
# ============================================================
def _chunk_list(data: List[str], n: int) -> List[List[str]]:
    """Split list into chunks of size n."""
    if n <= 0:
        return [data]
    return [data[i : i + n] for i in range(0, len(data), n)]


def _generate_output_path(mode: str) -> Path:
    """Return file path for saving batch output."""
    folder = EXPORT_DIR / "fetch_outputs" / mode.lower()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return folder / f"{name}.{EXPORT_FORMAT}"


async def _save_results(results: Dict[str, pl.DataFrame], out_path: Path) -> None:
    """Save consolidated results in selected format."""
    dfs = [
        df
        for df in results.values()
        if isinstance(df, pl.DataFrame) and not df.is_empty()
    ]
    if not dfs:
        log.warning("[Router] No valid dataframes to save.")
        return

    combined = pl.concat(dfs, how="vertical_relaxed")

    match EXPORT_FORMAT:
        case "parquet":
            io.write_parquet(out_path, combined)
        case "csv":
            io.write_csv(out_path, combined)
        case "json":
            io.write_json(out_path, combined)
        case _:
            io.write_parquet(out_path.with_suffix(".parquet"), combined)
            log.warning(
                f"[Router] Unknown export format '{EXPORT_FORMAT}', wrote parquet instead."
            )

    log.info(f"[Router] 💾 Saved results → {out_path}")

# ============================================================
# ⚡ Async Fetch Logic (thin wrapper around fetch_unified)
# ============================================================
async def _fetch_symbol(
    symbol,
    mode,
    from_date,
    to_date,
    interval,
    sem,
    **kwargs,
) -> pl.DataFrame:
    async with sem:
        start = time.perf_counter()
        try:
            df = await fetch_unified(symbol, mode, from_date, to_date, interval, **kwargs)
            log.info(
                f"[Fetch] ✅ {symbol}: {0 if df.is_empty() else len(df)} rows | "
                f"{time.perf_counter() - start:.2f}s"
            )
            return df
        except Exception as e:
            log.error(f"[Fetch] ❌ {symbol} failed → {e}")
            return pl.DataFrame()


async def _fetch_batch(
    symbols,
    mode,
    from_date,
    to_date,
    interval,
) -> Dict[str, pl.DataFrame]:
    """Batch wrapper — policy-free; all smartness lives in upstox_fetcher."""
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    tasks = (
        _fetch_symbol(
            sym,
            mode,
            from_date,
            to_date,
            interval,
            sem,
        )
        for sym in symbols
    )
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        sym: (res if isinstance(res, pl.DataFrame) else pl.DataFrame())
        for sym, res in zip(symbols, results)
    }

# ============================================================
# 🚀 Main Orchestrator (preferred entry) — NON-RECURSIVE
# ============================================================
async def run_router(
    symbols: Sequence[str],
    mode: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    interval: str | int | None = None,
    use_gate: bool = True,  # if True and intraday: run only when market is LIVE
) -> None:
    """Run a single fetch cycle over `symbols` (no recursion, no looping)."""
    symbols = list(dict.fromkeys(symbols))  # de-dup but keep order
    if not symbols:
        log.error("[Router] No symbols provided.")
        return

    mode_lower = mode.lower()

    if mode_lower == "daily" and (to_date is None or from_date is None):
        warn_if_same_day_eod(
            from_date or "",
            to_date or datetime.now().strftime("%Y-%m-%d"),
        )

    # Read state defensively
    state = get_market_state()
    session = state.get("session") or state.get("gate") or "UNKNOWN"
    gate = state.get("gate", session)
    is_open = bool(state.get("is_open", False))
    stamp = state.get("timestamp")

    log.info(
        f"[Router] 🚀 Start: {len(symbols)} symbols | mode={mode} | "
        f"session={session} | gate={gate} | at={stamp}"
    )

    # Intraday + gate = skip if closed (for live-style runs)
    if mode_lower == "intraday" and use_gate and not is_open:
        log.info("[Router] ⛳ Market not live (gate on). Skipping this run.")
        return

    eff_from = from_date
    eff_to = to_date
    eff_interval: str | int | None = interval

    if mode_lower == "daily":
        # daily always uses historical service-day semantics
        eff_interval = None
        today_str = datetime.now().strftime("%Y-%m-%d")
        eff_from = from_date or today_str
        eff_to = to_date or eff_from
        target = current_historical_service_day()
        log.info(
            f"[Router] Historical service day (effective): {target} | "
            f"requested {eff_from}→{eff_to}"
        )

    # Concurrent fetch in batches
    chunks = _chunk_list(symbols, BATCH_SIZE)
    all_results: Dict[str, pl.DataFrame] = {}

    for i, chunk in enumerate(chunks, 1):
        log.info(f"[Router] 🧩 Batch {i}/{len(chunks)} | {len(chunk)} symbols")
        t0 = time.perf_counter()
        results = await _fetch_batch(chunk, mode, eff_from, eff_to, eff_interval)
        all_results.update(results)
        log.info(f"[Router] ⏱️ Batch {i} done in {time.perf_counter() - t0:.2f}s")

    # Persist results
    out_path = _generate_output_path(mode)
    await _save_results(all_results, out_path)
    log.info(f"[Router] ✅ Completed {len(symbols)} symbols total → {out_path}")

# ============================================================
# 🔁 Back-compat alias
# ============================================================
async def run_cycle(
    symbols: Sequence[str],
    mode: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    interval: str | int | None = None,
) -> None:
    await run_router(
        symbols,
        mode=mode,
        from_date=from_date,
        to_date=to_date,
        interval=interval,
    )

# ============================================================
# ⏰ Continuous Scheduler (simple local loop)
# ============================================================
async def run_scheduled(
    interval_minutes: int = DEFAULT_INTERVAL_MIN,
    mode: str = "intraday",
    *,
    refresh_every_cycles: int = 12,   # ~ hourly if 5m cadence
    log_universe_stats: bool = True,
):
    """Continuously run fetch cycles while market is open."""
    log.info(f"[Router] 🕒 Scheduler started — every {interval_minutes}m | mode={mode}")
    df = load_instruments_df("INTRADAY" if mode.lower() == "intraday" else "MONTHLY")
    symbols = df["symbol"].to_list() if not df.is_empty() else []
    if log_universe_stats:
        log.info(f"[Router] Universe boot: {len(symbols)} symbols")

    cycle = 0
    while True:
        state = get_market_state()
        if state.get("is_open"):
            log.info(
                f"[Router] Market LIVE — triggering fetch @ {state.get('timestamp')}"
            )

            # For intraday scheduler we want **live** semantics (no from/to)
            if mode.lower() == "intraday":
                await run_router(
                    symbols,
                    mode=mode,
                    from_date=None,
                    to_date=None,
                    interval=f"{interval_minutes}m",
                    use_gate=False,
                )
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                await run_router(
                    symbols,
                    mode=mode,
                    from_date=today,
                    to_date=today,
                    interval=None,
                    use_gate=False,
                )

            # 🔄 periodic universe refresh
            cycle += 1
            if refresh_every_cycles > 0 and (cycle % refresh_every_cycles == 0):
                try:
                    df_new = load_instruments_df(
                        "INTRADAY" if mode.lower() == "intraday" else "MONTHLY"
                    )
                    new_symbols = (
                        df_new["symbol"].to_list() if not df_new.is_empty() else []
                    )
                    if new_symbols != symbols:
                        added = [s for s in new_symbols if s not in symbols]
                        removed = [s for s in symbols if s not in new_symbols]
                        symbols = new_symbols
                        if log_universe_stats:
                            log.info(
                                f"[Router] 🔄 Universe refreshed: {len(symbols)} symbols "
                                f"(+{len(added)}/-{len(removed)})"
                            )
                    else:
                        if log_universe_stats:
                            log.info("[Router] Universe refresh: no changes")
                except Exception as e:
                    log.warning(f"[Router] Universe refresh failed → {e}")

        else:
            log.info(
                f"[Router] Market closed — gate={state.get('gate')} | "
                f"next={state.get('next_open')}"
            )

        await sleep_until_next_candle(interval_minutes)

# ============================================================
# 🧪 CLI Interface
# ============================================================
def run_cli():
    parser = argparse.ArgumentParser(description="Queen Unified Async Fetch Router")
    parser.add_argument("--mode", choices=["daily", "intraday"], default="daily")
    parser.add_argument("--symbols", nargs="+", help="Symbols to fetch")
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--interval",
        default=None,
        help=(
            "Interval token (e.g. 1, 5m, 15m, 1h). "
            "If omitted: daily uses 1d, intraday uses 5m "
            "(from settings.DEFAULT_INTERVALS)."
        ),
    )
    parser.add_argument("--auto", action="store_true", help="Enable continuous scheduler")
    parser.add_argument(
        "--force-live",
        action="store_true",
        help="Bypass market gate (run even on weekends/holidays)",
    )
    parser.add_argument("--interval-minutes", type=int, default=DEFAULT_INTERVAL_MIN)
    parser.add_argument(
        "--max",
        dest="max_symbols",
        type=int,
        default=50,
        help="Limit symbols if --symbols omitted",
    )
    args = parser.parse_args()

    async def main():
        if args.auto:
            await run_scheduled(args.interval_minutes, args.mode)
        else:
            if not args.symbols:
                df = load_instruments_df(
                    "INTRADAY" if args.mode == "intraday" else "MONTHLY"
                )
                symbols = df["symbol"].head(args.max).to_list()
                log.info(f"[Router] Using top {len(symbols)} symbols from universe.")
            else:
                symbols = args.symbols

            if args.mode == "daily":
                warn_if_same_day_eod(args.from_date, args.to_date)

            await run_router(
                symbols,
                args.mode,
                args.from_date,
                args.to_date,
                args.interval,
                use_gate=not args.force_live,
            )

    asyncio.run(main())

# ============================================================
# 🧠 Entrypoint
# ============================================================
if __name__ == "__main__":
    run_cli()
