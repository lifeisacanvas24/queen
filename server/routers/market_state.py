# queen/server/routers/market_state.py — v11.0 (Cockpit Session Engine)
from __future__ import annotations

from datetime import datetime, time, timedelta

from fastapi import APIRouter
from queen.helpers.common import next_candle_ms
from queen.helpers.market import (
    MARKET_TZ,
    current_session,
    get_gate,
    is_working_day,
)
from queen.server import state as qstate

try:
    from queen.helpers.market import is_market_live
except Exception:
    is_market_live = None  # optional


router = APIRouter(prefix="/market", tags=["market"])


# --------------------------------------------
# Local helper: fallback session classification
# --------------------------------------------
def _session_label(now_ist: datetime) -> str:
    today = now_ist.date()

    # Weekend or holiday
    if not is_working_day(today):
        return "HOLIDAY"

    t = time(now_ist.hour, now_ist.minute)

    pre_start = time(9, 0)
    live_start = time(9, 15)
    live_end = time(15, 30)

    if t < pre_start:
        return "PREOPEN"
    if pre_start <= t < live_start:
        return "PREOPEN"
    if live_start <= t <= live_end:
        return "LIVE"
    return "POST"


# --------------------------------------------
# Main endpoint: /market/state
# --------------------------------------------
@router.get("/state")
async def market_state() -> dict:
    now = datetime.now(MARKET_TZ)
    today = now.date()

    # Working day?
    working = is_working_day(today)

    # Gate: PREOPEN / LIVE / POST / HOLIDAY (fallbacks built-in)
    try:
        gate = get_gate(now)
    except Exception:
        gate = _session_label(now)

    # NSE-style session classification
    sess = current_session(now) or gate

    # Live determination logic
    live_flag = (
        gate == "LIVE" or
        (is_market_live() if callable(is_market_live) else False)
    )

    # Data latency / tick freshness
    last_tick = qstate.get_last_tick()
    if last_tick and last_tick.tzinfo is None:
        last_tick = last_tick.replace(tzinfo=MARKET_TZ)

    data_age = None
    is_stale = True
    if last_tick:
        data_age = max((now - last_tick).total_seconds(), 0)
        is_stale = data_age > 60  # >60s = stale

    # Candle timing payload (UI uses this)
    payload = {
        "asof": int(now.timestamp() * 1000),
        "next_at": int((now + timedelta(seconds=15)).timestamp() * 1000),
        "candle_next_at": next_candle_ms(now, 15),
    }

    # UI-friendly session key
    # (Cockpit v11.0 uses: LIVE, PREOPEN, REGULAR, POST, WEEKEND, HOLIDAY)
    if not working:
        ui_sess = "WEEKEND" if today.weekday() >= 5 else "HOLIDAY"
    else:
        if live_flag:
            ui_sess = "LIVE"
        elif gate == "PREOPEN" or sess == "PREOPEN":
            ui_sess = "PREOPEN"
        elif gate == "POST":
            ui_sess = "POST"
        else:
            ui_sess = "REGULAR"

    return {
        **payload,
        "timestamp": now.isoformat(),
        "session": ui_sess,
        "gate": gate,
        "is_working": working,
        "is_live": live_flag,
        "data_age_sec": data_age,
        "is_stale": is_stale,
    }


# --------------------------------------------
# /market/gate (simple)
# --------------------------------------------
@router.get("/gate")
async def gate_state() -> dict:
    now = datetime.now(MARKET_TZ)
    try:
        gate = get_gate(now)
    except Exception:
        gate = _session_label(now)
    return {
        "gate": gate,
        "timestamp": now.isoformat()
    }


# --------------------------------------------
# /market/ping
# --------------------------------------------
@router.get("/ping")
async def market_ping() -> dict:
    return {
        "status": "ok",
        "router": "market_state",
        "message": "Market router active"
    }
