#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_instruments.py — v1.1 (schema-aligned)
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
    """Create tiny instrument sources in STATIC + UNIVERSE.

    Note:
        We now seed **schema-correct** instrument keys:
        - meta["isin"] holds the Upstox-style instrument_key, e.g. 'NSE_EQ|INE002A01018'
        This mirrors the real static JSON used in production.

    """
    instruments_cfg = EXCHANGE["EXCHANGES"][EXCHANGE["ACTIVE"]]["INSTRUMENTS"]
    static = Path(instruments_cfg["MONTHLY"]).expanduser()
    intraday = Path(instruments_cfg["INTRADAY"]).expanduser()
    universe_dir = PATHS["UNIVERSE"]

    static.parent.mkdir(parents=True, exist_ok=True)
    intraday.parent.mkdir(parents=True, exist_ok=True)
    universe_dir.mkdir(parents=True, exist_ok=True)

    # Minimal MONTHLY/INTRADAY sets
    # (note: lowercase/whitespace to test normalization)
    df_monthly = pl.DataFrame(
        {
            "symbol": ["  nsdl  ", "Reliance", "tcs"],
            # Treat "isin" as instrument_key, same as real static JSON.
            "isin": [
                "NSE_EQ|INEA00000101",  # fake but schema-correct NSDL key
                "NSE_EQ|INE002A01018",  # RELIANCE (real-format example)
                "NSE_EQ|INE467B01029",  # TCS (real-format example)
            ],
            "listing_date": [date(2023, 1, 1), date(2000, 1, 1), date(2004, 1, 1)],
        }
    )

    df_intraday = pl.DataFrame(
        {
            "symbol": ["nsdl", "reliance"],
            "isin": [
                "NSE_EQ|INEA00000101",
                "NSE_EQ|INE002A01018",
            ],
        }
    )

    # These helpers should serialize to the same shape as production:
    #   [
    #     {"symbol": "...", "isin": "...", "listing_date": "..."},
    #     ...
    #   ]
    io.write_json(df_monthly, static)
    io.write_json(df_intraday, intraday)

    # Active universe filter
    io.write_csv(
        pl.DataFrame({"symbol": ["NSDL", "TCS"]}),
        universe_dir / "active_universe.csv",
    )


def main():
    _seed_instrument_sources()
    clear_instrument_cache()  # ensure clean slate

    # ---------- Basic listings ----------
    syms_monthly = list_symbols("MONTHLY")
    assert "NSDL" in syms_monthly
    assert "RELIANCE" in syms_monthly
    assert "TCS" in syms_monthly

    # ---------- Map + resolves ----------
    m = get_instrument_map("MONTHLY")
    # map should return the instrument_key stored under "isin"
    assert m.get("NSDL") == "NSE_EQ|INEA00000101"
    assert m.get("RELIANCE") == "NSE_EQ|INE002A01018"
    assert m.get("TCS") == "NSE_EQ|INE467B01029"

    # resolve_instrument must return a proper Upstox instrument_key
    assert resolve_instrument("nsdl") == "NSE_EQ|INEA00000101"
    assert resolve_instrument("RELIANCE") == "NSE_EQ|INE002A01018"

    # get_symbol_from_isin should invert that map
    assert get_symbol_from_isin("NSE_EQ|INE002A01018", "MONTHLY") == "RELIANCE"

    # ---------- Meta + listing date ----------
    meta = get_instrument_meta("tcs", "MONTHLY")
    assert meta["symbol"] == "TCS"
    assert meta["isin"] == "NSE_EQ|INE467B01029"

    ld = get_listing_date("tcs")
    assert isinstance(ld, date)

    # ---------- Active universe intersection ----------
    filtered = list_symbols_from_active_universe("MONTHLY")
    # Should be sorted + intersected with active_universe.csv
    assert filtered == ["NSDL", "TCS"]

    print("✅ smoke_instruments: passed")


if __name__ == "__main__":
    main()
