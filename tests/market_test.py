#!/usr/bin/env python3
# ============================================================
# queen/tests/market_test.py — Market Environment Test Harness (fixed)
# ============================================================
from __future__ import annotations

import asyncio
import datetime as dt

from queen.helpers import market


# ------------------------------------------------------------
# 🧩 Core Sync Tests
# ------------------------------------------------------------
def test_holidays():
    today = dt.date.today()
    print("\n🗓️  HOLIDAY TEST")
    print(f"Today: {today} | Holiday? {market.is_holiday(today)}")

    hol = market._holidays()  # using internal cache accessor
    years = sorted(list(hol.keys()))[:5]
    print(f"Loaded holiday years: {', '.join(str(y) for y in years)}")
    for y in years:
        print(f"  {y}: {len(hol[y])} holidays")


def test_working_days():
    today = dt.date.today()
    last_ = market.last_working_day(today)
    next_ = market.next_working_day(today)
    prev_ = market.offset_working_day(today, -1)
    print("\n📅  WORKING DAY TEST")
    print(f"Today: {today}")
    print(f"Last working day: {last_}")
    print(f"Next working day: {next_}")
    print(f"Previous working day (offset -1): {prev_}")


def test_market_state():
    now = dt.datetime.now(market.MARKET_TZ)
    gate = market.get_gate(now)
    state = market.get_market_state()
    print("\n🕒  MARKET STATE TEST")
    print(f"Now: {now.strftime('%Y-%m-%d %H:%M:%S')} {market.MARKET_TZ}")
    print(f"Gate: {gate}")
    for k, v in state.items():
        print(f"  {k}: {v}")


def test_time_bucket():
    print("\n⏱️  SESSION TEST")
    test_times = [
        dt.datetime(2025, 10, 21, 9, 30),
        dt.datetime(2025, 10, 21, 12, 15),
        dt.datetime(2025, 10, 21, 15, 15),
        dt.datetime(2025, 10, 21, 16, 0),
    ]
    for t in test_times:
        sess = market.current_session(t)
        print(f"{t.time()} → {sess or 'CLOSED'}")


# ------------------------------------------------------------
# ⚡ Async Tests
# ------------------------------------------------------------
async def test_sleep_until_next_candle():
    print("\n🌙  ASYNC TEST — sleep_until_next_candle()")
    await market.sleep_until_next_candle(
        interval_minutes=1, jitter_ratio=0.1, emit_log=True
    )
    print("⏰ Woke up at next candle boundary.")


async def test_market_clock():
    print("\n⏱️  ASYNC TEST — MarketClock")

    clock = market.MarketClock(interval=1, name="TestClock", verbose=True)
    q1 = clock.subscribe("FetcherDaemon")

    async def listener(name: str, queue: asyncio.Queue):
        n = 0
        while n < 2:  # ~2 ticks then stop
            tick = await queue.get()
            print(
                f"[{name}] ⏰ Tick @ {tick['timestamp'].strftime('%H:%M:%S')} | {tick['session']}"
            )
            n += 1

    # run clock and listener briefly, then stop
    async def run_short():
        task_clock = asyncio.create_task(clock.start())
        task_listen = asyncio.create_task(listener("FetcherDaemon", q1))
        await asyncio.wait({task_listen}, return_when=asyncio.ALL_COMPLETED)
        await clock.stop()
        task_clock.cancel()

    await run_short()


# ------------------------------------------------------------
# 🧠 Runner
# ------------------------------------------------------------
def run_sync_tests():
    print("\n🧩 Queen Market System — Sync Diagnostics")
    print("====================================================")
    test_holidays()
    test_working_days()
    test_market_state()
    test_time_bucket()


async def run_async_tests():
    print("\n⚙️  Running async timing tests...")
    await test_sleep_until_next_candle()
    await test_market_clock()


if __name__ == "__main__":
    run_sync_tests()
    try:
        asyncio.run(run_async_tests())
    except KeyboardInterrupt:
        print("\n[🛑] Interrupted by user.")
