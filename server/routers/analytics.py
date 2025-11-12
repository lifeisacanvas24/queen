#!/usr/bin/env python3
# ============================================================
# queen/server/routers/analytics.py — v1.0 (Top-N actionables)
# ============================================================
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Query
from queen.daemons.live_engine import MonitorConfig, _one_pass
from queen.helpers.portfolio import load_positions
from queen.services.scoring import action_for, compute_indicators

try:
    from queen.helpers.instruments import list_intraday_symbols
except ImportError:
    from queen.helpers.instruments import list_symbols as _ls
    def list_intraday_symbols() -> List[str]:
        return _ls("INTRADAY")

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/top_actionables")
async def top_actionables(
    limit: int = Query(10, ge=1, le=50),
    book: str = Query("all"),
    interval: int = Query(15, ge=1, le=120),
    symbols: Optional[List[str]] = Query(None, description="Override universe"),
) -> Dict:
    syms = symbols or list_intraday_symbols()
    pos_map = load_positions(book)

    cfg = MonitorConfig(symbols=syms, interval_min=interval, view="compact")
    raw = await _one_pass(cfg)

    rows: List[Dict] = []
    for r in raw:
        df = r.get("df")
        sym = r.get("symbol")
        if not sym or df is None or df.is_empty():
            continue
        ind = compute_indicators(df)
        if not ind:
            continue
        row = action_for(sym, ind, book=book, use_uc_lc=True)
        row["held"] = sym in pos_map
        rows.append(row)

    # Sort by score desc, then BUY/ADD first, HOLD, then others
    prio = {"BUY": 0, "ADD": 0, "HOLD": 1}
    rows.sort(key=lambda x: (-(x.get("score") or 0), prio.get(x.get("decision",""), 2)))

    return {"count": len(rows), "rows": rows[:limit]}
