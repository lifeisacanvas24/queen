# queen/server/routers/health.py — v1.1
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from queen.helpers.market import MARKET_TZ
from queen.server import state as qstate

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/engine")
async def engine_health():
    now = datetime.now(MARKET_TZ)
    last = qstate.get_last_tick()
    if last and last.tzinfo is None:
        # normalize naive timestamps to MARKET_TZ
        last = last.replace(tzinfo=MARKET_TZ)

    age = None
    ok = False
    if last:
        age = max(0, int((now - last).total_seconds()))
        ok = age <= 90
    return {
        "last_tick_ist": last.isoformat() if last else None,
        "age_sec": age,
        "ok": ok,
    }
