from __future__ import annotations
from fastapi import APIRouter, Query
from queen.daemons.live_engine import MonitorConfig, _one_pass  # reuse the engine
import asyncio

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/snapshot")
async def snapshot(symbols: list[str] = Query(...), interval: int = 15):
    cfg = MonitorConfig(symbols=symbols, interval_min=interval)
    rows = await _one_pass(cfg)
    return {"symbols": symbols, "interval": interval, "rows": rows}
