#!/usr/bin/env python3
# ============================================================
# queen/helpers/verify.py — v1.0
# Small shared validation helpers (DF + basic guards)
# ============================================================
from __future__ import annotations

from typing import Iterable, Sequence

import polars as pl

from queen.helpers.logger import log


def require_columns(
    df: pl.DataFrame,
    required: Sequence[str],
    *,
    ctx: str = "",
    strict: bool = False,
) -> bool:
    """Ensure DataFrame has required columns.

    Returns True if all are present, False otherwise.
    If strict=True, logs as error; else logs as warning.
    """
    if df.is_empty():
        msg = f"[Verify] Empty DataFrame in {ctx or 'require_columns'}"
        log.warning(msg)
        return False

    missing = [c for c in required if c not in df.columns]
    if missing:
        level = log.error if strict else log.warning
        level(
            f"[Verify] Missing cols {missing} "
            f"in {ctx or 'DataFrame'} (have={df.columns})"
        )
        return False

    return True


def ensure_sorted(
    df: pl.DataFrame,
    by: str | Sequence[str],
    *,
    ctx: str = "",
    ascending: bool = True,
) -> pl.DataFrame:
    """Return df sorted by the given column(s)."""
    if df.is_empty():
        return df
    try:
        return df.sort(by, descending=not ascending)
    except Exception as e:
        log.warning(f"[Verify] ensure_sorted failed in {ctx or 'ensure_sorted'} → {e}")
        return df


def ensure_time_ordered(
    df: pl.DataFrame,
    ts_col: str = "timestamp",
    *,
    ctx: str = "",
) -> pl.DataFrame:
    """Sort by timestamp if present; no-op otherwise."""
    if ts_col not in df.columns:
        log.warning(f"[Verify] {ctx or 'ensure_time_ordered'}: '{ts_col}' not in df")
        return df
    return ensure_sorted(df, ts_col, ctx=ctx)


def non_empty_symbols(symbols: Iterable[str | None]) -> list[str]:
    """Normalize a list of symbols, dropping empties/None."""
    out: list[str] = []
    for s in symbols:
        if not s:
            continue
        s = str(s).strip().upper()
        if s:
            out.append(s)
    return out


__all__ = [
    "require_columns",
    "ensure_sorted",
    "ensure_time_ordered",
    "non_empty_symbols",
]
