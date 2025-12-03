#!/usr/bin/env python3
# ============================================================
# queen/helpers/fno_universe.py — Hybrid F&O Universe Loader
# ============================================================
from __future__ import annotations

import polars as pl
from pathlib import Path
from typing import Optional, List, Dict, Any

from queen.helpers.logger import log

# ---------------------------------------------------------------------
# Load all_fo.json — structure:
# [
#   {
#     "segment": "NSE_FO",
#     "asset_symbol": "SBIN",
#     "expiry": 1769538599000,
#     "lot_size": 1500,
#     "weekly": false,
#     "asset_type": "EQUITY",
#     ... (other keys)
#   }
# ]
# ---------------------------------------------------------------------

_FNO_PATH = Path("queen/data/static/all_fo.json")

try:
    _df = pl.read_json(_FNO_PATH)
    log.info(f"[FNO] Loaded {len(_df)} F&O entries.")
except Exception as e:
    log.error(f"[FNO] Failed loading all_fo.json: {e}")
    _df = pl.DataFrame()

# Keep only required columns
_COLUMNS = [
    "asset_symbol", "expiry", "weekly", "lot_size",
    "asset_type", "segment"
]

for c in _COLUMNS:
    if c not in _df.columns:
        _df = _df.with_columns(pl.lit(None).alias(c))

FNO = _df.select(_COLUMNS).unique()


# ============================================================
# Helpers
# ============================================================

def is_fno(symbol: str) -> bool:
    """Check if symbol is part of F&O universe."""
    if not symbol:
        return False
    return symbol.upper() in FNO["asset_symbol"].unique().to_list()


def get_expiries(symbol: str) -> List[int]:
    """Return list of UNIX ms expiries for this symbol."""
    symbol = symbol.upper()
    out = FNO.filter(pl.col("asset_symbol") == symbol)["expiry"]
    return out.unique().to_list() if out.len() else []


def get_lot_size(symbol: str) -> Optional[int]:
    symbol = symbol.upper()
    out = FNO.filter(pl.col("asset_symbol") == symbol)["lot_size"]
    return out.item() if out.len() else None


def get_symbol_type(symbol: str) -> str:
    """Return 'INDEX' or 'EQUITY' or 'UNKNOWN'."""
    symbol = symbol.upper()
    out = FNO.filter(pl.col("asset_symbol") == symbol)["asset_type"]
    return out.item() if out.len() else "UNKNOWN"


def select_expiry(symbol: str, mode: str = "intraday") -> Optional[int]:
    """
    Returns nearest expiry depending on mode:
    intraday → nearest
    btst     → nearest
    swing    → nearest monthly (if available) else nearest
    """
    expiries = sorted(get_expiries(symbol))
    if not expiries:
        return None

    if mode in ("intraday", "btst"):
        return expiries[0]

    # swing → prefer monthly expiry
    df = FNO.filter(pl.col("asset_symbol") == symbol.upper())
    monthlies = df.filter(~pl.col("weekly"))["expiry"].unique().to_list()

    if monthlies:
        return sorted(monthlies)[0]

    return expiries[0]


def get_atm_strike(symbol: str, ltp: float) -> Optional[float]:
    """
    Snap LTP to nearest strike boundary.
    This is *not* option-chain dependent, only catalog-dependent.
    """
    symbol = symbol.upper()
    df = FNO.filter(pl.col("asset_symbol") == symbol)
    if df.is_empty():
        return None

    # Collect strike steps if they exist
    # If not present, default ATM rounding to nearest 50 steps
    tick = 50
    return round(ltp / tick) * tick
