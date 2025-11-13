#!/usr/bin/env python3
# ============================================================
# queen/server/routers/cockpit.py — v2.1 (Unified pages + APIs)
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import polars as pl
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from queen.alerts.rules import load_rules
from queen.fetchers.upstox_fetcher import fetch_intraday
from queen.helpers.instruments import list_symbols as _list_symbols
from queen.helpers.instruments import filter_to_active_universe
from queen.helpers.market import MARKET_TZ
from queen.helpers.portfolio import load_positions
from queen.services.history import load_history  # add this import
from queen.services.scoring import action_for, compute_indicators
from queen.services.symbol_scan import run_symbol_scan
from starlette.requests import Request
from queen.services.live import _intraday_with_backfill

# -----------------------------------------------------------------------------
# Router setup
# -----------------------------------------------------------------------------
router_pages = APIRouter(prefix="/cockpit", tags=["cockpit-pages"])
router_api   = APIRouter(prefix="/cockpit/api", tags=["cockpit-api"])

ROUTERS = [router_pages, router_api]  # optional loop include

# -----------------------------------------------------------------------------
# Local render helper (avoids circular import with main.render)
# -----------------------------------------------------------------------------
def _render(request: Request, tpl_name: str, ctx: Optional[dict] = None):
    ctx = ctx or {}
    ctx.setdefault("now", datetime.now(MARKET_TZ).strftime("%Y-%m-%d %H:%M:%S IST"))
    return request.app.state.templates.TemplateResponse(tpl_name, {"request": request, **ctx})

# -----------------------------------------------------------------------------
# Pages (HTML templates)
# -----------------------------------------------------------------------------
@router_pages.get("", include_in_schema=False)
async def cockpit_root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/cockpit/live", status_code=307)

@router_pages.get("/live")
async def cockpit_live(request: Request):
    return _render(request, "cockpit/live.html")

@router_pages.get("/summary")
async def cockpit_summary(request: Request):
    return _render(request, "cockpit/summary.html")

@router_api.get("/history")
async def history_api(limit: int = Query(500, ge=1, le=2000)) -> Dict:
    rows = load_history(limit)
    return {"count": len(rows), "rows": rows}

@router_pages.get("/upcoming")
async def cockpit_upcoming(request: Request):
    return _render(request, "cockpit/upcoming.html")

@router_pages.get("/analytics")
async def cockpit_analytics(request: Request):
    return _render(request, "cockpit/analytics.html")

@router_pages.get("/history")
async def cockpit_history(request: Request):
    # Placeholder: reuse summary layout for now
    return _render(request, "cockpit/summary.html")

# -----------------------------------------------------------------------------
# Scan / Pulse APIs
# -----------------------------------------------------------------------------
_PULSE_STATE: Dict[str, Any] = {"results": [], "ts": None}

class ScanRequest(BaseModel):
    symbols: List[str] = Field(..., description="Symbols to scan")
    rules_path: str = Field(..., description="Path to YAML rules file")
    bars: int = Field(150, ge=10, le=2000, description="History bars per TF")

class PulseRequest(BaseModel):
    symbols: List[str]
    rules_path: str
    bars: int = 150

@router_api.post("/scan")
async def scan(req: ScanRequest) -> List[Dict[str, Any]]:
    try:
        rules = load_rules(req.rules_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load rules: {e}") from e

    rules = [r for r in rules if r.symbol in set(req.symbols)]
    if not rules:
        _PULSE_STATE.update({"results": [], "ts": None})
        return []

    results = await run_symbol_scan(req.symbols, rules, bars=req.bars)
    _PULSE_STATE["results"] = results
    _PULSE_STATE["ts"] = datetime.utcnow().isoformat() + "Z"
    return results

@router_api.get("/pulse/state")
async def pulse_state() -> Dict[str, Any]:
    return {
        "updated_at": _PULSE_STATE.get("ts"),
        "count": len(_PULSE_STATE.get("results", [])),
        "results": _PULSE_STATE.get("results", []),
    }

@router_api.post("/pulse/scan")
async def pulse_scan(req: PulseRequest) -> Dict[str, Any]:
    try:
        rules = load_rules(req.rules_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load rules: {e}") from e

    rules = [r for r in rules if r.symbol in set(req.symbols)]
    results = await run_symbol_scan(req.symbols, rules, bars=req.bars) if rules else []
    _PULSE_STATE["results"] = results
    _PULSE_STATE["ts"] = datetime.utcnow().isoformat() + "Z"
    return {"updated_at": _PULSE_STATE["ts"], "count": len(results), "results": results}

# -----------------------------------------------------------------------------
# Summary / Upcoming APIs (indicator computation + actioning)
# -----------------------------------------------------------------------------
def _universe(symbols: Optional[List[str]]) -> List[str]:
    """Determine which symbols the cockpit should operate on.

    Priority:
      1) Explicit symbols passed via query
      2) Intraday instruments JSON (INTRADAY)
      3) Optional filter by active_universe.csv (if present)
    """
    if symbols:
        return [s.upper() for s in symbols]

    base = _list_symbols("INTRADAY")
    return filter_to_active_universe(base)



async def _fetch_latest_df(symbol: str, interval_min: int) -> pl.DataFrame:
    """Fetch intraday OHLCV with backfill aware of MIN_BARS from settings."""
    return await _intraday_with_backfill(symbol, interval_min)

@router_api.get("/summary")
async def summary_api(
    symbols: Optional[List[str]] = Query(None),
    interval: int = Query(15, ge=1, le=120),
    book: str = Query("all"),
) -> Dict:
    """Lightweight rollup for Summary page.
    Fetches OHLCV per symbol (intraday), computes indicators, and derives action rows.
    """
    syms = _universe(symbols)
    pos_map = load_positions(book)

    rows: List[Dict] = []
    for sym in syms:
        df = await _fetch_latest_df(sym, interval)
        if df.is_empty():
            continue
        ind = compute_indicators(df)
        if not ind:
            continue
        row = action_for(sym, ind, book=book, use_uc_lc=True)
        row["held"] = sym in pos_map
        rows.append(row)

    # Sort by score desc, then BUY/ADD, then HOLD, then others
    prio = {"BUY": 0, "ADD": 0, "HOLD": 1}
    rows.sort(key=lambda x: (-(x.get("score") or 0), prio.get(x.get("decision", ""), 2)))
    return {"count": len(rows), "rows": rows}

@router_api.get("/upcoming/next")
async def upcoming_next(
    symbols: Optional[List[str]] = Query(None),
    interval: int = Query(15, ge=1, le=120),
    book: str = Query("all"),
) -> Dict:
    """Tomorrow/next-session lean list — placeholder; reuses summary for now."""
    return await summary_api(symbols=symbols, interval=interval, book=book)

@router_api.get("/upcoming/week")
async def upcoming_week(
    symbols: Optional[List[str]] = Query(None),
    interval: int = Query(15, ge=1, le=120),
    book: str = Query("all"),
) -> Dict:
    """Week-ahead placeholder; reuse summary until planner is wired."""
    return await summary_api(symbols=symbols, interval=interval, book=book)

# -----------------------------------------------------------------------------
# Unified export for main.py
# -----------------------------------------------------------------------------
router = APIRouter()
router.include_router(router_pages)
router.include_router(router_api)

__all__ = ["router", "ROUTERS"]
