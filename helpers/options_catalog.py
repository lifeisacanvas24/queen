#!/usr/bin/env python3
# ============================================================
# queen/helpers/options_catalog.py — Hybrid Options Catalog
# ============================================================
from __future__ import annotations

import polars as pl
from pathlib import Path
from typing import List, Optional

from queen.helpers.logger import log

OPTIONS_PATH = Path("queen/data/static/all_options.json")

try:
    df = pl.read_json(OPTIONS_PATH)
    log.info(f"[OptionsCatalog] Loaded {len(df)} option entries.")
except Exception as e:
    log.error(f"[OptionsCatalog] Failed to load all_options.json: {e}")
    df = pl.DataFrame()

# Required columns
REQ = ["asset_symbol", "expiry", "strike_price", "instrument_type"]
for c in REQ:
    if c not in df.columns:
        df = df.with_columns(pl.lit(None).alias(c))

CAT = df.select(REQ).unique()


# ============================================================
# Helpers
# ============================================================

def get_strikes(symbol: str, expiry: int) -> List[float]:
    """Return strike list for given symbol & expiry."""
    out = CAT.filter(
        (pl.col("asset_symbol") == symbol.upper())
        & (pl.col("expiry") == expiry)
    )["strike_price"]

    return sorted(out.unique().to_list()) if out.len() else []


def validate_expiry(symbol: str, expiry: int) -> bool:
    """Return True if expiry belongs to symbol."""
    return expiry in CAT.filter(
        pl.col("asset_symbol") == symbol.upper()
    )["expiry"].unique().to_list()


def validate_strike(symbol: str, expiry: int, strike: float) -> bool:
    """Return True if strike belongs to symbol+expiry."""
    return strike in CAT.filter(
        (pl.col("asset_symbol") == symbol.upper())
        & (pl.col("expiry") == expiry)
    )["strike_price"].unique().to_list()


def get_atm_ladder(strikes: List[float], ltp: float, width: int = 2) -> dict:
    """
    Return ATM+1/+2/-1/-2 strikes.
    width = 2 → returns 5 strikes (ATM, ±1, ±2)
    """
    if not strikes:
        return {}

    # ATM = nearest by absolute difference
    atm = min(strikes, key=lambda s: abs(s - ltp))
    idx = strikes.index(atm)

    return {
        "atm": atm,
        "plus_one": strikes[idx + 1] if idx + 1 < len(strikes) else None,
        "plus_two": strikes[idx + 2] if idx + 2 < len(strikes) else None,
        "minus_one": strikes[idx - 1] if idx - 1 >= 0 else None,
        "minus_two": strikes[idx - 2] if idx - 2 >= 0 else None,
    }
