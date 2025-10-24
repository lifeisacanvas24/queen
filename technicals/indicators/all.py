# ============================================================
# quant/indicators/all.py (v1.0 — Unified Indicator Layer)
# ============================================================
"""Unified interface for all technical indicators in Quant-Core.

Features:
    ✅ Combines Core (EMA, RSI, MACD) and Advanced (ATR, Supertrend, BB)
    ✅ Metadata tagging ("indicator_group": "core" / "advanced")
    ✅ Safe schema joins (inner merge on timestamp, symbol)
    ✅ Designed for both live-stream and backtest pipelines
"""

from __future__ import annotations

import polars as pl

from quant.indicators.advanced import attach_advanced as attach_adv
from quant.indicators.core import attach_indicators as attach_core


# ============================================================
# 🧠 Helpers
# ============================================================
def _safe_merge(df_base: pl.DataFrame, df_add: pl.DataFrame) -> pl.DataFrame:
    """Safely merge two DataFrames on timestamp and symbol (inner join)."""
    if df_add.is_empty():
        return df_base

    join_cols = [c for c in ["timestamp", "symbol"] if c in df_base.columns and c in df_add.columns]
    if not join_cols:
        # fallback — align by row position
        return pl.concat([df_base, df_add], how="horizontal")

    # Avoid duplicate columns (like close, open, etc.)
    overlapping = [c for c in df_add.columns if c in df_base.columns and c not in join_cols]
    df_add = df_add.drop(overlapping)

    merged = df_base.join(df_add, on=join_cols, how="inner")
    return merged


def _tag_columns(df: pl.DataFrame, tag: str) -> pl.DataFrame:
    """Attach metadata tag to all numeric indicator columns."""
    meta = {"indicator_group": tag}
    # Polars has no per-column metadata, so store a mapping
    df.attrs = meta  # Accessible via df.attrs if needed
    return df


# ============================================================
# ⚙️ Main entrypoint
# ============================================================
def attach_all_indicators(df: pl.DataFrame) -> pl.DataFrame:
    """Attach both core and advanced indicators safely."""
    if df.is_empty():
        return df

    # Core indicators
    core_df = attach_core(df)
    core_df = _tag_columns(core_df, "core")

    # Advanced indicators
    adv_df = attach_adv(df)
    adv_df = _tag_columns(adv_df, "advanced")

    # Safe merge
    merged = _safe_merge(core_df, adv_df)

    # Sort chronologically
    if "timestamp" in merged.columns:
        merged = merged.sort("timestamp")

    return merged


# ============================================================
# 🧩 Example usage
# ============================================================
if __name__ == "__main__":
    # Simple sanity test
    import polars as pl

    df = pl.DataFrame({
        "timestamp": pl.datetime_range("2025-01-01", "2025-01-30", "1d", eager=True),
        "open": range(100,130),
        "high": range(101,131),
        "low":  range(99,129),
        "close": range(100,130),
        "volume": [1000+i*10 for i in range(30)],
        "oi": [0]*30,
        "symbol": ["TEST"]*30
    })

    full = attach_all_indicators(df)
    print(full.tail(5))
