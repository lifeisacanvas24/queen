# queen/server/routers/market_state.py — v2.3
from __future__ import annotations

from datetime import datetime, time,timedelta

from fastapi import APIRouter
from queen.helpers.market import MARKET_TZ, current_session, get_gate, is_working_day
from queen.server import state as qstate
from queen.helpers.common import next_candle_ms

try:
    from queen.helpers.market import is_market_live  # optional
except Exception:
    is_market_live = None  # type: ignore

router = APIRouter(prefix="/market", tags=["market"])


def _session_label(now_ist: datetime) -> str:
    today = now_ist.date()
    if not is_working_day(today):
        return "HOLIDAY"
    t = time(now_ist.hour, now_ist.minute)
    pre_start = time(9, 0)
    live_start = time(9, 15)
    live_end = time(15, 30)
    if t < pre_start:
        return "PRE"
    if pre_start <= t < live_start:
        return "PRE"
    if live_start <= t <= live_end:
        return "LIVE"
    return "POST"

@router.get("/state")
async def market_state() -> dict:
    now = datetime.now(MARKET_TZ)
    working = is_working_day(now.date())
    try:
        gate = get_gate(now)
    except Exception:
        gate = _session_label(now)
    sess = current_session(now)
    live_flag = (gate == "LIVE") or (is_market_live() if callable(is_market_live) else False)

    last_tick = qstate.get_last_tick()
    if last_tick and last_tick.tzinfo is None:
        last_tick = last_tick.replace(tzinfo=MARKET_TZ)
    data_age = None
    is_stale = True
    if last_tick:
        data_age = max((now - last_tick).total_seconds(), 0)
        is_stale = data_age > 60

    # ✅ Correct usage (this is inside the function, where 'now' exists)
    payload = {
        "asof": int(now.timestamp() * 1000),
        "next_at": int((now + timedelta(seconds=15)).timestamp() * 1000),
        "candle_next_at": next_candle_ms(now, 15),
    }

    ui_session = "LIVE" if live_flag else ("PRE" if gate == "PRE" else "REGULAR")
    return {
        **payload,  # optional if you want to include those times
        "timestamp": now.isoformat(),
        "session": ui_session,
        "gate": gate,
        "is_working": working,
        "is_live": live_flag,
        "data_age_sec": data_age,
        "is_stale": is_stale,
    }

@router.get("/gate")
async def gate_state() -> dict:
    now = datetime.now(MARKET_TZ)
    try:
        gate = get_gate(now)
    except Exception:
        gate = _session_label(now)
    return {"gate": gate, "timestamp": now.isoformat()}

@router.get("/ping")
async def market_ping() -> dict:
    return {"status": "ok", "router": "market_state", "message": "Market router active"}
