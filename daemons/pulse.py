#!/usr/bin/env python3
# ============================================================
# queen/daemons/pulse.py — v1.0 (Cockpit pulse scheduler)
# ============================================================
from __future__ import annotations

import argparse
import asyncio
from typing import List

import httpx
from queen.helpers.logger import log


async def _tick(
    client: httpx.AsyncClient,
    base_url: str,
    symbols: List[str],
    rules_path: str,
    bars: int,
) -> None:
    payload = {"symbols": symbols, "rules_path": rules_path, "bars": bars}
    url = base_url.rstrip("/") + "/cockpit/pulse/scan"
    try:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        log.info(
            f"[Pulse] updated_at={data.get('updated_at')} count={data.get('count')}"
        )
    except Exception as e:
        log.error(f"[Pulse] POST {url} failed → {e}")


async def _amain(args: argparse.Namespace) -> int:
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    base_url = args.base_url
    rules_path = args.rules
    bars = args.bars
    interval = max(10, args.interval_sec)

    timeout = httpx.Timeout(args.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if args.run_once:
            await _tick(client, base_url, symbols, rules_path, bars)
            return 0

        log.info(
            f"[Pulse] started interval={interval}s symbols={symbols} rules={rules_path}"
        )
        try:
            while True:
                await _tick(client, base_url, symbols, rules_path, bars)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            log.info("[Pulse] interrupted")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description="Cockpit pulse scheduler (keeps /cockpit/pulse/state fresh)."
    )
    p.add_argument(
        "--base-url", default="http://127.0.0.1:8000", help="Your server base URL"
    )
    p.add_argument(
        "--rules", required=True, help="Path to the YAML rules file (intraday/daily)"
    )
    p.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated symbols (e.g., BSE,NETWEB,GODFRYPHLP)",
    )
    p.add_argument("--bars", type=int, default=150, help="Bars per TF (floor)")
    p.add_argument(
        "--interval-sec", type=int, default=60, help="Refresh interval seconds"
    )
    p.add_argument(
        "--http-timeout", type=float, default=5.0, help="HTTP timeout seconds"
    )
    p.add_argument("--run-once", action="store_true", help="Run a single scan and exit")
    args = p.parse_args()

    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
