#!/usr/bin/env python3
# ============================================================
# queen/server/routers/portfolio.py — v1.2 (DRY + shared live CMP)
# ============================================================
from __future__ import annotations

from typing import Dict, List
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from queen.services.history import load_history  # add this import
from queen.services.live import cmp_snapshot
from queen.helpers.portfolio import (
    list_books, load_positions, position_for, compute_pnl, clear_positions_cache
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("/books")
async def books() -> Dict[str, List[str]]:
    return {"books": list(list_books())}

@router.get("/positions")
async def positions(book: str = Query("all", description="ank/mnk/... or 'all'")):
    try:
        data = load_positions(book)
        return JSONResponse(
            content={"book": book, "count": len(data), "positions": data},
            media_type="application/json"
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@router.get("/position")
async def one_position(symbol: str, book: str = Query("all")):
    pos = position_for(symbol, book=book)
    return {"symbol": symbol.upper(), "book": book, "position": pos}

@router.get("/pnl")
async def pnl(symbol: str, cmp: float, book: str = Query("all")):
    pos = position_for(symbol, book=book)
    res = compute_pnl(cmp, pos)
    return {
        "symbol": symbol.upper(),
        "book": book,
        "cmp": cmp,
        "position": pos,
        "pnl_abs": round(res[0], 2) if res else None,
        "pnl_pct": round(res[1], 2) if res else None,
    }

@router.post("/cache/clear")
async def cache_clear():
    clear_positions_cache()
    return {"status": "cleared"}

@router.get("/pnl/table")
async def pnl_table(
    book: str = Query("all"),
    symbols: List[str] = Query([]),
    interval: int = Query(15, ge=1)
) -> Dict:
    """Merged table of {symbol, qty, avg_price, cmp, pnl_abs, pnl_pct} for a book+symbols."""
    pos = load_positions(book)
    if not symbols:
        symbols = list(pos.keys())

    symbols = [s.upper() for s in symbols]
    snap = await cmp_snapshot(symbols, interval)
    cmps: Dict[str, float] = {r["symbol"]: r.get("cmp") for r in snap if r.get("cmp") is not None}

    out = []
    for sym in symbols:
        p = position_for(sym, book=book)
        if not p:
            out.append({"symbol": sym, "qty": None, "avg_price": None, "cmp": cmps.get(sym), "pnl_abs": None, "pnl_pct": None})
            continue
        res = compute_pnl(cmps.get(sym, 0.0), p)
        out.append({
            "symbol": sym,
            "qty": p["qty"],
            "avg_price": p["avg_price"],
            "cmp": cmps.get(sym),
            "pnl_abs": round(res[0],2) if res else None,
            "pnl_pct": round(res[1],2) if res else None
        })
    return {"book": book, "interval": interval, "count": len(out), "rows": out}
