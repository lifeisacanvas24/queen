#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_instruments.py — v1.0
# ============================================================
from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from queen.helpers import io
from queen.helpers.instruments import (
    clear_instrument_cache,
    get_instrument_map,
    get_instrument_meta,
    get_listing_date,
    get_symbol_from_isin,
    list_symbols,
    list_symbols_from_active_universe,
    resolve_instrument,
)
from queen.settings.settings import EXCHANGE, PATHS


def _seed_instrument_sources() -> None:
    """Create tiny instrument sources in STATIC + UNIVERSE."""
    static = Path(EXCHANGE["EXCHANGES"][EXCHANGE["ACTIVE"]]["INSTRUMENTS"]["MONTHLY"]).expanduser()
    intraday = Path(EXCHANGE["EXCHANGES"][EXCHANGE["ACTIVE"]]["INSTRUMENTS"]["INTRADAY"]).expanduser()
    universe_dir = PATHS["UNIVERSE"]

    static.parent.mkdir(parents=True, exist_ok=True)
    intraday.parent.mkdir(parents=True, exist_ok=True)
    universe_dir.mkdir(parents=True, exist_ok=True)

    # Minimal MONTHLY/INTRADAY sets (note: lowercase/whitespace to test normalization)
    df_monthly = pl.DataFrame({
        "symbol": ["  nsdl  ", "Reliance", "tcs"],
        "isin":   ["NSDL|ISIN", "RELIANCE|ISIN", "TCS|ISIN"],
        "listing_date": [date(2023,1,1), date(2000,1,1), date(2004,1,1)]
    })
    df_intraday = pl.DataFrame({
        "symbol": ["nsdl", "reliance"],
        "isin":   ["NSDL|ISIN", "RELIANCE|ISIN"],
    })

    io.write_json(df_monthly, static)
    io.write_json(df_intraday, intraday)

    # Active universe filter
    io.write_csv(pl.DataFrame({"symbol": ["NSDL", "TCS"]}), universe_dir / "active_universe.csv")

def main():
    _seed_instrument_sources()
    clear_instrument_cache()  # ensure clean slate

    # Basic listings
    syms_monthly = list_symbols("MONTHLY")
    assert "NSDL" in syms_monthly and "RELIANCE" in syms_monthly and "TCS" in syms_monthly

    # Map + resolves
    m = get_instrument_map("MONTHLY")
    assert m.get("NSDL") == "NSDL|ISIN"
    assert resolve_instrument("nsdl") == "NSDL|ISIN"
    assert get_symbol_from_isin("RELIANCE|ISIN", "MONTHLY") == "RELIANCE"

    # Meta + listing date
    meta = get_instrument_meta("tcs", "MONTHLY")
    assert meta["symbol"] == "TCS" and meta["isin"] == "TCS|ISIN"
    ld = get_listing_date("tcs")
    assert isinstance(ld, date)

    # Active universe intersection
    filtered = list_symbols_from_active_universe("MONTHLY")
    assert filtered == ["NSDL", "TCS"]  # sorted & intersected

    print("✅ smoke_instruments: passed")

if __name__ == "__main__":
    main()
