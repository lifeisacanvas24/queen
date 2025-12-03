#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_registry.py — v3.0 (COMPATIBLE WITH SCRAPER v7.0)
# ------------------------------------------------------------
# Sector-wise, global stats, z-scores, and ranking for fundamentals
#
# Features:
#   - Global and sector-wise statistics (mean, std, min, max)
#   - Z-score calculations (sector and global)
#   - Percentile rankings
#   - Metric filtering and validation
#   - Integration with fundamentals_map.py
#
# Usage:
#   from queen.helpers.fundamentals_registry import REGISTRY
#   REGISTRY.build(df, FUNDAMENTALS_METRIC_COLUMNS)
#   z_scores = REGISTRY.compute_z_scores(df)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import polars as pl

# Try to import from project
try:
    from queen.settings.fundamentals_map import (
        FUNDAMENTALS_IMPORTANCE_MAP,
        FUNDAMENTALS_METRIC_COLUMNS,
        FUNDAMENTALS_TACTICAL_FILTERS,
        POWERSCORE_DIMENSION_METRICS,
        POWERSCORE_WEIGHTS,
        SECTOR_METRIC_ADJUSTMENTS,
    )
    _HAS_MAP = True
except ImportError:
    FUNDAMENTALS_METRIC_COLUMNS = []
    FUNDAMENTALS_IMPORTANCE_MAP = {}
    FUNDAMENTALS_TACTICAL_FILTERS = {}
    POWERSCORE_WEIGHTS = {}
    POWERSCORE_DIMENSION_METRICS = {}
    SECTOR_METRIC_ADJUSTMENTS = {}
    _HAS_MAP = False

# Try to import logger
try:
    from queen.helpers.logger import log
except ImportError:
    class _FallbackLog:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARNING] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
        def debug(self, msg): print(f"[DEBUG] {msg}")
    log = _FallbackLog()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _pick_col(df: pl.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    """Pick first existing column from candidates list."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _safe_float(v: Any) -> Optional[float]:
    """Safely convert value to float."""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _get_numeric_cols(df: pl.DataFrame, candidates: Sequence[str]) -> List[str]:
    """Filter to only numeric columns that exist in DataFrame."""
    return [
        c for c in candidates
        if c in df.columns and df[c].dtype.is_numeric()
    ]


# ============================================================
# FUNDAMENTALS REGISTRY CLASS
# ============================================================

class FundamentalsRegistry:
    """Registry for fundamentals statistics and scoring.

    Stores:
        - Global metric stats (mean/std/min/max)
        - Sector-wise stats
        - Metric column list
        - Importance weights

    Provides:
        - Z-score calculations (sector and global)
        - Percentile rankings
        - PowerScore computation
        - Tactical filtering
    """

    def __init__(self):
        self.sector_map: Dict[str, Dict[str, float]] = {}
        self.global_stats: Dict[str, float] = {}
        self.columns: List[str] = []
        self.importance_map: Dict[str, float] = FUNDAMENTALS_IMPORTANCE_MAP.copy()
        self.sector_adjustments: Dict[str, Dict[str, float]] = SECTOR_METRIC_ADJUSTMENTS.copy()
        self._is_built: bool = False

    # ──────────────────────────────────────────────────────────
    # CORE BUILDER
    # ──────────────────────────────────────────────────────────
    def build(
        self,
        df: pl.DataFrame,
        metric_columns: Optional[Sequence[str]] = None
    ) -> FundamentalsRegistry:
        """Build registry from DataFrame.

        Args:
            df: Polars DataFrame with fundamentals data
            metric_columns: List of metric column names (defaults to FUNDAMENTALS_METRIC_COLUMNS)

        Returns:
            Self for chaining

        """
        if df.is_empty():
            self._reset("Empty DataFrame")
            return self

        # Use provided columns or default from map
        if metric_columns is None:
            metric_columns = FUNDAMENTALS_METRIC_COLUMNS or []

        # Filter to only existing numeric columns
        cols = _get_numeric_cols(df, metric_columns)

        # Also include any *_pct, *_cagr_* columns that exist
        for c in df.columns:
            if c not in cols and df[c].dtype.is_numeric():
                if (
                    c.endswith("_pct") or
                    "_cagr_" in c or
                    c.endswith("_latest") or
                    c in ["market_cap", "pe_ratio", "book_value", "eps_ttm",
                          "debt_to_equity", "week_52_high", "week_52_low",
                          "interest_coverage", "peers_count"]
                ):
                    cols.append(c)

        cols = list(set(cols))  # Remove duplicates

        if not cols:
            self._reset("No numeric metric columns found")
            return self

        self.columns = cols
        log.info(f"[FUND-REGISTRY] Building stats for {len(cols)} metric columns...")

        # Determine Symbol and Sector column names
        symbol_col = _pick_col(df, ["Symbol", "symbol"])
        sector_col = _pick_col(df, ["Sector", "sector"])

        # ─────────────────────────────────────────
        # 1. GLOBAL STATS
        # ─────────────────────────────────────────
        global_exprs = []
        for c in cols:
            global_exprs.extend([
                pl.col(c).mean().alias(f"{c}_global_mean"),
                pl.col(c).std().alias(f"{c}_global_std"),
                pl.col(c).min().alias(f"{c}_global_min"),
                pl.col(c).max().alias(f"{c}_global_max"),
                pl.col(c).median().alias(f"{c}_global_median"),
                pl.col(c).count().alias(f"{c}_global_count"),
            ])

        try:
            global_stats_row = df.select(global_exprs).row(0, named=True)
            self.global_stats = {k: v for k, v in global_stats_row.items() if v is not None}
        except Exception as e:
            log.error(f"[FUND-REGISTRY] Global stats failed: {e}")
            self.global_stats = {}

        # ─────────────────────────────────────────
        # 2. SECTOR STATS
        # ─────────────────────────────────────────
        if not sector_col:
            log.warning("[FUND-REGISTRY] No Sector column found, skipping sector stats")
            self.sector_map = {}
        else:
            sector_exprs = []
            for c in cols:
                sector_exprs.extend([
                    pl.col(c).mean().alias(f"{c}__mean"),
                    pl.col(c).std().alias(f"{c}__std"),
                    pl.col(c).min().alias(f"{c}__min"),
                    pl.col(c).max().alias(f"{c}__max"),
                    pl.col(c).median().alias(f"{c}__median"),
                    pl.col(c).count().alias(f"{c}__count"),
                ])

            try:
                sec_df = df.group_by(sector_col).agg(sector_exprs)

                out: Dict[str, Dict[str, float]] = {}
                for row in sec_df.iter_rows(named=True):
                    sector = str(row.pop(sector_col))
                    out[sector] = {k: v for k, v in row.items() if v is not None}

                self.sector_map = out
                log.info(f"[FUND-REGISTRY] Built stats for {len(out)} sectors")
            except Exception as e:
                log.error(f"[FUND-REGISTRY] Sector stats failed: {e}")
                self.sector_map = {}

        self._is_built = True
        log.info(
            f"[FUND-REGISTRY] Registry built: {len(self.columns)} metrics, "
            f"{len(self.sector_map)} sectors, {len(self.global_stats)} global stats"
        )

        return self

    # ──────────────────────────────────────────────────────────
    # RESET
    # ──────────────────────────────────────────────────────────
    def _reset(self, reason: str):
        """Reset registry to empty state."""
        self.sector_map = {}
        self.global_stats = {}
        self.columns = []
        self._is_built = False
        log.warning(f"[FUND-REGISTRY] Reset — {reason}")

    # ──────────────────────────────────────────────────────────
    # STAT ACCESSORS
    # ──────────────────────────────────────────────────────────
    def sector_stats(self, sector: str) -> Optional[Dict[str, float]]:
        """Get all stats for a sector."""
        return self.sector_map.get(sector)

    def sector_mean(self, sector: str, metric: str) -> Optional[float]:
        """Get sector mean for a metric."""
        stats = self.sector_map.get(sector)
        if stats:
            return stats.get(f"{metric}__mean")
        return None

    def sector_std(self, sector: str, metric: str) -> Optional[float]:
        """Get sector std for a metric."""
        stats = self.sector_map.get(sector)
        if stats:
            return stats.get(f"{metric}__std")
        return None

    def global_mean(self, metric: str) -> Optional[float]:
        """Get global mean for a metric."""
        return self.global_stats.get(f"{metric}_global_mean")

    def global_std(self, metric: str) -> Optional[float]:
        """Get global std for a metric."""
        return self.global_stats.get(f"{metric}_global_std")

    def global_min(self, metric: str) -> Optional[float]:
        """Get global min for a metric."""
        return self.global_stats.get(f"{metric}_global_min")

    def global_max(self, metric: str) -> Optional[float]:
        """Get global max for a metric."""
        return self.global_stats.get(f"{metric}_global_max")

    def get_sectors(self) -> List[str]:
        """Get list of all sectors."""
        return list(self.sector_map.keys())

    def get_metrics(self) -> List[str]:
        """Get list of all metric columns."""
        return self.columns.copy()

    # ──────────────────────────────────────────────────────────
    # Z-SCORE CALCULATIONS
    # ──────────────────────────────────────────────────────────
    def compute_z_scores(
        self,
        df: pl.DataFrame,
        metrics: Optional[List[str]] = None
    ) -> pl.DataFrame:
        """Compute z-scores for metrics (both sector and global).

        Args:
            df: DataFrame with fundamentals
            metrics: List of metrics to compute z-scores for (default: all)

        Returns:
            DataFrame with added z-score columns

        """
        if not self._is_built:
            log.warning("[FUND-REGISTRY] Registry not built, call build() first")
            return df

        metrics = metrics or self.columns
        metrics = [m for m in metrics if m in df.columns and m in self.columns]

        if not metrics:
            return df

        sector_col = _pick_col(df, ["Sector", "sector"])

        exprs = []
        for m in metrics:
            g_mean = self.global_mean(m)
            g_std = self.global_std(m)

            # Global z-score
            if g_mean is not None and g_std is not None and g_std > 0:
                exprs.append(
                    ((pl.col(m) - g_mean) / g_std).alias(f"{m}_z_global")
                )

            # Sector z-score (requires mapping)
            if sector_col:
                # Create a when-then chain for sector z-scores
                z_expr = pl.lit(None).alias(f"{m}_z_sector")

                for sector, stats in self.sector_map.items():
                    s_mean = stats.get(f"{m}__mean")
                    s_std = stats.get(f"{m}__std")

                    if s_mean is not None and s_std is not None and s_std > 0:
                        z_val = (pl.col(m) - s_mean) / s_std
                        z_expr = (
                            pl.when(pl.col(sector_col) == sector)
                            .then(z_val)
                            .otherwise(z_expr)
                        ).alias(f"{m}_z_sector")

                exprs.append(z_expr)

        if exprs:
            df = df.with_columns(exprs)

        return df

    # ──────────────────────────────────────────────────────────
    # PERCENTILE RANKINGS
    # ──────────────────────────────────────────────────────────
    def compute_percentile_ranks(
        self,
        df: pl.DataFrame,
        metrics: Optional[List[str]] = None,
        descending: Optional[Dict[str, bool]] = None
    ) -> pl.DataFrame:
        """Compute percentile ranks for metrics.

        Args:
            df: DataFrame with fundamentals
            metrics: List of metrics (default: all)
            descending: Dict mapping metric to whether higher is better
                       (default: True for most metrics)

        Returns:
            DataFrame with added rank columns

        """
        metrics = metrics or self.columns
        metrics = [m for m in metrics if m in df.columns]

        if not metrics:
            return df

        # Default: higher is better for most metrics, lower is better for some
        default_descending = {
            "pe_ratio": False,  # Lower P/E is better
            "debt_to_equity": False,  # Lower D/E is better
            "gross_npa_pct": False,  # Lower NPA is better
            "net_npa_pct": False,
            "promoter_pledge_pct": False,  # Lower pledge is better
            "ratio_debtor_days": False,  # Lower is better
            "ratio_working_capital_days": False,
        }

        descending = descending or {}

        exprs = []
        for m in metrics:
            is_desc = descending.get(m, default_descending.get(m, True))

            # Global rank
            exprs.append(
                pl.col(m).rank(descending=is_desc).alias(f"{m}_rank_global")
            )

            # Percentile (0-100)
            exprs.append(
                (pl.col(m).rank(descending=is_desc) / pl.col(m).count() * 100)
                .alias(f"{m}_pctl_global")
            )

        if exprs:
            df = df.with_columns(exprs)

        return df

    # ──────────────────────────────────────────────────────────
    # SECTOR RANKINGS
    # ──────────────────────────────────────────────────────────
    def compute_sector_ranks(
        self,
        df: pl.DataFrame,
        metrics: Optional[List[str]] = None
    ) -> pl.DataFrame:
        """Compute within-sector ranks for metrics.

        Args:
            df: DataFrame with fundamentals
            metrics: List of metrics (default: all)

        Returns:
            DataFrame with added sector rank columns

        """
        metrics = metrics or self.columns
        metrics = [m for m in metrics if m in df.columns]

        sector_col = _pick_col(df, ["Sector", "sector"])
        if not sector_col or not metrics:
            return df

        exprs = []
        for m in metrics:
            exprs.append(
                pl.col(m).rank(descending=True).over(sector_col).alias(f"{m}_rank_sector")
            )

        if exprs:
            df = df.with_columns(exprs)

        return df

    # ──────────────────────────────────────────────────────────
    # POWERSCORE CALCULATION
    # ──────────────────────────────────────────────────────────
    def compute_powerscore(
        self,
        df: pl.DataFrame,
        weights: Optional[Dict[str, float]] = None,
        dimension_metrics: Optional[Dict[str, List[str]]] = None
    ) -> pl.DataFrame:
        """Compute PowerScore based on dimension weights.

        Args:
            df: DataFrame with fundamentals
            weights: Dimension weights (default: POWERSCORE_WEIGHTS)
            dimension_metrics: Metrics per dimension (default: POWERSCORE_DIMENSION_METRICS)

        Returns:
            DataFrame with PowerScore column

        """
        weights = weights or POWERSCORE_WEIGHTS
        dimension_metrics = dimension_metrics or POWERSCORE_DIMENSION_METRICS

        if not weights or not dimension_metrics:
            log.warning("[FUND-REGISTRY] No weights/dimension_metrics for PowerScore")
            return df

        # First compute z-scores if not already present
        all_metrics = []
        for metrics in dimension_metrics.values():
            all_metrics.extend(metrics)
        all_metrics = list(set(all_metrics))

        # Check if z-scores exist
        z_cols = [f"{m}_z_global" for m in all_metrics if f"{m}_z_global" not in df.columns]
        if z_cols:
            df = self.compute_z_scores(df, all_metrics)

        # Compute dimension scores
        dimension_scores = {}
        for dim, metrics in dimension_metrics.items():
            z_cols = [f"{m}_z_global" for m in metrics if f"{m}_z_global" in df.columns]
            if z_cols:
                # Average z-score for dimension
                dimension_scores[dim] = pl.concat_list(z_cols).list.mean()

        if not dimension_scores:
            log.warning("[FUND-REGISTRY] No dimension scores computed")
            return df

        # Weighted sum of dimension scores
        total_weight = sum(weights.get(dim, 0) for dim in dimension_scores)
        if total_weight == 0:
            total_weight = 1

        powerscore_expr = pl.lit(0.0)
        for dim, score_expr in dimension_scores.items():
            weight = weights.get(dim, 0) / total_weight
            powerscore_expr = powerscore_expr + (score_expr * weight)

        # Normalize to 0-100 scale
        df = df.with_columns([
            powerscore_expr.alias("_raw_powerscore")
        ])

        # Scale to 0-100
        min_ps = df["_raw_powerscore"].min()
        max_ps = df["_raw_powerscore"].max()

        if min_ps is not None and max_ps is not None and max_ps != min_ps:
            df = df.with_columns([
                ((pl.col("_raw_powerscore") - min_ps) / (max_ps - min_ps) * 100)
                .alias("PowerScore")
            ]).drop("_raw_powerscore")
        else:
            df = df.with_columns([
                pl.lit(50.0).alias("PowerScore")
            ]).drop("_raw_powerscore")

        return df

    # ──────────────────────────────────────────────────────────
    # TACTICAL FILTERING
    # ──────────────────────────────────────────────────────────
    def apply_tactical_filters(
        self,
        df: pl.DataFrame,
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[pl.DataFrame, pl.DataFrame]:
        """Apply tactical filters and return passing/failing DataFrames.

        Args:
            df: DataFrame with fundamentals
            filters: List of filter dicts (default: FUNDAMENTALS_TACTICAL_FILTER_LIST)

        Returns:
            Tuple of (passing_df, failing_df)

        """
        if filters is None:
            filters = FUNDAMENTALS_TACTICAL_FILTERS.get("filters", [])

        if not filters:
            return df, pl.DataFrame()

        # Build filter expression
        pass_expr = pl.lit(True)

        for f in filters:
            col = f.get("col")
            op = f.get("op")
            value = f.get("value")

            if not col or col not in df.columns:
                continue

            if op == ">=":
                pass_expr = pass_expr & (pl.col(col) >= value)
            elif op == "<=":
                pass_expr = pass_expr & (pl.col(col) <= value)
            elif op == ">":
                pass_expr = pass_expr & (pl.col(col) > value)
            elif op == "<":
                pass_expr = pass_expr & (pl.col(col) < value)
            elif op == "==":
                pass_expr = pass_expr & (pl.col(col) == value)
            elif op == "!=":
                pass_expr = pass_expr & (pl.col(col) != value)

        passing = df.filter(pass_expr)
        failing = df.filter(~pass_expr)

        log.info(
            f"[FUND-REGISTRY] Tactical filter: {passing.height} passed, "
            f"{failing.height} failed out of {df.height}"
        )

        return passing, failing

    # ──────────────────────────────────────────────────────────
    # SUMMARY / DEBUG
    # ──────────────────────────────────────────────────────────
    def summary(self) -> Dict[str, Any]:
        """Get registry summary."""
        return {
            "is_built": self._is_built,
            "num_metrics": len(self.columns),
            "num_sectors": len(self.sector_map),
            "num_global_stats": len(self.global_stats),
            "sectors": list(self.sector_map.keys()),
            "metrics": self.columns[:10] + (["..."] if len(self.columns) > 10 else []),
        }

    def print_summary(self):
        """Print registry summary."""
        s = self.summary()
        print("\n" + "="*60)
        print("FUNDAMENTALS REGISTRY SUMMARY")
        print("="*60)
        print(f"  Built: {s['is_built']}")
        print(f"  Metrics: {s['num_metrics']}")
        print(f"  Sectors: {s['num_sectors']}")
        print(f"  Global Stats: {s['num_global_stats']}")
        print(f"\n  Sectors: {', '.join(s['sectors'][:5])}{'...' if len(s['sectors']) > 5 else ''}")
        print(f"  Metrics: {', '.join(s['metrics'])}")
        print("="*60)


# ============================================================
# SINGLETON INSTANCE
# ============================================================

REGISTRY = FundamentalsRegistry()


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def build_registry(df: pl.DataFrame, metric_columns: Optional[List[str]] = None) -> FundamentalsRegistry:
    """Build the global registry."""
    return REGISTRY.build(df, metric_columns)


def get_registry() -> FundamentalsRegistry:
    """Get the global registry instance."""
    return REGISTRY


# ============================================================
# EXPORTS
# ============================================================

EXPORTS = {
    "fundamentals_registry": {
        "FundamentalsRegistry": FundamentalsRegistry,
        "REGISTRY": REGISTRY,
        "build_registry": build_registry,
        "get_registry": get_registry,
    }
}


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    import sys

    # Try to load sample data
    try:
        from queen.helpers.fundamentals_polars_engine import load_all
        from queen.settings.settings import PATHS

        processed_dir = PATHS.get("FUNDAMENTALS_PROCESSED")
        if processed_dir and processed_dir.exists():
            df = load_all(processed_dir)
        else:
            print("No processed dir found")
            sys.exit(1)
    except ImportError:
        print("Could not import required modules")
        sys.exit(1)

    if df.is_empty():
        print("No data loaded")
        sys.exit(1)

    print(f"\nLoaded {df.height} symbols")

    # Build registry
    REGISTRY.build(df)
    REGISTRY.print_summary()

    # Compute z-scores
    df = REGISTRY.compute_z_scores(df)
    print(f"\nAfter z-scores: {len(df.columns)} columns")

    # Compute ranks
    df = REGISTRY.compute_percentile_ranks(df)
    df = REGISTRY.compute_sector_ranks(df)
    print(f"After ranks: {len(df.columns)} columns")

    # Apply tactical filters
    passing, failing = REGISTRY.apply_tactical_filters(df)
    print(f"\nTactical filter: {passing.height} passed, {failing.height} failed")

    # Show sample
    key_cols = ["Symbol", "Sector", "market_cap", "roce_pct", "roe_pct"]
    available = [c for c in key_cols if c in df.columns]
    print("\nSample data:")
    print(df.select(available).head(5))
