# queen/server/routers/services.py — morning + forecast
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query
from queen.services.forecast import ForecastOptions, build_next_session_plan
from queen.services.morning import run_morning_briefing

router = APIRouter(prefix="/services", tags=["services"])

@router.get("/morning")
async def morning_briefing_api():
    # returns dict {generated_at, today_top, trend_5, weekly_strength, status}
    return run_morning_briefing()

@router.post("/forecast")
async def forecast_api(symbols: List[str] = Query(...), interval_min: int = 15):
    payload = await build_next_session_plan(symbols, ForecastOptions(interval_min=interval_min))
    return payload
