#!/usr/bin/env python3
# ============================================================
# queen/server/routers/instruments.py — v4.1
# Market Instruments API (JSON-based, universe-aware, forward-only)
# ============================================================
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from queen.helpers import io
from queen.helpers.common import normalize_symbol
from queen.helpers.instruments import (
    filter_to_active_universe,
    get_instrument_meta,
    list_symbols,
)
from queen.helpers.logger import log
from queen.settings import settings as SETTINGS

router = APIRouter(prefix="/market/instruments", tags=["instruments"])


# -----------------------------------------------------------------------------
# Core listing endpoints
# -----------------------------------------------------------------------------
@router.get("/list")
async def list_instruments(mode: str = "INTRADAY") -> dict:
    """Return all symbols for the given mode (from static JSON)."""
    try:
        mode = (mode or "INTRADAY").strip().upper()
        symbols = list_symbols(mode)

        # normalize + dedupe + sort
        symbols = sorted({normalize_symbol(s) for s in symbols if s is not None})

        return {"mode": mode, "count": len(symbols), "symbols": symbols}
    except Exception as e:
        log.error(f"[InstrumentsAPI] list_instruments({mode}) failed → {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Instrument listing failed: {e}",
        ) from e


@router.get("/active")
async def list_active_universe(mode: str = "INTRADAY") -> dict:
    """Return symbols intersected with active_universe.csv (if present)."""
    try:
        mode = (mode or "INTRADAY").strip().upper()

        # 1) base symbols from JSON (e.g. intraday_instruments.json)
        base = list_symbols(mode)

        # 2) intersection with active_universe.csv (if exists)
        symbols = filter_to_active_universe(base)

        # 3) normalize + dedupe + sort
        symbols = sorted({normalize_symbol(s) for s in symbols if s is not None})

        return {"mode": mode, "count": len(symbols), "symbols": symbols}
    except Exception as e:
        log.error(f"[InstrumentsAPI] list_active_universe({mode}) failed → {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Active universe fetch failed: {e}",
        ) from e


@router.get("/meta/{symbol}")
async def instrument_metadata(symbol: str, mode: str = "MONTHLY") -> dict:
    """Return metadata (symbol, isin, listing_date) for a given symbol."""
    try:
        symbol_norm = normalize_symbol(symbol)
        meta = get_instrument_meta(symbol_norm, mode)
        return {
            "symbol": meta["symbol"],
            "isin": meta["isin"],
            "listing_date": meta.get("listing_date"),
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve)) from ve
    except Exception as e:
        log.error(f"[InstrumentsAPI] meta({symbol}) failed → {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Instrument metadata fetch failed: {e}",
        ) from e


@router.get("/ping")
async def instruments_ping() -> dict:
    return {"status": "ok", "message": "Instruments router active"}


# -----------------------------------------------------------------------------
# 🔍 Debug endpoint — show paths & row counts for each mode
# -----------------------------------------------------------------------------
@router.get("/debug")
async def instruments_debug() -> dict:
    """Debug helper to see which files are wired for instruments + universe.

    Returns, per mode:
      - path (resolved)
      - exists (bool)
      - format (json/csv/parquet/None)
      - rows (if readable)
      - cols (if readable)
    Also includes active_universe.csv location.
    """
    try:
        ex = SETTINGS.EXCHANGE["ACTIVE"]
        ex_cfg = SETTINGS.EXCHANGE["EXCHANGES"].get(ex, {})
        inst_cfg = ex_cfg.get("INSTRUMENTS", {})

        modes = ("INTRADAY", "MONTHLY", "WEEKLY", "PORTFOLIO")
        data: dict[str, dict] = {}

        for mode in modes:
            raw = inst_cfg.get(mode)
            if not raw:
                data[mode] = {
                    "path": None,
                    "exists": False,
                    "format": None,
                    "rows": None,
                    "cols": [],
                }
                continue

            p = Path(raw).expanduser().resolve()
            info: dict[str, object] = {
                "path": str(p),
                "exists": p.exists(),
                "format": p.suffix.lower().lstrip(".") or None,
                "rows": None,
                "cols": [],
            }

            if p.exists():
                try:
                    df = io.read_any(p)
                    info["rows"] = int(df.height)
                    info["cols"] = list(df.columns)
                except Exception as e:
                    log.warning(f"[InstrumentsAPI] debug read failed for {p.name} → {e}")

            data[mode] = info

        # active_universe.csv
        uni_path = (SETTINGS.PATHS["UNIVERSE"] / "active_universe.csv").expanduser().resolve()
        data["ACTIVE_UNIVERSE"] = {
            "path": str(uni_path),
            "exists": uni_path.exists(),
            "format": "csv",
        }

        return {
            "exchange": ex,
            "market_timezone": SETTINGS.EXCHANGE.get("MARKET_TIMEZONE"),
            "instruments": data,
        }

    except Exception as e:
        log.error(f"[InstrumentsAPI] debug() failed → {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Instruments debug failed: {e}",
        ) from e
