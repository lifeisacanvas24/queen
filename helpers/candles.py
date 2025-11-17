#!/usr/bin/env python3
# ============================================================
# queen/helpers/candles.py — v1.1
# Canonical candle helpers (CMP, ordering) on top of schema_adapter
# ============================================================
from __future__ import annotations

from typing import Optional

import polars as pl

from queen.helpers.logger import log


def ensure_sorted(df: pl.DataFrame, ts_col: str = "timestamp") -> pl.DataFrame:
    """Return df sorted by ts_col if present; safe on empty."""
    if df.is_empty() or ts_col not in df.columns:
        return df
    try:
        return df.sort(ts_col)
    except Exception as e:
        log.warning(f"[candles.ensure_sorted] sort failed → {e}")
        return df


def last_close(df: pl.DataFrame) -> Optional[float]:
    """Canonical CMP: last close from a schema-adapted candle frame.

    Assumes:
      • df comes from CandleAdapter / schema_adapter
      • it has a 'close' column
      • it's roughly time-ordered (we still just take tail(1))
    """
    try:
        if df.is_empty() or "close" not in df.columns:
            return None

        s = (
            df["close"]
            .cast(pl.Float64, strict=False)
            .drop_nulls()
        )
        if s.is_empty():
            return None

        return float(s.tail(1).item())
    except Exception as e:
        log.warning(f"[candles.last_close] failed → {e}")
        return None


__all__ = ["last_close", "ensure_sorted"]
