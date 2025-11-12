#!/usr/bin/env python3
# ============================================================
# queen/server/routers/alerts.py — v1.0
# ============================================================
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("")
async def alerts_page(request: Request):
    return request.app.state.templates.TemplateResponse("alerts/alerts.html", {"request": request})
