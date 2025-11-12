#!/usr/bin/env python3
# ============================================================
# queen/cli/monitor_stream.py — v1.4 (SSE console client + retry)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import json
import signal
from typing import List

import httpx
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


def _fmt(x):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:,.1f}"
    return str(x)


def _render(rows: List[dict]) -> Table:
    t = Table(title="📡 Live Stream Monitor", expand=True)
    for col in ["Symbol", "CPR", "VWAP", "ATR", "RSI", "OBV", "Summary", "Targets", "SL"]:
        t.add_column(col)
    for r in rows:
        t.add_row(
            r.get("symbol", ""),
            _fmt(r.get("cpr")),
            _fmt(r.get("vwap")),
            _fmt(r.get("atr")),
            _fmt(r.get("rsi")),
            _fmt(r.get("obv")),
            r.get("summary", ""),
            " • ".join(r.get("targets", [])),
            _fmt(r.get("sl")),
        )
    return t


async def _listen(url: str, stop_evt: asyncio.Event):
    while not stop_evt.is_set():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                async with client.stream("GET", url, headers={"Accept": "text/event-stream"}) as resp:
                    resp.raise_for_status()
                    with Live(Panel("✅ Connected to Live Stream", border_style="green"), refresh_per_second=3) as live:
                        async for line in resp.aiter_lines():
                            if stop_evt.is_set():
                                break
                            if not line or not line.startswith("data:"):
                                continue
                            payload = json.loads(line.removeprefix("data: ").strip())
                            table = _render(payload.get("rows", []))
                            live.update(Group(Panel.fit("📡 Live Stream", border_style="green"), table))
        except Exception as e:
            with Live(Panel(f"Reconnecting... ({e.__class__.__name__})", border_style="yellow")) as live:
                await asyncio.sleep(2.0)
        await asyncio.sleep(1.0)


async def _run(url: str):
    stop_evt = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _graceful(*_):
        stop_evt.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _graceful)
        except NotImplementedError:
            pass

    await _listen(url, stop_evt)
    print("\n👋 Stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="Queen Live Monitor Stream (SSE)")
    parser.add_argument("--symbols", nargs="+", required=True, help="Symbols to stream")
    parser.add_argument("--interval", type=int, default=15, help="Interval minutes (default: 15)")
    parser.add_argument("--tick-sec", type=int, default=15, help="Update frequency in seconds (default: 15)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="8000")
    args = parser.parse_args()

    query = "&".join([f"symbols={s}" for s in args.symbols])
    url = f"http://{args.host}:{args.port}/monitor/stream?{query}&interval={args.interval}&view=compact&tick_sec={args.tick_sec}"

    asyncio.run(_run(url))


if __name__ == "__main__":
    main()
