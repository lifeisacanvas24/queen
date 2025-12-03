#!/usr/bin/env python3
# ============================================================
# queen/server/routers/monitor.py — v1.2
# ------------------------------------------------------------
# Monitor endpoints:
#   • /snapshot, /stream       → cmp_snapshot (transitional)
#   • /actionable, /summary    → live.actionables_for(...)
#   • /stream_actionable       → SSE of actionables_for(...)
#
# v1.2:
#   • Add mode=light support to:
#       - /monitor/actionable
#       - /monitor/stream_actionable
#     using actionables_light_for() from queen.services.live.
# ============================================================
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from queen.helpers.common import next_candle_ms
from queen.helpers.market import MARKET_TZ
from queen.server import state as qstate
from queen.services.history import load_history  # ensure this exists
from queen.services.live import (
    actionables_for,
    actionables_light_for,  # ✅ new: light wrapper
    cmp_snapshot,
)

# Universe source (prefers helper, falls back to static)
try:
    from queen.helpers.instruments import list_intraday_symbols
except Exception:
    import json as _json

    from queen.settings.settings import PATHS as _PATHS

    def list_intraday_symbols() -> List[str]:
        p = _PATHS["STATIC"] / "intraday_instruments.json"
        data = _json.loads(p.read_text()) if p.exists() else []
        if data and isinstance(data[0], dict):
            return [
                d.get("symbol") or d.get("SYMBOL")
                for d in data
                if (d.get("symbol") or d.get("SYMBOL"))
            ]
        return [str(x) for x in data]


router = APIRouter(prefix="/monitor", tags=["monitor"])


# -------------------------------------------------------------------
# Snapshot (transitional, CMP-only helper)
# -------------------------------------------------------------------
@router.get("/snapshot")
async def snapshot(
    symbols: Optional[List[str]] = Query(None),
    interval: int = Query(15, ge=1, le=120),
):
    syms = [s.upper() for s in (symbols or list_intraday_symbols())]
    rows = await cmp_snapshot(syms, interval)
    qstate.set_last_tick(datetime.now(MARKET_TZ))
    return {"symbols": syms, "interval": interval, "rows": rows}


@router.get("/stream")
async def stream(
    symbols: Optional[List[str]] = Query(None),
    interval: int = Query(15, ge=1, le=120),
    tick_sec: int = Query(15, ge=5, le=120),
):
    syms = [s.upper() for s in (symbols or list_intraday_symbols())]

    async def gen():
        while True:
            try:
                rows = await cmp_snapshot(syms, interval)
                qstate.set_last_tick(datetime.now(MARKET_TZ))
                payload = {"symbols": syms, "interval": interval, "rows": rows}
                yield f"data: {json.dumps(payload, default=str)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(tick_sec)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


# -------------------------------------------------------------------
# Actionable (full vs light)
# -------------------------------------------------------------------
@router.get("/actionable")
async def actionable(
    symbols: Optional[List[str]] = Query(None),
    interval: int = Query(15, ge=1, le=120),
    book: str = Query("all"),
    limit: int = Query(25, ge=1, le=250),
    mode: str = Query("full", description="View mode: full | light"),
):
    """mode:
    - "full"  → original rich row (default)
    - "light" → projected via actionables_light_for(...)
    """
    syms = [s.upper() for s in (symbols or list_intraday_symbols())]

    # Normalise mode defensively
    m = (mode or "full").lower()
    if m not in ("full", "light"):
        m = "full"

    if m == "light":
        rows = await actionables_light_for(syms, interval_min=interval, book=book)
    else:
        rows = await actionables_for(syms, interval_min=interval, book=book)

    qstate.set_last_tick(datetime.now(MARKET_TZ))

    rows = rows[:limit]
    return {"count": len(rows), "rows": rows, "mode": m}


# -------------------------------------------------------------------
# Summary (still full for now)
# -------------------------------------------------------------------
@router.get("/summary")
async def summary(
    symbols: Optional[List[str]] = Query(None),
    interval: int = Query(15, ge=1, le=120),
    book: str = Query("all"),
    limit: int = Query(200, ge=1, le=500),
):
    syms = [s.upper() for s in (symbols or list_intraday_symbols())]
    rows = await actionables_for(syms, interval_min=interval, book=book)
    rows = rows[:limit]
    return {"count": len(rows), "rows": rows}


# -------------------------------------------------------------------
# History (unchanged)
# -------------------------------------------------------------------
@router.get("/history")
async def history(limit: int = Query(500, ge=1, le=2000)):
    rows = load_history(limit)
    return {"count": len(rows), "rows": rows}


# -------------------------------------------------------------------
# Stream Actionable (full vs light, SSE)
# -------------------------------------------------------------------
@router.get("/stream_actionable")
async def stream_actionable(
    symbols: Optional[List[str]] = Query(None),
    interval: int = Query(15, ge=1, le=120),
    book: str = Query("all"),
    tick_sec: int = Query(15, ge=5, le=120),
    mode: str = Query("full", description="View mode: full | light"),
):
    """mode:
    - "full"  → original rich row (default)
    - "light" → projected via actionables_light_for(...)
    """
    syms = [s.upper() for s in (symbols or list_intraday_symbols())]

    m = (mode or "full").lower()
    if m not in ("full", "light"):
        m = "full"

    async def gen():
        while True:
            try:
                if m == "light":
                    rows = await actionables_light_for(
                        syms, interval_min=interval, book=book
                    )
                else:
                    rows = await actionables_for(
                        syms, interval_min=interval, book=book
                    )

                now = datetime.now(MARKET_TZ)
                qstate.set_last_tick(now)

                rows = rows[:250]  # safety cap
                payload = {
                    "symbols": syms,
                    "interval": interval,
                    "rows": rows,
                    "mode": m,
                    "asof": int(now.timestamp() * 1000),
                    "next_at": int(
                        (now + timedelta(seconds=tick_sec)).timestamp() * 1000
                    ),
                    "candle_next_at": next_candle_ms(now, interval),
                }
                yield f"data: {json.dumps(payload, default=str)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(tick_sec)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
