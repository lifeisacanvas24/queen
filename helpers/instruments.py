#!/usr/bin/env python3
# ============================================================
# queen/helpers/instruments.py — v9.3 (Robust Loader + Caches)
# ============================================================
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional

import polars as pl
from queen.helpers.logger import log
from queen.settings import settings as SETTINGS
from queen.settings.settings import PATHS as _PATHS

VALID_MODES = ("INTRADAY", "WEEKLY", "MONTHLY", "PORTFOLIO")
INSTRUMENT_COLUMNS = ["symbol", "isin", "listing_date"]  # optional: listing_date


# -------- Path Resolver -------------------------------------------------------
def _instrument_paths_for(mode: str) -> Iterable[Path]:
    mode = (mode or "MONTHLY").strip().upper()
    ex = SETTINGS.EXCHANGE["ACTIVE"]
    ex_info = SETTINGS.EXCHANGE["EXCHANGES"].get(ex, {})
    inst = ex_info.get("INSTRUMENTS", {})
    wanted = [inst.get(mode), inst.get("APPROVED_SYMBOLS")]
    return [Path(p).expanduser().resolve() for p in wanted if p]


def _all_instrument_paths() -> Iterable[Path]:
    ex = SETTINGS.EXCHANGE["ACTIVE"]
    inst = SETTINGS.EXCHANGE["EXCHANGES"].get(ex, {}).get("INSTRUMENTS", {})
    paths = [inst.get(m) for m in VALID_MODES] + [inst.get("APPROVED_SYMBOLS")]
    uniq: Dict[str, Path] = {}
    for p in paths:
        if p:
            rp = str(Path(p).expanduser().resolve())
            uniq[rp] = Path(rp)
    return uniq.values()


# -------- Readers -------------------------------------------------------------
def _read_any(path: Path) -> pl.DataFrame:
    if not path.exists():
        log.warning(f"[Instruments] File missing: {path}")
        return pl.DataFrame()

    try:
        suf = path.suffix.lower()
        if suf == ".csv":
            return pl.read_csv(path)

        # Peek first non-whitespace byte in binary
        with path.open("rb") as fh:
            # skip leading whitespace/newlines
            first = b""
            while True:
                ch = fh.read(1)
                if not ch:
                    break
                if not ch.isspace():
                    first = ch
                    break
        if first == b"[":
            return pl.read_json(path)  # JSON array
        # NDJSON (jsonlines) or fallback JSON
        try:
            return pl.read_ndjson(path)
        except Exception:
            return pl.read_json(path)
    except Exception as e:
        log.error(f"[Instruments] Read failed for {path.name} → {e}")
        return pl.DataFrame()


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df

    df = df.rename({c: c.lower() for c in df.columns})

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

    if "listing_date" in df.columns:
        try:
            df = df.with_columns(
                pl.col("listing_date").str.strptime(pl.Date, strict=False)
            )
        except Exception:
            log.warning("[Instruments] listing_date parse skipped.")

    required = {"symbol", "isin"}
    missing = required - set(df.columns)
    if missing:
        log.warning(
            f"[Instruments] Missing required columns after normalize: {missing}"
        )
        return pl.DataFrame()

    # Deduplicate by symbol
    return df.unique(subset=["symbol"], keep="first")


# -------- Cached loaders ------------------------------------------------------
@lru_cache(maxsize=None)
def load_instruments_df(mode: str = "MONTHLY") -> pl.DataFrame:
    for p in _instrument_paths_for(mode):
        df = _normalize_columns(_read_any(p))
        if not df.is_empty():
            log.info(f"[Instruments] Loaded {len(df)} rows from {p.name}")
            return df
        log.warning(f"[Instruments] {p.name} empty or invalid; trying fallback...")
    log.error(f"[Instruments] No valid instrument data for mode={mode}")
    return pl.DataFrame()


@lru_cache(maxsize=None)
def _merged_df_all_modes() -> pl.DataFrame:
    parts = []
    for p in _all_instrument_paths():
        dfp = _normalize_columns(_read_any(p))
        if not dfp.is_empty():
            parts.append(dfp)
    if parts:
        merged = pl.concat(parts, how="vertical").unique(
            subset=["symbol"], keep="first"
        )
        log.info(
            f"[Instruments] Merged view: {len(merged)} total symbols across all sources"
        )
        return merged
    return pl.DataFrame()


# -------- Lookups -------------------------------------------------------------
@lru_cache(maxsize=4096)
def get_listing_date(symbol: str) -> date | None:
    """Return the listing date for a given symbol, or None if unavailable."""
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
        pass
    return None


@lru_cache(maxsize=None)
def get_instrument_map(mode: str = "MONTHLY") -> Dict[str, str]:
    df = load_instruments_df(mode)
    if df.is_empty():
        log.warning(f"[Instruments] Empty dataset for mode '{mode}'.")
        return {}
    return dict(zip(df["symbol"].to_list(), df["isin"].to_list()))


def resolve_instrument(symbol_or_key: str, mode: str = "MONTHLY") -> str:
    if "|" in symbol_or_key:
        return symbol_or_key

    m = get_instrument_map(mode).get(symbol_or_key)
    if m:
        return m

    merged = _merged_df_all_modes()
    if not merged.is_empty():
        row = merged.filter(pl.col("symbol") == symbol_or_key)
        if not row.is_empty():
            return row["isin"].item()

    msg = f"[Instruments] Unknown symbol: {symbol_or_key}"
    log.warning(msg)
    raise ValueError(msg)


def get_symbol_from_isin(isin: str, mode: str = "MONTHLY") -> Optional[str]:
    df = load_instruments_df(mode)
    if df.is_empty():
        df = _merged_df_all_modes()
        if df.is_empty():
            return None
    row = df.filter(pl.col("isin") == isin)
    return row["symbol"].item() if not row.is_empty() else None


def get_instrument_meta(symbol: str, mode: str = "MONTHLY") -> Dict[str, Optional[str]]:
    df = load_instruments_df(mode)
    if df.is_empty():
        df = _merged_df_all_modes()
    if df.is_empty():
        raise ValueError("Instrument dataset not loaded.")

    row = df.filter(pl.col("symbol") == symbol)
    if row.is_empty():
        raise ValueError(f"Unknown symbol: {symbol}")

    meta = {"symbol": symbol, "isin": row["isin"].item()}
    if "listing_date" in row.columns:
        try:
            meta["listing_date"] = row["listing_date"].item()
        except Exception:
            meta["listing_date"] = None
    return meta


def validate_historical_range(
    symbol: str, start_date: date, mode: str = "MONTHLY"
) -> bool:
    meta = get_instrument_meta(symbol, mode)
    listing_date = meta.get("listing_date")
    if not listing_date:
        return True
    if isinstance(listing_date, str):
        try:
            listing_date = date.fromisoformat(listing_date)
        except Exception:
            return True
    if start_date < listing_date:
        log.warning(f"[RangeCheck] {symbol}: {start_date} < {listing_date}")
        return False
    return True


def list_symbols(mode: str = "MONTHLY") -> list[str]:
    df = load_instruments_df(mode)
    return df["symbol"].to_list() if not df.is_empty() else []


# -------- Cache admin ---------------------------------------------------------
def clear_instrument_cache() -> None:
    load_instruments_df.cache_clear()
    get_instrument_map.cache_clear()
    _merged_df_all_modes.cache_clear()
    get_listing_date.cache_clear()
    log.info("[Instruments] Cache cleared.")


def cache_info() -> Dict[str, str]:
    infos = {
        "load_instruments_df": str(load_instruments_df.cache_info()),
        "get_instrument_map": str(get_instrument_map.cache_info()),
        "_merged_df_all_modes": str(_merged_df_all_modes.cache_info()),
        "get_listing_date": str(get_listing_date.cache_info()),
    }
    log.info(f"[Instruments] Cache info: {infos}")
    return infos


# -------- Universe helpers (optional) -----------------------------------------
def _active_universe_csv() -> Path:
    try:
        from queen.settings.settings import PATHS

        return (PATHS["UNIVERSE"] / "active_universe.csv").expanduser().resolve()
    except Exception:
        return Path("active_universe.csv")  # harmless fallback


@lru_cache(maxsize=1)
def load_active_universe() -> set[str]:
    """Load 'active_universe.csv' with at least a 'symbol' column; returns a set."""
    p = _active_universe_csv()
    if not p.exists():
        return set()
    try:
        df = pl.read_csv(p)
        cols = {c.lower() for c in df.columns}
        col = (
            "symbol"
            if "symbol" in cols
            else next((c for c in df.columns if c.lower() == "symbol"), None)
        )
        if not col:
            return set()
        return set(df[col].drop_nulls().unique().to_list())
    except Exception:
        return set()


def filter_to_active_universe(symbols: Iterable[str]) -> list[str]:
    uni = load_active_universe()
    if not uni:
        return list(symbols)
    return [s for s in symbols if s in uni]


def list_symbols_from_active_universe(mode: str = "MONTHLY") -> list[str]:
    """If {PATHS['UNIVERSE']}/active_universe.csv exists with a 'symbol' column,
    return its intersection with the instrument list. Otherwise fall back to
    the full list for the mode.
    """
    base = set(list_symbols(mode))
    ufile = (_PATHS["UNIVERSE"] / "active_universe.csv").expanduser().resolve()
    if not ufile.exists() or not ufile.is_file():
        return sorted(base)

    try:
        udf = pl.read_csv(ufile)
        if "symbol" not in udf.columns:
            return sorted(base)
        allowed = set(udf["symbol"].drop_nulls().unique().to_list())
        if not allowed:
            return sorted(base)
        return sorted(base & allowed)
    except Exception as e:
        log.warning(f"[Instruments] Universe filter skipped ({e})")
        return sorted(base)


# -------- Self-test -----------------------------------------------------------
if __name__ == "__main__":
    print("📘 Instruments Resolver — v9.3")
    for m in ("MONTHLY", "PORTFOLIO", "WEEKLY", "INTRADAY"):
        df = load_instruments_df(m)
        print(m, len(df))
    try:
        print("NSDL →", resolve_instrument("NSDL"))
        print("Meta →", get_instrument_meta("NSDL"))
        print("List →", list_symbols()[:5])
    except Exception as e:
        print("Lookup error:", e)
    print("Cache →", cache_info())
