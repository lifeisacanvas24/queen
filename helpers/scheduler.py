#!/usr/bin/env python3
# ============================================================
# quant/utils/scheduler.py — Quant-Core Adaptive Scheduler (v8.0)
# ============================================================
"""Quant-Core Adaptive Refresh Scheduler (IST + Market-Aware)

Purpose:
    Synchronize live refresh cycles to exact candle boundaries
    — automatically pausing when market is fully closed.

Highlights:
    ✅ Fully timezone-aware (IST)
    ✅ Auto-skips refreshes on weekends / holidays
    ✅ Uses market.should_refresh() before each cycle
    ✅ Reads dynamic interval & buffer via config_proxy (no circular import)
"""

from __future__ import annotations

import asyncio
import datetime
import math
from typing import Optional

import pytz
from rich.console import Console

from quant.utils import market
from quant.utils.config_proxy import cfg_get  # 🔄 circular-safe config access
from quant.utils.logs import auto_logger

console = Console()
logger = auto_logger()
IST = pytz.timezone("Asia/Kolkata")


# ============================================================
# 🕒 Interval Helpers
# ============================================================
def parse_interval(interval: str) -> int:
    """Convert interval string (e.g., '5m', '1h') to seconds."""
    i = str(interval).lower().strip()
    if i.endswith("m"):
        return int(i[:-1]) * 60
    if i.endswith("h"):
        return int(i[:-1]) * 3600
    if i.endswith("d"):
        return int(i[:-1]) * 86400
    return int(i) * 60


# ============================================================
# 🧩 Config Defaults (Hybrid-Safe)
# ============================================================
def get_default_interval() -> str:
    """Fetch default scheduler interval (e.g., 5m, 15m)."""
    return cfg_get("scheduler.default_interval", "15m")


def get_default_buffer() -> int:
    """Fetch default post-candle buffer in seconds."""
    return int(cfg_get("scheduler.default_buffer", 3))


def get_refresh_buffer(interval: Optional[str] = None) -> int:
    """Fetch refresh buffer (in seconds) from config.refresh_map."""
    interval = (interval or get_default_interval()).lower().replace(" ", "")
    refresh_map = cfg_get("scheduler.refresh_map", {}) or {}
    try:
        if interval in refresh_map:
            return int(refresh_map[interval])
        numeric_key = interval.replace("m", "")
        if numeric_key in refresh_map:
            return int(refresh_map[numeric_key])
    except Exception:
        pass
    return get_default_buffer()


# ============================================================
# 🕰️ Core Time Computations
# ============================================================
def get_next_candle_boundary(interval: Optional[str] = None) -> datetime.datetime:
    """Return next aligned candle boundary in IST."""
    interval = interval or get_default_interval()
    now = datetime.datetime.now(tz=IST)
    seconds = parse_interval(interval)
    next_epoch = math.ceil(now.timestamp() / seconds) * seconds
    return datetime.datetime.fromtimestamp(next_epoch, tz=IST)


def next_refresh_time(
    interval: Optional[str] = None, buffer: Optional[int] = None
) -> datetime.datetime:
    """Compute the exact time (datetime) for the next refresh."""
    interval = interval or get_default_interval()
    buffer = buffer if buffer is not None else get_default_buffer()
    next_dt = get_next_candle_boundary(interval)
    return next_dt + datetime.timedelta(seconds=buffer)


def seconds_until_next_refresh(
    interval: Optional[str] = None, buffer: Optional[int] = None
) -> int:
    """Return remaining seconds until the next refresh trigger."""
    interval = interval or get_default_interval()
    buffer = buffer if buffer is not None else get_default_buffer()
    nxt = next_refresh_time(interval, buffer)
    delta = nxt - datetime.datetime.now(tz=IST)
    return max(int(delta.total_seconds()), 0)


# ============================================================
# 🕹️ Market-Aware Sleep
# ============================================================
async def sleep_until_next_refresh(
    interval: Optional[str] = None,
    buffer: Optional[int] = None,
    show_countdown: bool = True,
) -> None:
    """Async sleep aligned to next candle boundary, skipping if market closed."""
    interval = interval or get_default_interval()
    buffer = buffer or get_refresh_buffer(interval)

    # Market guard
    if not market.should_refresh():
        state = market.get_market_state()
        logger.info(f"⏸️ Skipping scheduler — Market={state}")
        await asyncio.sleep(60)
        return

    delay = seconds_until_next_refresh(interval, buffer)
    next_dt = next_refresh_time(interval, buffer)
    state = market.get_market_state()

    if not show_countdown:
        await asyncio.sleep(delay)
        return

    console.print(
        f"[dim]🕒 Next refresh @ [cyan]{next_dt.strftime('%H:%M:%S')}[/cyan] "
        f"({delay}s) | Market: [green]{state}[/green][/dim]"
    )

    for r in range(delay, 0, -1):
        m, s = divmod(r, 60)
        console.print(f"\r⏳ Refresh in {m:02d}:{s:02d}", end="")
        await asyncio.sleep(1)

    console.print("\r✅ [green]Aligned to next candle boundary.[/green]\n")
    logger.info(f"Aligned refresh at {next_dt.isoformat()} ({interval})")


# ============================================================
# 🧪 CLI Demo
# ============================================================
if __name__ == "__main__":

    async def _demo() -> None:
        console.print("[bold cyan]Scheduler Demo[/bold cyan]")
        await sleep_until_next_refresh()

    asyncio.run(_demo())
