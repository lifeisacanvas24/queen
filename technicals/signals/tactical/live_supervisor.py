#!/usr/bin/env python3
# ============================================================
# queen/technicals/signals/tactical/live_supervisor.py
# ------------------------------------------------------------
# 🧭 Tactical Live Supervisor — concurrent single-cycle runner
# Launches multiple cognition cycles concurrently and writes
# a health snapshot to settings-driven logs.
# ============================================================

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import polars as pl

from queen.helpers.logger import log

try:
    from queen.settings import settings as SETTINGS
except Exception:
    SETTINGS = None

# --- Settings & paths --------------------------------------------------------
LOG_DIR = (
    SETTINGS.PATHS["LOGS"]
    if SETTINGS
    else os.path.join("queen", "data", "runtime", "logs")
)
os.makedirs(LOG_DIR, exist_ok=True)
HEALTH_FILE = os.path.join(LOG_DIR, "supervisor_health.json")

SUP_CFG = (getattr(SETTINGS, "SUPERVISOR", {}) if SETTINGS else {}) or {}
DEFAULTS = {
    "symbols": ["AAPL", "NVDA", "BTCUSD", "ETHUSD"],
    "timeframes": ["5m", "15m", "1h"],
    "max_concurrent": 3,
    "interval_sec": 6 * 60 * 60,  # 6h run cadence for reference
    "healthcheck_interval": 10 * 60,  # 10m between supervision cycles
}
CFG = {**DEFAULTS, **SUP_CFG}

# Reuse the daemon's single-cycle entry (no nested sleep loops)
from queen.technicals.signals.tactical.live_daemon import run_daemon_once


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_health(status: Dict[str, Any]) -> None:
    try:
        with open(HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
        log.info(
            f"[Supervisor] 🩺 Health snapshot → {HEALTH_FILE}", extra={"extra": status}
        )
    except Exception as e:
        log.warning(f"[Supervisor] Failed to write health snapshot → {e}")


async def _run_single(symbol: str, tf: str) -> Dict[str, Any]:
    """Wrap a single cognition cycle for a (symbol, timeframe)."""
    ts = _utc_now()
    # In future you can build df map keyed by tf/symbol here:
    global_health: Dict[str, pl.DataFrame] | None = None
    ok = await asyncio.to_thread(run_daemon_once, global_health)
    return {
        "symbol": symbol,
        "timeframe": tf,
        "status": "success" if ok else "failed",
        "timestamp": ts,
    }


async def run_supervisor() -> None:
    log.info("[Supervisor] 🛰️ Launching fleet (single-cycle concurrent runs)")
    symbols: List[str] = list(CFG["symbols"])
    tfs: List[str] = list(CFG["timeframes"])
    max_conc: int = int(CFG["max_concurrent"])
    health_iv: int = int(CFG["healthcheck_interval"])

    sem = asyncio.Semaphore(max_conc)

    async def _guarded(symbol: str, tf: str) -> Dict[str, Any]:
        async with sem:
            return await _run_single(symbol, tf)

    cycle = 0
    while True:
        cycle += 1
        start = time.time()
        tasks = [asyncio.create_task(_guarded(s, tf)) for s in symbols for tf in tfs]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        healthy = [r for r in results if r.get("status") == "success"]
        failed = [r for r in results if r.get("status") != "success"]
        summary = {
            "timestamp": _utc_now(),
            "cycle": cycle,
            "healthy": len(healthy),
            "failed": len(failed),
            "symbols": len(symbols),
            "timeframes": len(tfs),
            "duration_sec": round(time.time() - start, 3),
            "results": results,
        }
        _save_health(summary)

        log.info(
            f"[Supervisor] ✅ cycle #{cycle} — ok={len(healthy)} fail={len(failed)} "
            f"dur={summary['duration_sec']}s"
        )
        await asyncio.sleep(health_iv)


if __name__ == "__main__":
    try:
        asyncio.run(run_supervisor())
    except KeyboardInterrupt:
        log.info("[Supervisor] 🛑 Stopped by user")
