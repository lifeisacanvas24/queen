# ============================================================
# queen/server/routers/intel.py — v1.0 (intel state + next-day forecast)
# ============================================================
from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from queen.daemons.morning_intel import forecast_next_session
from queen.settings.settings import PATHS

router = APIRouter(prefix="/intel", tags=["intel"])


@router.get("/nextday")
async def nextday_api(next_session: str | None = None) -> Dict[str, Any]:
    """Compute (or return) next-session plan; writes runtime JSON too."""
    if next_session:
        try:
            ns = date.fromisoformat(next_session)
        except Exception:
            ns = date.today() + timedelta(days=1)
    else:
        ns = date.today() + timedelta(days=1)

    rows = await forecast_next_session(ns)
    payload = [
        {
            "symbol": r.symbol,
            "cmp": r.cmp,
            "score": r.score,
            "decision": r.decision,
            "reasons": r.reasons,
            "ema_bias": r.ema_bias,
            "rsi": r.rsi,
            "vwap_zone": r.vwap_zone,
            "supertrend": r.supertrend_bias,
            "next_session": ns.isoformat(),
        }
        for r in rows
    ]
    # also cache the latest for a quick GET
    (PATHS["RUNTIME"] / "next_session_plan.json").write_text(json.dumps(payload, indent=2))
    return {"count": len(payload), "next_session": ns.isoformat(), "rows": payload}


@router.get("/state")
async def intel_state() -> Dict[str, Any]:
    """Return last computed forecast (if any) from runtime."""
    path = PATHS["RUNTIME"] / "next_session_plan.json"
    if not path.exists():
        return {"count": 0, "rows": []}
    try:
        data = json.loads(path.read_text())
    except Exception:
        data = []
    return {"count": len(data), "rows": data}


@router.get("/stream")
async def intel_stream(tick_sec: int = Query(20, ge=5, le=120)) -> StreamingResponse:
    """SSE stream of the current intel state (poll file, push rows)."""
    async def gen():
        while True:
            path = PATHS["RUNTIME"] / "next_session_plan.json"
            rows: List[Dict[str, Any]] = []
            if path.exists():
                try:
                    rows = json.loads(path.read_text())
                except Exception:
                    rows = []
            yield f"data: {json.dumps({'rows': rows})}\n\n"
            await asyncio.sleep(tick_sec)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
