# queen/server/routers/instruments_router.py — v3.1
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from queen.helpers.common import normalize_symbol
from queen.helpers.instruments import (
    get_instrument_meta,
    list_symbols,
    list_symbols_from_active_universe,
)
from queen.helpers.logger import log

router = APIRouter(prefix="/market/instruments", tags=["instruments"])

@router.get("/list")
async def list_instruments(mode: str = "INTRADAY") -> dict:
    try:
        mode = mode.strip().upper()
        symbols = list_symbols(mode)
        symbols = sorted({normalize_symbol(s) for s in symbols if s})
        return {"mode": mode, "count": len(symbols), "symbols": symbols}
    except Exception as e:
        log.error(f"[InstrumentsAPI] list_instruments({mode}) failed → {e}")
        raise HTTPException(status_code=500, detail=f"Instrument listing failed: {e}")

@router.get("/active")
async def list_active_universe(mode: str = "INTRADAY") -> dict:
    try:
        mode = mode.strip().upper()
        symbols = list_symbols_from_active_universe(mode)
        symbols = sorted({normalize_symbol(s) for s in symbols if s})
        return {"mode": mode, "count": len(symbols), "symbols": symbols}
    except Exception as e:
        log.error(f"[InstrumentsAPI] list_active_universe({mode}) failed → {e}")
        raise HTTPException(status_code=500, detail=f"Active universe fetch failed: {e}")

@router.get("/meta/{symbol}")
async def instrument_metadata(symbol: str, mode: str = "MONTHLY") -> dict:
    try:
        symbol = normalize_symbol(symbol)
        meta = get_instrument_meta(symbol, mode)
        return {"symbol": meta["symbol"], "isin": meta["isin"], "listing_date": meta.get("listing_date")}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        log.error(f"[InstrumentsAPI] meta({symbol}) failed → {e}")
        raise HTTPException(status_code=500, detail=f"Instrument metadata fetch failed: {e}")

@router.get("/ping")
async def instruments_ping() -> dict:
    return {"status": "ok", "message": "Instruments router active"}
