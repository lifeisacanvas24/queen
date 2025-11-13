#!/usr/bin/env python3
# ============================================================
# queen/helpers/instruments.py — v10.1
# Static JSON Instruments (NSE/BSE) + Caches + Universe Filter
# ============================================================

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

import polars as pl

from queen.helpers import io
from queen.helpers.common import normalize_symbol
from queen.helpers.logger import log
from queen.settings import settings as SETTINGS

# Logical instrument universes we support
VALID_MODES = ("INTRADAY", "WEEKLY", "MONTHLY")

# Expected JSON structure:
# [
#   { "symbol": "FORCEMOT", "isin": "NSE_EQ|INE451A01017" },
#   { "symbol": "NSDL", "isin": "BSE_EQ|INE301O01023", "listing_date": "2025-08-06" }
# ]
INSTRUMENT_COLUMNS = ["symbol", "isin", "listing_date"]  # listing_date optional


# ============================================================
# 📁 Path Resolution (uses EXCHANGE dict directly)
# ============================================================
def _instrument_path_for(mode: str) -> Path | None:
    """Resolve the JSON file path for a given mode."""
    mode = (mode or "MONTHLY").strip().upper()
    ex_cfg = getattr(SETTINGS, "EXCHANGE", None)
    if not isinstance(ex_cfg, dict):
        log.error("[Instruments] SETTINGS.EXCHANGE must be a dict.")
        return None

    active = ex_cfg.get("ACTIVE")
    exchanges = ex_cfg.get("EXCHANGES", {})
    ex_info = exchanges.get(active, {})
    inst_cfg = ex_info.get("INSTRUMENTS", {})

    path = inst_cfg.get(mode)
    if not path:
        log.warning(f"[Instruments] No path configured for mode={mode} in EXCHANGE.INSTRUMENTS.")
        return None

    return Path(path).expanduser().resolve()


def _all_instrument_paths() -> Iterable[Path]:
    """Return all distinct instrument JSON paths across VALID_MODES."""
    seen: dict[str, Path] = {}
    for m in VALID_MODES:
        p = _instrument_path_for(m)
        if p:
            rp = str(p)
            if rp not in seen:
                seen[rp] = p
    return seen.values()


# ============================================================
# 📚 Readers (via queen.helpers.io)
# ============================================================
def _read_instruments(path: Path | None) -> pl.DataFrame:
    """Read instrument data using the shared IO layer."""
    if not path:
        return pl.DataFrame()
    df = io.read_json(path)
    if df.is_empty():
        log.warning(f"[Instruments] Empty or missing: {path}")
    return df


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize and sanitize instrument columns."""
    if df.is_empty():
        return df

    # lowercase column names
    df = df.rename({c: c.lower() for c in df.columns})

    # Alias mapping for flexibility
    alias = {
        "tradingsymbol": "symbol",
        "ticker": "symbol",
        "symbol_name": "symbol",
        "name": "symbol",
        "instrument_key": "isin",
        "isinid": "isin",
        "token": "isin",
        "exchange_token": "isin",
        "listingdate": "listing_date",
        "listing_dt": "listing_date",
    }
    need_rename = {
        k: v for k, v in alias.items() if k in df.columns and v not in df.columns
    }
    if need_rename:
        df = df.rename(need_rename)

    # Parse listing_date → Date if present
    if "listing_date" in df.columns:
        try:
            df = df.with_columns(
                pl.col("listing_date")
                .cast(pl.Utf8)
                .str.strptime(pl.Date, strict=False)
            )
        except Exception:
            log.warning("[Instruments] listing_date parse skipped.")

    # Ensure required cols exist
    required = {"symbol", "isin"}
    missing = required - set(df.columns)
    if missing:
        log.warning(f"[Instruments] Missing required columns: {missing}")
        return pl.DataFrame()

    # Normalize symbol casing
    df = df.with_columns(
        pl.col("symbol")
        .map_elements(normalize_symbol, return_dtype=pl.Utf8)
        .alias("symbol")
    )

    # Deduplicate by symbol
    return df.unique(subset=["symbol"], keep="first")


# ============================================================
# 🧠 Cached loaders
# ============================================================
@cache
def load_instruments_df(mode: str = "MONTHLY") -> pl.DataFrame:
    """Load instruments for a specific mode from STATIC JSON."""
    p = _instrument_path_for(mode)
    df_raw = _read_instruments(p)
    df = _normalize_columns(df_raw)
    if df.is_empty():
        log.error(f"[Instruments] No valid instrument data for mode={mode}")
        return pl.DataFrame()
    log.info(f"[Instruments] Loaded {len(df)} rows for mode={mode} from {p.name}")
    return df


@cache
def _merged_df_all_modes() -> pl.DataFrame:
    """Merged view across all instrument sources (for fallback lookups)."""
    parts = []
    for p in _all_instrument_paths():
        df = _normalize_columns(_read_instruments(p))
        if not df.is_empty():
            parts.append(df)
    if not parts:
        return pl.DataFrame()
    merged = (
        pl.concat(parts, how="vertical")
        .unique(subset=["symbol"], keep="first")
    )
    log.info(
        f"[Instruments] Merged instruments: {len(merged)} symbols across all modes"
    )
    return merged


# ============================================================
# 🔍 Lookups
# ============================================================
@lru_cache(maxsize=4096)
def get_listing_date(symbol: str) -> date | None:
    """Return listing date for symbol, if present in MONTHLY file."""
    symbol = normalize_symbol(symbol)
    df = load_instruments_df("MONTHLY")
    if df.is_empty() or "symbol" not in df.columns:
        return None
    try:
        row = df.filter(pl.col("symbol") == symbol).select("listing_date").head(1)
        if row.is_empty():
            return None
        val = row.item(0, 0)
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            try:
                return date.fromisoformat(val)
            except Exception:
                return None
    except Exception:
        return None
    return None


@cache
def get_instrument_map(mode: str = "MONTHLY") -> dict[str, str]:
    """Symbol → isin map for a given mode."""
    df = load_instruments_df(mode)
    if df.is_empty():
        log.warning(f"[Instruments] Empty dataset for mode '{mode}'.")
        return {}
    return dict(zip(df["symbol"].to_list(), df["isin"].to_list()))


def resolve_instrument(symbol_or_key: str, mode: str = "MONTHLY") -> str:
    """Resolve a symbol or instrument key to its broker instrument-key (isin)."""
    symbol_or_key = normalize_symbol(symbol_or_key)
    # Already "NSE_EQ|..." etc → treat as instrument key
    if "|" in symbol_or_key:
        return symbol_or_key

    # Mode-local map first
    m = get_instrument_map(mode).get(symbol_or_key)
    if m:
        return m

    # Fallback: merged view
    merged = _merged_df_all_modes()
    if not merged.is_empty():
        row = merged.filter(pl.col("symbol") == symbol_or_key)
        if not row.is_empty():
            return row["isin"].item()

    msg = f"[Instruments] Unknown symbol: {symbol_or_key}"
    log.warning(msg)
    raise ValueError(msg)


def get_symbol_from_isin(isin: str, mode: str = "MONTHLY") -> str | None:
    """Reverse lookup: ISIN/instrument-key → symbol."""
    df = load_instruments_df(mode)
    if df.is_empty():
        df = _merged_df_all_modes()
        if df.is_empty():
            return None
    row = df.filter(pl.col("isin") == isin)
    return row["symbol"].item() if not row.is_empty() else None


def get_instrument_meta(symbol: str, mode: str = "MONTHLY") -> dict[str, Any]:
    """Return dict with symbol, isin, and optional listing_date."""
    symbol = normalize_symbol(symbol)
    df = load_instruments_df(mode)
    if df.is_empty():
        df = _merged_df_all_modes()
    if df.is_empty():
        raise ValueError("Instrument dataset not loaded.")

    row = df.filter(pl.col("symbol") == symbol)
    if row.is_empty():
        raise ValueError(f"Unknown symbol: {symbol}")

    meta: dict[str, Any] = {
        "symbol": symbol,
        "isin": row["isin"].item(),
    }
    if "listing_date" in row.columns:
        try:
            meta["listing_date"] = row["listing_date"].item()
        except Exception:
            meta["listing_date"] = None
    return meta


def validate_historical_range(
    symbol: str,
    start_date: date,
    mode: str = "MONTHLY",
) -> bool:
    """Ensure the requested historical range does not predate listing."""
    symbol = normalize_symbol(symbol)
    listing = get_listing_date(symbol)
    if not listing:
        return True
    if isinstance(listing, str):
        try:
            listing = date.fromisoformat(listing)
        except Exception:
            return True
    if start_date < listing:
        log.warning(f"[RangeCheck] {symbol}: {start_date} < {listing}")
        return False
    return True


def list_symbols(mode: str = "MONTHLY") -> list[str]:
    """Return all symbols for the given mode (from static JSON)."""
    df = load_instruments_df(mode)
    return df["symbol"].drop_nulls().unique().to_list() if not df.is_empty() else []


# ============================================================
# 🌌 Active Universe (optional filter for cockpit)
# ============================================================
def _active_universe_csv() -> Path:
    """Locate active_universe.csv if present.

    Priority:
      1) STATIC/active_universe.csv
      2) PATHS['UNIVERSE']/active_universe.csv
      3) fallback: STATIC/active_universe.csv (even if missing)
    """
    static_path = (SETTINGS.PATHS["STATIC"] / "active_universe.csv").expanduser().resolve()
    if static_path.exists():
        return static_path

    try:
        uni_root = SETTINGS.PATHS["UNIVERSE"]
        uni_path = (uni_root / "active_universe.csv").expanduser().resolve()
        if uni_path.exists():
            return uni_path
    except Exception:
        pass

    # harmless default (may not exist)
    return static_path


@lru_cache(maxsize=1)
def load_active_universe() -> set[str]:
    """Load 'active_universe.csv' and normalize symbols.

    Expected structure:
        symbol
        FORCEMOT
        GODFRYPHLP
        ...
    """
    p = _active_universe_csv()
    if not p.exists():
        log.info("[Instruments] active_universe.csv not found → using full list.")
        return set()
    try:
        df = io.read_csv(p)
        if df.is_empty():
            return set()
        col = None
        for c in df.columns:
            if c.lower() == "symbol":
                col = c
                break
        if not col:
            return set()
        symbols = set(df[col].drop_nulls().unique().to_list())
        return {normalize_symbol(s) for s in symbols if s}
    except Exception as e:
        log.warning(f"[Instruments] Universe load failed ({e})")
        return set()


def filter_to_active_universe(symbols: Iterable[str]) -> list[str]:
    """Filter an iterable of symbols by the active universe (if present)."""
    uni = load_active_universe()
    if not uni:
        return [normalize_symbol(s) for s in symbols]
    return [normalize_symbol(s) for s in symbols if normalize_symbol(s) in uni]


# ============================================================
# 🧹 Cache Admin
# ============================================================
def clear_instrument_cache() -> None:
    load_instruments_df.cache_clear()
    get_instrument_map.cache_clear()
    _merged_df_all_modes.cache_clear()
    get_listing_date.cache_clear()
    load_active_universe.cache_clear()
    log.info("[Instruments] Cache cleared.")


def cache_info() -> dict[str, str]:
    infos = {
        "load_instruments_df": str(load_instruments_df.cache_info()),
        "get_instrument_map": str(get_instrument_map.cache_info()),
        "_merged_df_all_modes": str(_merged_df_all_modes.cache_info()),
        "get_listing_date": str(get_listing_date.cache_info()),
        "load_active_universe": str(load_active_universe.cache_info()),
    }
    log.info(f"[Instruments] Cache info: {infos}")
    return infos


# ============================================================
# 🧪 Self-Test
# ============================================================
if __name__ == "__main__":
    print("📘 Instruments Resolver — v10.1 (STATIC JSON + Universe)")
    for m in ("INTRADAY", "MONTHLY", "WEEKLY"):
        df = load_instruments_df(m)
        print(m, "→", len(df), "rows")
    try:
        print("Intraday symbols sample:", list_symbols("INTRADAY")[:10])
        base = list_symbols("INTRADAY")
        print("Universe-filtered sample:", filter_to_active_universe(base)[:10])
    except Exception as e:
        print("Lookup error:", e)
    print("Cache →", cache_info())
