#!/usr/bin/env python3
# ============================================================
# queen/fetchers/fetch_router.py — v9.5 (Unified Async Orchestrator)
# ============================================================
"""Queen Fetch Router — Unified Async Dispatcher
-------------------------------------------------
✅ Central async orchestrator for broker fetch cycles
✅ Integrates with:
    • upstox_fetcher (v9.x)
    • market (gate + clock)
    • instruments + schema_adapter
✅ Settings-driven (batch size, concurrency, export format)
✅ Polars-native and production-safe
✅ Unified JSONL + Rich diagnostics
✅ Long-term fix: daily runs pass interval=None so the fetcher
   applies settings.DEFAULTS['DEFAULT_INTERVALS']['daily'].
"""

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
from queen.helpers.intervals import parse_minutes, to_fetcher_interval
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

# Concurrency / batches from settings with safe fallbacks
MAX_CONCURRENCY: int = int(FETCH_CFG.get("MAX_WORKERS", 8))
BATCH_SIZE: int = int(FETCH_CFG.get("BATCH_SIZE", 50))  # optional knob

# Export format knob (parquet|csv|json)
EXPORT_FORMAT: str = (DEFAULTS.get("EXPORT_FORMAT") or "parquet").lower()

# Scheduler default interval (handles "5m", "15", 5 etc.)
DEFAULT_INTERVAL_MIN: int = parse_minutes(SCHED_CFG.get("DEFAULT_INTERVAL", "5m"))


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
            # fallback stays atomic as well
            io.write_parquet(out_path.with_suffix(".parquet"), combined)
            log.warning(
                f"[Router] Unknown export format '{EXPORT_FORMAT}', wrote parquet instead."
            )

    log.info(f"[Router] 💾 Saved results → {out_path}")


# ============================================================
# ⚡ Async Fetch Logic
# ============================================================
async def _fetch_symbol(
    symbol: str,
    mode: str,
    from_date: str,
    to_date: str,
    interval: str | int | None,
    sem: asyncio.Semaphore,
) -> pl.DataFrame:
    async with sem:
        start = time.perf_counter()
        try:
            df = await fetch_unified(symbol, mode, from_date, to_date, interval)
            latency = time.perf_counter() - start
            log.info(
                f"[Fetch] ✅ {symbol}: {0 if df.is_empty() else len(df)} rows | {latency:.2f}s"
            )
            return df
        except Exception as e:
            log.error(f"[Fetch] ❌ {symbol} failed → {e}")
            return pl.DataFrame()


async def _fetch_batch(
    symbols: List[str],
    mode: str,
    from_date: str,
    to_date: str,
    interval: str | int | None,
) -> Dict[str, pl.DataFrame]:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    tasks = (
        _fetch_symbol(sym, mode, from_date, to_date, interval, sem) for sym in symbols
    )
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: Dict[str, pl.DataFrame] = {}
    for sym, res in zip(symbols, results):
        if isinstance(res, Exception):
            # This catches catastrophic crashes *outside* _fetch_symbol’s try/except
            log.error(f"[Fetch] ❌ {sym} task crashed → {res}")
            out[sym] = pl.DataFrame()
        else:
            out[sym] = res
    return out


# ============================================================
# 🚀 Main Orchestrator (preferred entry)
# ============================================================
async def run_router(
    symbols: Sequence[str],
    mode: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    interval: str | int | None = None,
    use_gate: bool = True,  # NEW: default keeps existing behavior
) -> None:
    """Run a full fetch cycle over `symbols`.

    Long-term design:
      • For daily/historical → pass interval=None so the fetcher applies
        DEFAULTS['DEFAULT_INTERVALS']['daily'] (usually '1d').
      • For intraday → interval may be None (fetcher uses '5m') or an explicit token.
    """
    symbols = list(dict.fromkeys(symbols))  # de-dup but keep order
    if not symbols:
        log.error("[Router] No symbols provided.")
        return

    # Friendly EOD hint if user omitted to_date in daily mode
    if mode.lower() == "daily" and (to_date is None or from_date is None):
        warn_if_same_day_eod(
            from_date or "", to_date or datetime.now().strftime("%Y-%m-%d")
        )

    async def _cycle_body():
        state = get_market_state()
        log.info(
            f"[Router] 🚀 Start: {len(symbols)} symbols | mode={mode} | session={state['session']} | gate={state['gate']}"
        )

        from_date = from_date or datetime.now().strftime("%Y-%m-%d")
        to_date = to_date or from_date

        # Let the fetcher decide the default interval for daily/historical
        effective_interval: str | int | None = interval
        if mode.lower() == "daily":
            effective_interval = None  # fetcher will use DEFAULT_INTERVALS['daily']

        if mode.lower() == "daily":
            target = current_historical_service_day()
            log.info(
                f"[Router] Historical service day (effective): {target} | requested {from_date}→{to_date}"
            )

        chunks = _chunk_list(symbols, BATCH_SIZE)
        all_results: Dict[str, pl.DataFrame] = {}

        for i, chunk in enumerate(chunks, 1):
            log.info(f"[Router] 🧩 Batch {i}/{len(chunks)} | {len(chunk)} symbols")
            start = time.perf_counter()
            results = await _fetch_batch(
                chunk, mode, from_date, to_date, effective_interval
            )
            all_results.update(results)
            elapsed = time.perf_counter() - start
            log.info(f"[Router] ⏱️ Batch {i} done in {elapsed:.2f}s")

        out_path = _generate_output_path(mode)
        await _save_results(all_results, out_path)
        log.info(f"[Router] ✅ Completed {len(symbols)} symbols total.")

        if use_gate:
            async with market_gate():
                await _cycle_body()
        else:
            log.info("[Router] ⛳ Gate bypass enabled — running immediately")
            await _cycle_body()


# ============================================================
# 🔁 Back-compat alias (some code calls run_cycle)
# ============================================================
async def run_cycle(
    symbols: Sequence[str],
    mode: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    interval: str | int | None = None,
) -> None:
    await run_router(
        symbols, mode=mode, from_date=from_date, to_date=to_date, interval=interval
    )


# ============================================================
# ⏰ Continuous Scheduler (simple local loop)
# ============================================================
async def run_scheduled(
    interval_minutes: int = DEFAULT_INTERVAL_MIN, mode: str = "intraday"
):
    """Continuously run fetch cycles while market is open."""
    log.info(f"[Router] 🕒 Scheduler started — every {interval_minutes}m | mode={mode}")
    df = load_instruments_df("INTRADAY" if mode.lower() == "intraday" else "MONTHLY")
    symbols = df["symbol"].to_list() if not df.is_empty() else []

    while True:
        state = get_market_state()
        if state["is_open"]:
            today = datetime.now().strftime("%Y-%m-%d")
            log.info(f"[Router] Market LIVE — triggering fetch @ {state['timestamp']}")
            # Canonicalize the intraday interval once here for consistency
            intraday_interval = to_fetcher_interval(f"{interval_minutes}m")
            await run_router(
                symbols,
                mode=mode,
                from_date=today,
                to_date=today,
                interval=(intraday_interval if mode.lower() == "intraday" else None),
            )
        else:
            log.info(
                f"[Router] Market closed — gate={state['gate']} | next={state['next_open']}"
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
        help="Interval token (e.g. 1, 5m, 15m, 1h). "
        "If omitted: daily uses 1d, intraday uses 5m (from settings.DEFAULT_INTERVALS).",
    )
    parser.add_argument(
        "--auto", action="store_true", help="Enable continuous scheduler"
    )
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
                symbols = df["symbol"].head(args.max_symbols).to_list()
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
                use_gate=not args.force_live,  # NEW
            )

    asyncio.run(main())


# ============================================================
# 🧠 Entrypoint
# ============================================================
if __name__ == "__main__":
    run_cli()
