#!/usr/bin/env python3
# ============================================================
# queen/settings/fno_universe.py — v1.0
# (F&O universe definition + loaders, Polars-only)
# ============================================================
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import polars as pl

from queen.helpers.logger import log
from queen.settings import settings as SETTINGS

# ------------------------------------------------------------
# 🗂️ File locations (settings-driven)
# ------------------------------------------------------------

# We keep this under queen/data/static/fno_universe.csv by default.
# You can move it later; just adjust this path.
FNO_UNIVERSE_CSV: Path = SETTINGS.PATHS["UNIVERSE"] / "fno_universe.csv"

# Optional: if you later want a separate file for liquid-only,
# e.g. queen/data/static/fno_liquid_intraday.csv
FNO_LIQUID_INTRADAY_CSV: Path | None = None  # not used yet

# ------------------------------------------------------------
# 📦 Internal cache
# ------------------------------------------------------------
_FNO_DF: pl.DataFrame | None = None


def _read_csv_safe(path: Path) -> pl.DataFrame:
    """Best-effort CSV reader with logging; never raises to callers."""
    if not path.exists():
        log.warning(f"[FNO_UNIVERSE] File not found: {path}")
        return pl.DataFrame()
    try:
        df = pl.read_csv(path)
        log.info(
            f"[FNO_UNIVERSE] Loaded {len(df)} rows from {path.name} "
            f"cols={df.columns}"
        )
        return df
    except Exception as e:
        log.error(f"[FNO_UNIVERSE] Failed to read {path} → {e}")
        return pl.DataFrame()


def _normalize_df(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize column names + minimal schema for downstream helpers."""
    if df.is_empty():
        return df

    # lower-case all column names
    df = df.rename({c: c.lower() for c in df.columns})

    # Ensure 'symbol' column exists
    if "symbol" not in df.columns:
        # Try common alternates
        for cand in ("SYMBOL", "name", "ticker"):
            if cand.lower() in df.columns:
                df = df.rename({cand.lower(): "symbol"})
                break

    if "symbol" not in df.columns:
        log.warning("[FNO_UNIVERSE] Missing 'symbol' column; returning empty DF.")
        return pl.DataFrame()

    # Standardize some optional columns
    if "segment" not in df.columns:
        df = df.with_columns(pl.lit("NSE_FO").alias("segment"))

    # Normalize bool-like columns (0/1 or True/False) if present
    def _as_bool(col: str) -> pl.Expr:
        return (
            pl.when(pl.col(col).cast(pl.Int64) > 0)
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias(col)
        )

    for col in ("is_index", "is_etf", "is_liquid_intraday"):
        if col in df.columns:
            df = df.with_columns(_as_bool(col))

    return df


def _load_fno_df() -> pl.DataFrame:
    df = _read_csv_safe(FNO_UNIVERSE_CSV)
    df = _normalize_df(df)
    return df


def _fno_df() -> pl.DataFrame:
    global _FNO_DF
    if _FNO_DF is None:
        _FNO_DF = _load_fno_df()
    return _FNO_DF


def reload() -> None:
    """Force reload of the F&O universe CSV."""
    global _FNO_DF
    _FNO_DF = None
    log.info("[FNO_UNIVERSE] Cache cleared; will reload on next access.")


# ------------------------------------------------------------
# 🔍 Public helpers
# ------------------------------------------------------------
def get_fno_universe_df() -> pl.DataFrame:
    """Return the full F&O universe as a Polars DataFrame (copy)."""
    df = _fno_df()
    return df.clone() if not df.is_empty() else df


def list_fno_symbols(
    *,
    segment: str | None = None,
    include_indices: bool = True,
    include_etf: bool = True,
    liquid_only: bool = False,
) -> list[str]:
    """
    List F&O symbols with basic filters.

    Args:
        segment: Optional segment filter, e.g. "NSE_FO".
        include_indices: keep index symbols (e.g., NIFTY).
        include_etf: keep ETFs.
        liquid_only: if True, only return rows where is_liquid_intraday == True
                     when that column exists; otherwise returns full list.

    Returns:
        List of symbol strings (e.g., ["RELIANCE", "HDFCBANK", ...])
    """
    df = _fno_df()
    if df.is_empty():
        return []

    out = df

    if segment is not None and "segment" in out.columns:
        out = out.filter(pl.col("segment") == segment)

    if not include_indices and "is_index" in out.columns:
        out = out.filter(~pl.col("is_index"))

    if not include_etf and "is_etf" in out.columns:
        out = out.filter(~pl.col("is_etf"))

    if liquid_only and "is_liquid_intraday" in out.columns:
        out = out.filter(pl.col("is_liquid_intraday"))

    # Always drop null/empty symbols
    out = out.filter(pl.col("symbol").is_not_null() & (pl.col("symbol") != ""))

    return out.get_column("symbol").to_list()


def list_liquid_fno_intraday_symbols(
    *,
    segment: str = "NSE_FO",
    include_indices: bool = False,
    include_etf: bool = False,
) -> list[str]:
    """Convenience: return your 'Liquid F&O Intraday' universe."""
    return list_fno_symbols(
        segment=segment,
        include_indices=include_indices,
        include_etf=include_etf,
        liquid_only=True,
    )


def is_fno_symbol(symbol: str) -> bool:
    """Return True if symbol is part of the F&O universe."""
    if not symbol:
        return False
    df = _fno_df()
    if df.is_empty():
        return False
    return (
        df.filter(pl.col("symbol") == symbol.upper())
        .select(pl.len())
        .item()  # 0 or >0
        > 0
    )
