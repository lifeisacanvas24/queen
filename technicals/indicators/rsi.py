#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/rsi.py — v0.2 (Series-native)
# ============================================================
from __future__ import annotations

import polars as pl


def rsi(df: pl.DataFrame, length: int = 14) -> pl.Series:
    """Wilder's RSI. Returns a Series aligned to df rows (may start with nulls).
    Expects columns: 'close'
    """
    if df.is_empty() or "close" not in df.columns:
        return pl.Series(name="rsi", values=[], dtype=pl.Float64)

    close = df["close"].cast(pl.Float64)
    delta = close.diff()

    # Use Series methods to avoid Expr/Series mixing
    gain = delta.clip(lower_bound=0.0)  # positive changes; else 0
    loss = (-delta).clip(lower_bound=0.0)  # negative changes (as +ve); else 0

    alpha = 1.0 / float(length)  # Wilder's smoothing
    avg_gain = gain.ewm_mean(alpha=alpha, adjust=False)
    avg_loss = loss.ewm_mean(alpha=alpha, adjust=False)

    rs = avg_gain / (avg_loss + 1e-12)  # avoid div-by-zero
    rsi_series = 100.0 - (100.0 / (1.0 + rs))
    return rsi_series.alias("rsi")


# Registry export: name -> callable(df, **params) -> pl.Series
EXPORTS = {
    "rsi": rsi,
}
