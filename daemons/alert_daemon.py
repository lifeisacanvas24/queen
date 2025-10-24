#!/usr/bin/env python3
# ============================================================
# queen/daemons/alert_daemon.py — v1.1 (Price Alerts + JSONL/HTTP sinks)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
import polars as pl
from queen.fetchers.upstox_fetcher import fetch_intraday
from queen.helpers.logger import log
from queen.helpers.market import MarketClock, get_market_state, market_gate
from queen.settings import settings as SETTINGS


# ---------- Rule model ----------
@dataclass(frozen=True)
class ThresholdRule:
    symbol: str
    op: str  # 'ge' | 'gt' | 'le' | 'lt' | 'eq' | 'ne'
    price: float
    interval: int  # minutes

    def check(self, last_close: float) -> bool:
        match self.op:
            case "ge":
                return last_close >= self.price
            case "gt":
                return last_close > self.price
            case "le":
                return last_close <= self.price
            case "lt":
                return last_close < self.price
            case "eq":
                return abs(last_close - self.price) < 1e-8
            case "ne":
                return abs(last_close - self.price) >= 1e-8
        return False


# ---------- Parsing ----------
def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Queen Alert Daemon")
    p.add_argument(
        "--symbols", nargs="+", required=True, help="Symbols to watch (e.g. TCS INFY)"
    )
    p.add_argument(
        "--op",
        choices=["ge", "gt", "le", "lt", "eq", "ne"],
        default="ge",
        help="Comparison op for close vs price (default: ge)",
    )
    p.add_argument("--price", type=float, required=True, help="Threshold price")
    p.add_argument(
        "--interval", type=int, default=5, help="Intraday minutes (default: 5)"
    )
    p.add_argument(
        "--tick-interval",
        type=int,
        default=5,
        help="Clock tick minutes (default: 5); align with fetch cadence",
    )
    p.add_argument(
        "--cooldown",
        type=int,
        default=15,
        help="Minutes to suppress duplicate alerts per symbol (default: 15)",
    )
    p.add_argument(
        "--log-only", action="store_true", help="Do not print to stdout, log only"
    )

    # New sinks (optional)
    p.add_argument(
        "--emit-jsonl",
        action="store_true",
        help="Append alerts to EXPORTS/alerts/alerts.jsonl",
    )
    p.add_argument(
        "--http-post",
        type=str,
        default=None,
        help="POST alert JSON to this URL (your future FastAPI endpoint)",
    )
    p.add_argument(
        "--http-timeout",
        type=float,
        default=3.0,
        help="HTTP POST timeout seconds (default: 3.0)",
    )
    return p.parse_args(argv)


# ---------- Sinks ----------
class Notifier:
    def __init__(
        self,
        log_only: bool = False,
        emit_jsonl: bool = False,
        http_post: Optional[str] = None,
        http_timeout: float = 3.0,
    ):
        self.log_only = log_only
        self.emit_jsonl = emit_jsonl
        self.http_post = http_post
        self.http_timeout = http_timeout
        self._jsonl_path = None
        if emit_jsonl:
            alerts_dir = SETTINGS.PATHS["EXPORTS"] / "alerts"
            alerts_dir.mkdir(parents=True, exist_ok=True)
            self._jsonl_path = alerts_dir / "alerts.jsonl"

    async def _http_send(self, payload: dict):
        if not self.http_post:
            return
        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                await client.post(self.http_post, json=payload)
        except Exception as e:
            log.warning(f"[Alert] HTTP sink error → {e}")

    def _jsonl_write(self, payload: dict):
        if not self._jsonl_path:
            return
        try:
            with self._jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            log.warning(f"[Alert] JSONL sink error → {e}")

    async def notify(self, payload: dict, human: str):
        # log + optional stdout
        log.info(f"[Alert] {human}")
        if not self.log_only:
            print(human, flush=True)
        # sinks
        self._jsonl_write(payload)
        await self._http_send(payload)


# ---------- Fetch latest close ----------
async def _latest_close(symbol: str, interval_min: int) -> float | None:
    df: pl.DataFrame = await fetch_intraday(symbol, interval_min)
    if df.is_empty():
        return None
    return float(df[-1, "close"])


# ---------- Main loop ----------
async def _run(
    rules: List[ThresholdRule], tick_minutes: int, cooldown_min: int, notifier: Notifier
):
    fired: Dict[str, Dict[str, Any]] = {}

    clock = MarketClock(
        interval=tick_minutes, name="AlertClock", verbose=True, auto_pause=True
    )
    queue = clock.subscribe("AlertDaemon")

    async with market_gate(mode="intraday"):
        log.info(f"[Alert] Starting with {len(rules)} rule(s)")
        state = get_market_state()
        log.info(
            f"[Alert] Market state @ start → session={state['session']} gate={state['gate']}"
        )

        async def evaluator():
            while True:
                _ = await queue.get()
                # parallel fetches
                tasks = {r.symbol: _latest_close(r.symbol, r.interval) for r in rules}
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)

                sym_to_close: Dict[str, float | None] = {}
                for sym, res in zip(tasks.keys(), results):
                    sym_to_close[sym] = None if isinstance(res, Exception) else res

                now = get_market_state()
                now_iso = now["timestamp"]
                for r in rules:
                    last = sym_to_close.get(r.symbol)
                    if last is None or not r.check(last):
                        continue
                    info = fired.get(r.symbol)
                    if info:
                        info["remaining"] = max(
                            0, info.get("remaining", 0) - tick_minutes
                        )
                        if info["remaining"] > 0:
                            continue
                    fired[r.symbol] = {
                        "remaining": cooldown_min,
                        "last_close": last,
                        "ts": now_iso,
                    }
                    payload = {
                        "symbol": r.symbol,
                        "op": r.op,
                        "threshold": r.price,
                        "last_close": last,
                        "interval_min": r.interval,
                        "timestamp": now_iso,
                        "session": now["session"],
                        "gate": now["gate"],
                    }
                    human = f"🔔 {r.symbol} close {last:.2f} {r.op} {r.price:.2f} @ {now_iso} ({r.interval}m)"
                    await notifier.notify(payload, human)

        await asyncio.gather(clock.start(), evaluator())


def run_cli(argv: Optional[List[str]] = None):
    args = _parse_args(argv)
    rules = [
        ThresholdRule(symbol=s, op=args.op, price=args.price, interval=args.interval)
        for s in args.symbols
    ]
    notifier = Notifier(
        log_only=args.log_only,
        emit_jsonl=args.emit_jsonl,
        http_post=args.http_post,
        http_timeout=args.http_timeout,
    )
    try:
        asyncio.run(
            _run(
                rules,
                tick_minutes=args.tick_interval,
                cooldown_min=args.cooldown,
                notifier=notifier,
            )
        )
    except KeyboardInterrupt:
        log.info("[Alert] Stopped by user.")


if __name__ == "__main__":
    run_cli()
