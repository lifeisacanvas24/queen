#!/usr/bin/env python3
# ============================================================
# queen/helpers/candle_adapter.py — v1.0
# Thin wrapper over schema_adapter (forward-only)
# ============================================================
from __future__ import annotations

from typing import Any, Iterable

import polars as pl

from queen.helpers.logger import log
from queen.helpers.schema_adapter import (
    DEFAULT_SCHEMA,
    finalize_candle_df,
    to_candle_df,
)


class CandleAdapter:
    """Forward-only adapter for candle data → Polars DataFrame.

    This is a thin convenience layer around queen.helpers.schema_adapter, so
    the single source of truth for schema stays there.

    Usage:
        df = CandleAdapter.to_polars(candles, symbol="TCS", isin="NSE_EQ|...")
        empty = CandleAdapter.empty_df()
    """

    DEFAULT_SCHEMA = DEFAULT_SCHEMA

    @staticmethod
    def to_polars(
        candles: Iterable[Iterable[Any]],
        symbol: str,
        isin: str,
    ) -> pl.DataFrame:
        """Convert raw candle rows into a typed Polars DataFrame.

        candles: list of [ts, open, high, low, close, volume, oi]
        """
        try:
            df = to_candle_df(list(candles), symbol)
            if df.is_empty():
                return CandleAdapter.empty_df()
            return finalize_candle_df(df, symbol, isin)
        except Exception as e:
            log.error(f"[CandleAdapter] to_polars failed for {symbol} → {e}")
            return CandleAdapter.empty_df()

    @staticmethod
    def empty_df() -> pl.DataFrame:
        """Return a typed empty candle frame (schema-consistent)."""
        return pl.DataFrame(schema=DEFAULT_SCHEMA + ["symbol", "isin"])

    @staticmethod
    def summary(df: pl.DataFrame, name: str = "candles") -> dict[str, Any]:
        """Tiny helper for diagnostics; safe on empty frames."""
        try:
            return {
                "name": name,
                "rows": int(df.height),
                "cols": list(df.columns),
            }
        except Exception:
            return {"name": name, "rows": 0, "cols": []}


__all__ = ["CandleAdapter"]
