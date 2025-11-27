#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_registry.py — v2.0 (FINAL)
# Sector-wise, ratio-wise fundamentals registry
# ============================================================
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import polars as pl
# from queen.helpers.logger import log # Assume log is available
class Logger:
    def info(self, msg): print(msg)
    def warning(self, msg): print(msg)
    def error(self, msg): print(msg)
log = Logger()

# ------------------------------------------------------------
# Helper: pick first existing column
# ------------------------------------------------------------
def _pick_col(df: pl.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

# ------------------------------------------------------------
# Fundamentals Registry
# ------------------------------------------------------------
class FundamentalsRegistry:
    """Stores:
    • Global metric stats (mean/std/min/max)
    • Sector-wise stats
    • Metric column list (after filtering)
    """

    def __init__(self):
        self.sector_map: Dict[str, Dict[str, float]] = {}
        self.global_stats: Dict[str, float] = {}
        self.columns: List[str] = []

    # ----------------------------------------------------------
    # Core Builder
    # ----------------------------------------------------------
    def build(self, df: pl.DataFrame, metric_columns: Sequence[str]):
        if df.is_empty():
            self._reset("Empty DataFrame")
            return

        # Filter to only existing metric columns
        cols = [c for c in metric_columns if c in df.columns and df[c].dtype.is_numeric()]
        if not cols:
            self._reset("No numeric metric columns found")
            return

        self.columns = cols

        # Determine Symbol and Sector column names
        symbol_col = _pick_col(df, ["Symbol", "symbol"])
        sector_col = _pick_col(df, ["Sector", "sector"])

        # 1. Global Stats
        global_exprs = [
            pl.col(c).mean().alias(f"{c}_global_mean") for c in cols
        ] + [
            pl.col(c).std().alias(f"{c}_global_std") for c in cols
        ]

        # Compute global stats over the entire DF (one row)
        global_stats_df = df.select(global_exprs).row(0, named=True)
        self.global_stats = global_stats_df or {}

        # 2. Sector Stats
        if not sector_col:
            log.warning("[FUND-REGISTRY] No Sector column found, skipping sector stats.")
            self.sector_map = {}
            return

        sector_exprs = []
        for c in cols:
            sector_exprs += [
                pl.col(c).mean().alias(f"{c}__mean"),
                pl.col(c).std().alias(f"{c}__std"),
                pl.col(c).min().alias(f"{c}__min"),
                pl.col(c).max().alias(f"{c}__max"),
            ]

        # Group by Sector and aggregate
        sec_df = df.group_by(sector_col).agg(sector_exprs)

        out: Dict[str, Dict[str, float]] = {}
        for row in sec_df.iter_rows(named=True):
            sector = row.pop(sector_col)
            out[str(sector)] = row

        self.sector_map = out

        log.info(f"[FUND-REGISTRY] Loaded stats for {len(out)} sectors, {len(cols)} metric columns")

    # ----------------------------------------------------------
    # Reset helper
    # ----------------------------------------------------------
    def _reset(self, reason: str):
        self.sector_map = {}
        self.global_stats = {}
        self.columns = []
        log.warning(f"[FUND-REGISTRY] Reset — {reason}")

    # ----------------------------------------------------------
    # API
    # ----------------------------------------------------------
    def sector_stats(self, sector: str) -> Optional[Dict[str, float]]:
        return self.sector_map.get(sector)

    def global_mean(self, metric: str) -> Optional[float]:
        return self.global_stats.get(f"{metric}_global_mean")

    # ... other API functions (global_std, etc.)

# Instantiate the singleton registry (common pattern in your code)
REGISTRY = FundamentalsRegistry()
