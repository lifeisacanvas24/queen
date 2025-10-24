#!/usr/bin/env python3
# ============================================================
# queen/helpers/instruments.py — v9.2 (Robust Loader + Caches)
# ============================================================
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional

import polars as pl
from queen.helpers.logger import log
from queen.settings import settings as SETTINGS

VALID_MODES = ("INTRADAY", "WEEKLY", "MONTHLY", "PORTFOLIO")
# Presentational/documentation hint; listing_date may be absent in some files.
INSTRUMENT_COLUMNS = ["symbol", "isin", "listing_date"]


# -------- Path Resolver -------------------------------------------------------
def _instrument_paths_for(mode: str) -> Iterable[Path]:
    mode = (mode or "MONTHLY").strip().upper()
    ex = SETTINGS.EXCHANGE["ACTIVE"]
    ex_info = SETTINGS.EXCHANGE["EXCHANGES"].get(ex, {})
    inst = ex_info.get("INSTRUMENTS", {})
    # Preferred -> fallback
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
            df = pl.read_csv(path)
        else:
            # Peek first non-empty byte to decide JSON array vs NDJSON
            head = path.read_text(encoding="utf-8", errors="ignore").lstrip()[:1]
            if head == "[":
                df = pl.read_json(path)  # JSON array
            else:
                # NDJSON (jsonlines)
                try:
                    df = pl.read_ndjson(path)  # Polars ≥ 0.20
                except Exception:
                    df = pl.read_json(path)  # fallback
        return df
    except Exception as e:
        log.error(f"[Instruments] Read failed for {path.name} → {e}")
        return pl.DataFrame()


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df

    # lower the names
    df = df.rename({c: c.lower() for c in df.columns})

    # Accept a wide set of aliases
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

    # Minimal required columns
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

    # Try requested mode
    m = get_instrument_map(mode).get(symbol_or_key)
    if m:
        return m

    # Try merged view (all modes + fallback files)
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


# -------- Cache admin ---------------------------------------------------------
def clear_instrument_cache() -> None:
    load_instruments_df.cache_clear()
    get_instrument_map.cache_clear()
    _merged_df_all_modes.cache_clear()
    log.info("[Instruments] Cache cleared.")


def cache_info() -> Dict[str, str]:
    """Return LRU cache stats for debugging/observability."""
    infos = {
        "load_instruments_df": str(load_instruments_df.cache_info()),
        "get_instrument_map": str(get_instrument_map.cache_info()),
        "_merged_df_all_modes": str(_merged_df_all_modes.cache_info()),
    }
    log.info(f"[Instruments] Cache info: {infos}")
    return infos


# -------- Self-test -----------------------------------------------------------
if __name__ == "__main__":
    print("📘 Instruments Resolver — v9.2")
    for m in ("MONTHLY", "PORTFOLIO", "WEEKLY", "INTRADAY"):
        df = load_instruments_df(m)
        print(m, len(df))
    try:
        print("NSDL →", resolve_instrument("NSDL"))
        print("Meta →", get_instrument_meta("NSDL"))
    except Exception as e:
        print("Lookup error:", e)
    print("Cache →", cache_info())
