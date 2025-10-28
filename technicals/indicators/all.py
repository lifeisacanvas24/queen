# ============================================================
# queen/technicals/indicators/all.py (v1.1 — Unified Indicator Layer)
# ============================================================
"""Unified interface for all technical indicators in Queen.

Features:
    ✅ Combines Core (EMA/RSI/MACD etc.) and Advanced (ATR, Supertrend, BB)
    ✅ Safe schema joins (inner on any common keys; falls back to horizontal concat)
    ✅ No I/O, no side effects — pure functions
"""

from __future__ import annotations

import polars as pl
from queen.technicals.indicators.advanced import attach_advanced as attach_adv
from queen.technicals.indicators.core import attach_indicators as attach_core


# ------------------------------------------------------------
# 🧠 Helpers
# ------------------------------------------------------------
def _safe_merge(df_base: pl.DataFrame, df_add: pl.DataFrame) -> pl.DataFrame:
    """Safely merge two DataFrames on shared keys (e.g., timestamp, symbol)."""
    if df_base.is_empty():
        return df_add
    if df_add.is_empty():
        return df_base

    # Pick join keys that both frames share (prefer timestamp/symbol if present)
    preferred = ["timestamp", "symbol"]
    shared = [c for c in preferred if c in df_base.columns and c in df_add.columns]
    if not shared:
        shared = [c for c in df_base.columns if c in df_add.columns]

    if shared:
        # Avoid duplicate non-key columns coming from df_add
        drop_cols = [
            c for c in df_add.columns if c in df_base.columns and c not in shared
        ]
        df_add = df_add.drop(drop_cols)
        return df_base.join(df_add, on=shared, how="inner")

    # No common keys → align by row position (best-effort)
    return pl.concat([df_base, df_add], how="horizontal")


# ------------------------------------------------------------
# ⚙️ Main entrypoint
# ------------------------------------------------------------
def attach_all_indicators(df: pl.DataFrame) -> pl.DataFrame:
    """Attach both core and advanced indicators safely."""
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    core_df = attach_core(df)
    adv_df = attach_adv(df)

    merged = _safe_merge(core_df, adv_df)
    if "timestamp" in merged.columns:
        merged = merged.sort("timestamp")
    return merged


# ------------------------------------------------------------
# 🧪 Local sanity
# ------------------------------------------------------------
if __name__ == "__main__":
    n = 30
    demo = pl.DataFrame(
        {
            "timestamp": pl.datetime_range(
                "2025-01-01", "2025-01-30", "1d", eager=True
            ),
            "open": pl.arange(100, 100 + n, eager=True) * 1.0,
            "high": pl.arange(101, 101 + n, eager=True) * 1.0,
            "low": pl.arange(99, 99 + n, eager=True) * 1.0,
            "close": pl.arange(100, 100 + n, eager=True) * 1.0,
            "volume": pl.lit(1000).repeat(n),
            "symbol": pl.lit("TEST").repeat(n),
        }
    )
    out = attach_all_indicators(demo)
    print(out.tail(3))
