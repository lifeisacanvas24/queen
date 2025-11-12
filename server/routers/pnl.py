#!/usr/bin/env python3
# ============================================================
# queen/server/routers/pnl.py — v1.2 (CMP via shared live service)
# ============================================================
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Query
from queen.helpers.portfolio import compute_pnl, load_positions
from queen.services.live import cmp_snapshot, actionables_for

router = APIRouter(prefix="/pnl", tags=["pnl"])

@router.get("/table")
async def pnl_table(
    symbols: List[str] = Query([], description="optional filter; defaults to all in book"),
    book: str = Query("all", description="positions book (ank/mnk/... or 'all')"),
    interval: int = Query(15, ge=1, le=120),
) -> Dict:
    pos = load_positions(book)
    if not pos:
        return {"updated": __import__("datetime").datetime.utcnow().isoformat()+"Z", "book": book, "rows": []}

    wanted = {s.upper() for s in symbols} if symbols else set(pos.keys())
    syms = sorted([s for s in pos.keys() if s in wanted])

    snap = await cmp_snapshot(syms, interval)
    cmp_map = {r["symbol"]: r.get("cmp") for r in snap if r.get("cmp") is not None}

    out_rows: List[Dict] = []
    for sym in syms:
        q = float(pos[sym].get("qty", 0) or 0)
        a = float(pos[sym].get("avg_price", 0) or 0)
        cmp_ = cmp_map.get(sym)
        pnl_abs = pnl_pct = None
        if cmp_ is not None and q > 0 and a > 0:
            res = compute_pnl(cmp_, {"qty": q, "avg_price": a})
            if res:
                pnl_abs, pnl_pct = round(res[0], 2), round(res[1], 2)
        out_rows.append({"symbol": sym, "qty": q, "avg_price": a, "cmp": cmp_, "pnl_abs": pnl_abs, "pnl_pct": pnl_pct})

    return {
        "updated": __import__("datetime").datetime.utcnow().isoformat()+"Z",
        "book": book,
        "rows": out_rows,
    }
