#!/usr/bin/env python3
# ============================================================
# queen/server/routers/cockpit.py — v1.2 (Scan API + pulse cache + UI)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from queen.alerts.rules import load_rules
from queen.services.symbol_scan import run_symbol_scan
from starlette.requests import Request

router = APIRouter(prefix="/cockpit", tags=["cockpit"])

_PULSE_STATE: Dict[str, Any] = {"results": [], "ts": None}


class ScanRequest(BaseModel):
    symbols: List[str] = Field(..., description="Symbols to scan")
    rules_path: str = Field(..., description="Path to YAML rules file")
    bars: int = Field(150, ge=10, le=2000, description="History bars per TF")


class PulseRequest(BaseModel):
    symbols: List[str]
    rules_path: str
    bars: int = 150


@router.post("/scan")
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
    _PULSE_STATE["ts"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    return results


@router.get("/pulse/state")
async def pulse_state() -> Dict[str, Any]:
    return {
        "updated_at": _PULSE_STATE.get("ts"),
        "count": len(_PULSE_STATE.get("results", [])),
        "results": _PULSE_STATE.get("results", []),
    }


@router.post("/pulse/scan")
async def pulse_scan(req: PulseRequest) -> Dict[str, Any]:
    try:
        rules = load_rules(req.rules_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load rules: {e}") from e

    rules = [r for r in rules if r.symbol in set(req.symbols)]
    results = await run_symbol_scan(req.symbols, rules, bars=req.bars) if rules else []
    _PULSE_STATE["results"] = results
    _PULSE_STATE["ts"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    return {"updated_at": _PULSE_STATE["ts"], "count": len(results), "results": results}


# ---------- Minimal UI (template) ----------
@router.get("/ui")
async def cockpit_ui(request: Request):
    """Simple HTML page with auto-refresh table for pulse state."""
    templates = request.app.state.templates  # set in server/main.py
    return templates.TemplateResponse("cockpit.html", {"request": request})
