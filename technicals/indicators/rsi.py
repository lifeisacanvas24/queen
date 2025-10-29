#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/rsi.py — v1.0 (Series-native, forward-only)
# ============================================================
from __future__ import annotations

import polars as pl


def rsi(df: pl.DataFrame, length: int = 14, price_col: str = "close") -> pl.Series:
    """Wilder RSI as a Series aligned to df rows (may start with nulls)."""
    if df.is_empty() or price_col not in df.columns:
        return pl.Series(name="rsi", values=[], dtype=pl.Float64)

    close = df[price_col].cast(pl.Float64)
    delta = close.diff()

    # Polars Series-native (no Expr mixing)
    # Polars >=1.x supports Series.clip(min, max); keep it forward-only:
    gain = delta.clip(0.0, None)  # positive changes; else 0
    loss = (-delta).clip(0.0, None)  # negative changes as +ve; else 0

    # Wilder smoothing: alpha = 1/length (EWMA)
    alpha = 1.0 / float(length)
    avg_gain = gain.ewm_mean(alpha=alpha, adjust=False)
    avg_loss = loss.ewm_mean(alpha=alpha, adjust=False)

    rs = avg_gain / (avg_loss + 1e-12)  # avoid div-by-zero
    rsi_series = 100.0 - (100.0 / (1.0 + rs))
    return rsi_series.alias("rsi")


# Registry export
EXPORTS = {"rsi": rsi}
