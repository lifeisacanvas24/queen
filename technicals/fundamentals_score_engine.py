#!/usr/bin/env python3
# ============================================================
# queen/technicals/fundamentals_score_engine.py — v4.0 (COMPATIBLE WITH SCRAPER v7.0)
# ------------------------------------------------------------
# Fundamental scoring engine with:
#   - Z-scores (sector + global)
#   - Intrinsic Score (weighted sigmoid)
#   - Intrinsic Bucket (A/B/C/D grading)
#   - PowerScore v2 (8-dimension composite)
#   - Pass/Fail logic with reasons
#   - Sector rankings
#
# Usage:
#   from queen.technicals.fundamentals_score_engine import score_and_filter
#   df = score_and_filter(df)
# ============================================================
from __future__ import annotations

import math
from typing import List, Optional

import polars as pl

# Try to import registry
try:
    from queen.helpers.fundamentals_registry import REGISTRY
except ImportError:
    REGISTRY = None

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

# Try to import settings
try:
    from queen.settings.fundamentals_map import (
        FUNDAMENTALS_IMPORTANCE_MAP,
        FUNDAMENTALS_METRIC_COLUMNS,
        FUNDAMENTALS_TACTICAL_FILTERS,
        INTRINSIC_BUCKETS,
        POWERSCORE_DIMENSION_METRICS,
        POWERSCORE_WEIGHTS,
    )
except ImportError:
    FUNDAMENTALS_IMPORTANCE_MAP = {}
    FUNDAMENTALS_METRIC_COLUMNS = []
    FUNDAMENTALS_TACTICAL_FILTERS = {}
    INTRINSIC_BUCKETS = [(85, "A"), (70, "B"), (50, "C"), (0, "D")]
    POWERSCORE_WEIGHTS = {
        "profitability": 0.18,
        "growth": 0.18,
        "efficiency": 0.12,
        "valuation": 0.10,
        "leverage": 0.10,
        "momentum": 0.12,
        "stability": 0.10,
        "ownership": 0.10,
    }
    POWERSCORE_DIMENSION_METRICS = {}

# If importance map is empty, create a default one
if not FUNDAMENTALS_IMPORTANCE_MAP:
    FUNDAMENTALS_IMPORTANCE_MAP = {
        "roce_pct": 1.5,
        "roe_pct": 1.5,
        "debt_to_equity": -1.0,  # Negative weight - lower is better
        "pe_ratio": -0.5,        # Negative weight - lower is better
        "market_cap": 0.5,
        "sales_cagr_5y": 1.0,
        "profit_cagr_5y": 1.0,
        "sh_promoters_pct": 0.5,
        "promoter_pledge_pct": -0.5,  # Negative weight - lower is better
        "eps_ttm": 0.5,
    }
    log.info("[FUND-SCORE] Using default FUNDAMENTALS_IMPORTANCE_MAP")


# ============================================================
# NORMALIZE TACTICAL FILTERS
# ============================================================

if isinstance(FUNDAMENTALS_TACTICAL_FILTERS, list):
    FUNDAMENTALS_TACTICAL_FILTERS = {"filters": FUNDAMENTALS_TACTICAL_FILTERS}

TACTICAL_FILTER_LIST = FUNDAMENTALS_TACTICAL_FILTERS.get("filters", [])

# Extract thresholds
MIN_SECTOR_RANK_N = int(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_SECTOR_RANK_N", 5))
MIN_GLOBAL_RANK_N = int(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_GLOBAL_RANK_N", 20))

MAX_DEBT_EQUITY = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MAX_DEBT_EQUITY", 2.0))
MAX_GROSS_NPA_PCT = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MAX_GROSS_NPA_PCT", 8.0))
MAX_NET_NPA_PCT = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MAX_NET_NPA_PCT", 4.0))
MAX_PROMOTER_PLEDGE_PCT = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MAX_PROMOTER_PLEDGE_PCT", 50.0))

MIN_ROCE_PCT = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_ROCE_PCT", 10.0))
MIN_ROE_PCT = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_ROE_PCT", 10.0))
MIN_EPS_TTM = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_EPS_TTM", 0.0))
MIN_SALES_CAGR_3Y = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_SALES_CAGR_3Y", 5.0))
MIN_PROFIT_CAGR_3Y = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_PROFIT_CAGR_3Y", 5.0))


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _safe_z(x: Optional[float], mean: Optional[float], std: Optional[float]) -> Optional[float]:
    """Calculate z-score safely."""
    if x is None or mean is None or std in (None, 0):
        return None
    return (x - mean) / std


def _sigmoid(z: float) -> float:
    """Sigmoid function for normalizing scores to 0-1."""
    try:
        return 1.0 / (1.0 + math.exp(-z))
    except OverflowError:
        return 0.0 if z < 0 else 1.0


def _bucket(score: float) -> str:
    """Map score to quality bucket (A/B/C/D)."""
    for threshold, bucket in INTRINSIC_BUCKETS:
        if score >= threshold:
            return bucket
    return "D"


def _coalesce(*vals):
    """Return first non-None value."""
    for v in vals:
        if v is not None:
            return v
    return None


def _pick_col(df: pl.DataFrame, candidates: List[str]) -> Optional[str]:
    """Pick first existing column from candidates."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _get_flat_numeric_columns(df: pl.DataFrame) -> List[str]:
    """Get list of flat numeric columns (exclude nested and Object types)."""
    flat_cols = []
    for col in df.columns:
        # Skip columns starting with underscore (nested)
        if col.startswith("_"):
            continue

        # Skip non-numeric columns
        dtype = df.schema.get(col)
        if dtype not in (pl.Float64, pl.Float32, pl.Int64, pl.Int32):
            continue

        flat_cols.append(col)

    return flat_cols


# ============================================================
# Z-SCORE CALCULATION
# ============================================================

def add_zscores(df: pl.DataFrame) -> pl.DataFrame:
    """Add z-score columns for each metric (both sector and global).

    Adds columns:
        - {metric}_z_global: Z-score vs global mean
        - {metric}_z_sector: Z-score vs sector mean

    Args:
        df: Input DataFrame with fundamental metrics

    Returns:
        DataFrame with z-score columns added

    """
    if df is None or df.is_empty():
        return df

    # Build registry if needed
    if REGISTRY is not None and not REGISTRY.columns:
        REGISTRY.build(df, FUNDAMENTALS_METRIC_COLUMNS)

    # Get metric columns
    if REGISTRY is not None:
        cols = REGISTRY.columns
    else:
        cols = [c for c in FUNDAMENTALS_METRIC_COLUMNS if c in df.columns]

    if not cols:
        log.warning("[FUND-SCORE] No metric columns found for z-score calculation")
        return df

    sector_col = _pick_col(df, ["Sector", "sector"])

    exprs: List[pl.Expr] = []

    for c in cols:
        if c not in df.columns:
            continue

        # Global z-score
        if REGISTRY is not None:
            g_mean = REGISTRY.global_mean(c)
            g_std = REGISTRY.global_std(c)
        else:
            # Calculate on the fly
            stats = df.select([
                pl.col(c).mean().alias("mean"),
                pl.col(c).std().alias("std"),
            ]).row(0, named=True)
            g_mean = stats.get("mean")
            g_std = stats.get("std")

        exprs.append(
            pl.col(c).map_elements(
                lambda x, m=g_mean, s=g_std: _safe_z(x, m, s),
                return_dtype=pl.Float64,
            ).alias(f"{c}_z_global")
        )

        # Sector z-score (requires sector column and registry)
        if sector_col and REGISTRY is not None:
            # Build when-then chain for each sector
            sector_z_expr = pl.lit(None).cast(pl.Float64).alias(f"{c}_z_sector")

            for sector in REGISTRY.get_sectors():
                sector_stats = REGISTRY.sector_stats(sector)
                if not sector_stats:
                    continue

                s_mean = sector_stats.get(f"{c}__mean")
                s_std = sector_stats.get(f"{c}__std")

                if s_mean is not None and s_std not in (None, 0):
                    z_val = (pl.col(c) - s_mean) / s_std
                    sector_z_expr = pl.when(pl.col(sector_col) == sector).then(z_val).otherwise(sector_z_expr)

            exprs.append(sector_z_expr)

    if exprs:
        df = df.with_columns(exprs)

    return df


# ============================================================
# INTRINSIC SCORE
# ============================================================

def add_intrinsic_score(df: pl.DataFrame) -> pl.DataFrame:
    """Add Intrinsic Score based on weighted z-scores.

    Adds columns:
        - Intrinsic_Score: 0-100 score based on fundamental quality
        - Intrinsic_Bucket: A/B/C/D quality grade

    Args:
        df: Input DataFrame (should have z-score columns)

    Returns:
        DataFrame with Intrinsic_Score and Intrinsic_Bucket columns

    """
    if df is None or df.is_empty():
        return df

    # Add z-scores first if not present
    z_cols = [c for c in df.columns if c.endswith("_z_sector") or c.endswith("_z_global")]
    if not z_cols:
        df = add_zscores(df)
        z_cols = [c for c in df.columns if c.endswith("_z_sector") or c.endswith("_z_global")]

    # Log available z-score columns
    log.info(f"[FUND-SCORE] Available z-score columns: {len(z_cols)}")

    # Log importance map
    log.info(f"[FUND-SCORE] Importance map has {len(FUNDAMENTALS_IMPORTANCE_MAP)} metrics")

    weight_map = FUNDAMENTALS_IMPORTANCE_MAP or {}

    # Debug: Check which metrics from importance map have z-scores
    matched_metrics = []
    for metric in weight_map.keys():
        sector_z_col = f"{metric}_z_sector"
        global_z_col = f"{metric}_z_global"
        if sector_z_col in df.columns or global_z_col in df.columns:
            matched_metrics.append(metric)

    log.info(f"[FUND-SCORE] Matched {len(matched_metrics)} metrics with z-scores: {matched_metrics[:10]}{'...' if len(matched_metrics) > 10 else ''}")

    # Create weighted sum expression for each metric
    weighted_sum_expr = pl.lit(0.0)
    total_weight_expr = pl.lit(0.0)

    for metric, weight in weight_map.items():
        # Prefer sector z-score, fallback to global
        sector_z_col = f"{metric}_z_sector"
        global_z_col = f"{metric}_z_global"

        if sector_z_col in df.columns:
            z_expr = pl.col(sector_z_col)
        elif global_z_col in df.columns:
            z_expr = pl.col(global_z_col)
        else:
            # log.debug(f"[FUND-SCORE] No z-score column for metric: {metric}")
            continue

        weighted_sum_expr = weighted_sum_expr + (z_expr * weight)
        total_weight_expr = total_weight_expr + pl.when(z_expr.is_not_null()).then(weight).otherwise(0)

    # Calculate intrinsic score: sigmoid(weighted_sum / total_weight) * 100
    intrinsic_score_expr = pl.when(total_weight_expr > 0).then(
        (1.0 / (1.0 + pl.lit(math.e) ** (-weighted_sum_expr / total_weight_expr))) * 100.0
    ).otherwise(None).alias("Intrinsic_Score")

    df = df.with_columns(intrinsic_score_expr)

    # Add bucket
    bucket_expr = pl.lit("D").cast(pl.Utf8)  # Default to "D"
    # Apply buckets in reverse order (highest threshold first)
    for threshold, bucket_label in sorted(INTRINSIC_BUCKETS, key=lambda x: x[0], reverse=True):
        bucket_expr = pl.when(pl.col("Intrinsic_Score") >= threshold).then(pl.lit(bucket_label)).otherwise(bucket_expr)

    df = df.with_columns(bucket_expr.alias("Intrinsic_Bucket"))

    # Log some stats
    if "Intrinsic_Score" in df.columns:
        # Count non-null values
        non_null_count = df.filter(pl.col("Intrinsic_Score").is_not_null()).height
        log.info(f"[FUND-SCORE] Intrinsic Score: {non_null_count}/{df.height} non-null values")

        if non_null_count > 0:
            stats = df.filter(pl.col("Intrinsic_Score").is_not_null()).select([
                pl.col("Intrinsic_Score").mean().alias("mean"),
                pl.col("Intrinsic_Score").std().alias("std"),
                pl.col("Intrinsic_Score").min().alias("min"),
                pl.col("Intrinsic_Score").max().alias("max"),
            ]).row(0, named=True)

            # Safely format stats, handling None values
            mean_str = f"{stats['mean']:.2f}" if stats['mean'] is not None else "N/A"
            std_str = f"{stats['std']:.2f}" if stats['std'] is not None else "N/A"
            min_str = f"{stats['min']:.2f}" if stats['min'] is not None else "N/A"
            max_str = f"{stats['max']:.2f}" if stats['max'] is not None else "N/A"

            log.info(f"[FUND-SCORE] Intrinsic Score stats: mean={mean_str}, std={std_str}, range={min_str}-{max_str}")
        else:
            log.warning("[FUND-SCORE] All Intrinsic Scores are null!")

    return df


# ============================================================
# POWERSCORE v2 (SIMPLIFIED - NO TIMESERIES DEPENDENCIES)
# ============================================================

def add_powerscore(df: pl.DataFrame) -> pl.DataFrame:
    """Add PowerScore based on 8 dimensions (simplified version).

    Dimensions:
        - Profitability: ROCE, ROE
        - Growth: Sales CAGR, Profit CAGR
        - Efficiency: Working capital, debtor days
        - Valuation: P/E ratio
        - Leverage: Debt/Equity, Interest coverage
        - Momentum: Price momentum (simplified)
        - Stability: Earnings stability (simplified)
        - Ownership: Promoter holding, FII, Pledge

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with PowerScore column

    """
    if df is None or df.is_empty():
        return df

    # Profitability dimension: ROCE + ROE
    roce_col = _pick_col(df, ["roce_pct", "roce"])
    roe_col = _pick_col(df, ["roe_pct", "roe"])

    if roce_col and roe_col:
        # Normalize to 0-1 (assuming 0-50% range is typical)
        roce_norm = pl.when(pl.col(roce_col) < 0).then(0).when(pl.col(roce_col) > 50).then(1).otherwise(pl.col(roce_col) / 50.0)
        roe_norm = pl.when(pl.col(roe_col) < 0).then(0).when(pl.col(roe_col) > 50).then(1).otherwise(pl.col(roe_col) / 50.0)
        profitability_score = (roce_norm * 0.6 + roe_norm * 0.4)
    else:
        profitability_score = pl.lit(0.5)

    # Growth dimension: Sales + Profit CAGR
    sales_cagr_col = _pick_col(df, ["sales_cagr_10y", "sales_cagr_5y", "sales_cagr_3y"])
    profit_cagr_col = _pick_col(df, ["profit_cagr_10y", "profit_cagr_5y", "profit_cagr_3y"])

    if sales_cagr_col and profit_cagr_col:
        # Normalize to 0-1 (assuming -20% to +30% range)
        sales_norm = pl.when(pl.col(sales_cagr_col) < -20).then(0).when(pl.col(sales_cagr_col) > 30).then(1).otherwise((pl.col(sales_cagr_col) + 20) / 50.0)
        profit_norm = pl.when(pl.col(profit_cagr_col) < -20).then(0).when(pl.col(profit_cagr_col) > 30).then(1).otherwise((pl.col(profit_cagr_col) + 20) / 50.0)
        growth_score = (sales_norm * 0.4 + profit_norm * 0.6)
    else:
        growth_score = pl.lit(0.5)

    # Efficiency dimension: Working capital, debtor days
    wc_days_col = _pick_col(df, ["ratio_working_capital_days"])
    debtor_days_col = _pick_col(df, ["ratio_debtor_days"])

    efficiency_score = pl.lit(0.5)
    if wc_days_col and debtor_days_col:
        wc_score = pl.when(pl.col(wc_days_col) <= 0).then(0.5).otherwise(pl.min_horizontal(1.0, 90 / pl.col(wc_days_col)))
        debtor_score = pl.when(pl.col(debtor_days_col) <= 0).then(0.5).otherwise(pl.min_horizontal(1.0, 60 / pl.col(debtor_days_col)))
        efficiency_score = (wc_score * 0.5 + debtor_score * 0.5)

    # Valuation dimension: P/E ratio
    pe_col = _pick_col(df, ["pe_ratio"])

    valuation_score = pl.lit(0.5)
    if pe_col:
        # Lower P/E is better (for value), normalize inversely
        # Assuming 5-50 range
        valuation_score = pl.when(pl.col(pe_col) <= 5).then(1.0).when(pl.col(pe_col) >= 50).then(0.0).otherwise(1.0 - (pl.col(pe_col) - 5) / 45.0)

    # Leverage dimension: Debt/Equity and Interest coverage
    de_col = _pick_col(df, ["debt_to_equity"])
    ic_col = _pick_col(df, ["interest_coverage"])

    leverage_score = pl.lit(0.5)
    if de_col and ic_col:
        # Lower D/E is better
        de_score = pl.when(pl.col(de_col) <= 0).then(1.0).when(pl.col(de_col) >= 2).then(0.0).otherwise(1.0 - (pl.col(de_col) / 2.0))
        # Higher interest coverage is better
        ic_score = pl.when(pl.col(ic_col) <= 1).then(0.0).when(pl.col(ic_col) >= 10).then(1.0).otherwise(pl.col(ic_col) / 10.0)
        leverage_score = (de_score * 0.6 + ic_score * 0.4)

    # Momentum dimension: Simplified - use price CAGR
    price_cagr_col = _pick_col(df, ["price_cagr_1y", "price_cagr_3y", "price_cagr_5y"])

    momentum_score = pl.lit(0.5)
    if price_cagr_col:
        # Normalize price CAGR (-50% to +50% range)
        momentum_score = pl.when(pl.col(price_cagr_col) < -50).then(0.0).when(pl.col(price_cagr_col) > 50).then(1.0).otherwise((pl.col(price_cagr_col) + 50) / 100.0)

    # Stability dimension: Simplified - use dividend yield as proxy
    div_yield_col = _pick_col(df, ["dividend_yield"])

    stability_score = pl.lit(0.5)
    if div_yield_col:
        # Higher dividend yield = more stable (to some extent)
        stability_score = pl.when(pl.col(div_yield_col) <= 0).then(0.3).when(pl.col(div_yield_col) >= 5).then(1.0).otherwise(pl.col(div_yield_col) / 5.0)

    # Ownership dimension: Promoter holding, FII, Pledge
    promoter_col = _pick_col(df, ["sh_promoters_pct", "promoters_holding_latest"])
    pledge_col = _pick_col(df, ["promoter_pledge_pct", "pledge_pct"])
    fii_col = _pick_col(df, ["sh_fii_pct", "fii_holding_latest"])

    ownership_score = pl.lit(0.5)
    if promoter_col and pledge_col and fii_col:
        # Higher promoter holding is generally positive (but not too high)
        promoter_score = pl.when(pl.col(promoter_col) >= 75).then(0.9) \
            .when(pl.col(promoter_col) >= 50).then(1.0) \
            .when(pl.col(promoter_col) >= 30).then(0.7) \
            .otherwise(0.5)

        # Lower pledge is better
        pledge_score = pl.max_horizontal(0, 1.0 - (pl.col(pledge_col) / 100.0))

        # Some FII holding is positive
        fii_score = pl.when(pl.col(fii_col) <= 0).then(0.3).otherwise(pl.min_horizontal(1.0, pl.col(fii_col) / 30.0))

        ownership_score = (promoter_score * 0.4 + pledge_score * 0.4 + fii_score * 0.2)

    # Weighted sum of all dimensions
    dimension_scores = {
        "profitability": profitability_score,
        "growth": growth_score,
        "efficiency": efficiency_score,
        "valuation": valuation_score,
        "leverage": leverage_score,
        "momentum": momentum_score,
        "stability": stability_score,
        "ownership": ownership_score,
    }

    # Calculate weighted sum
    weighted_sum = pl.lit(0.0)
    total_weight = pl.lit(0.0)

    for dim_name, score_expr in dimension_scores.items():
        weight = float(POWERSCORE_WEIGHTS.get(dim_name, 0.1))
        weighted_sum = weighted_sum + (score_expr * weight)
        total_weight = total_weight + weight

    # Scale to 0-100
    powerscore_expr = (weighted_sum / total_weight) * 100.0

    df = df.with_columns(powerscore_expr.alias("PowerScore"))

    # Log some stats
    if "PowerScore" in df.columns:
        # Count non-null values
        non_null_count = df.filter(pl.col("PowerScore").is_not_null()).height
        log.info(f"[FUND-SCORE] PowerScore: {non_null_count}/{df.height} non-null values")

        if non_null_count > 0:
            stats = df.filter(pl.col("PowerScore").is_not_null()).select([
                pl.col("PowerScore").mean().alias("mean"),
                pl.col("PowerScore").std().alias("std"),
                pl.col("PowerScore").min().alias("min"),
                pl.col("PowerScore").max().alias("max"),
            ]).row(0, named=True)

            # Safely format stats, handling None values
            mean_str = f"{stats['mean']:.2f}" if stats['mean'] is not None else "N/A"
            std_str = f"{stats['std']:.2f}" if stats['std'] is not None else "N/A"
            min_str = f"{stats['min']:.2f}" if stats['min'] is not None else "N/A"
            max_str = f"{stats['max']:.2f}" if stats['max'] is not None else "N/A"

            log.info(f"[FUND-SCORE] PowerScore stats: mean={mean_str}, std={std_str}, range={min_str}-{max_str}")
        else:
            log.warning("[FUND-SCORE] All PowerScores are null!")

    return df


# ============================================================
# PASS/FAIL LOGIC
# ============================================================

def add_pass_fail(df: pl.DataFrame) -> pl.DataFrame:
    """Add fundamental pass/fail based on tactical filters.

    Adds columns:
        - Fundamental_Pass: Boolean pass/fail
        - Fundamental_Fail_Reasons: Comma-separated list of failure reasons

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with pass/fail columns

    """
    if df is None or df.is_empty():
        return df

    # Start with all passing
    pass_expr = pl.lit(True)
    reasons_expr = pl.lit("")

    # Get columns for checks
    roce_col = _pick_col(df, ["roce_pct", "roce"])
    roe_col = _pick_col(df, ["roe_pct", "roe"])
    de_col = _pick_col(df, ["debt_to_equity"])
    eps_col = _pick_col(df, ["eps_ttm"])
    gnpa_col = _pick_col(df, ["gross_npa_pct"])
    nnpa_col = _pick_col(df, ["net_npa_pct"])
    pledge_col = _pick_col(df, ["promoter_pledge_pct"])
    sales_cagr_col = _pick_col(df, ["sales_cagr_3y"])
    profit_cagr_col = _pick_col(df, ["profit_cagr_3y"])

    # Helper function to format value in Polars expression
    def _format_reason(value_expr, prefix):
        # Format with 1 decimal place for percentages, 2 for others
        if "ROCE" in prefix or "ROE" in prefix or "NPA" in prefix or "Pledge" in prefix or "Sales" in prefix or "Profits" in prefix:
            formatted = value_expr.cast(pl.Utf8).str.replace(r"(\.\d*?)0+$", r"\1").str.replace(r"\.$", "")
            return pl.concat_str([pl.lit(f"{prefix} ("), formatted, pl.lit("%)")])
        if "D/E" in prefix:
            formatted = value_expr.cast(pl.Utf8).str.replace(r"(\.\d*?)0+$", r"\1").str.replace(r"\.$", "")
            return pl.concat_str([pl.lit(f"{prefix} ("), formatted, pl.lit(")")])
        return pl.lit(prefix)

    # Apply filters
    if roce_col:
        pass_expr = pass_expr & (pl.col(roce_col) >= MIN_ROCE_PCT)
        reasons_expr = pl.when(pl.col(roce_col) < MIN_ROCE_PCT).then(
            pl.concat_str([reasons_expr, _format_reason(pl.col(roce_col), "Low ROCE")], separator=", ")
        ).otherwise(reasons_expr)

    if roe_col:
        pass_expr = pass_expr & (pl.col(roe_col) >= MIN_ROE_PCT)
        reasons_expr = pl.when(pl.col(roe_col) < MIN_ROE_PCT).then(
            pl.concat_str([reasons_expr, _format_reason(pl.col(roe_col), "Low ROE")], separator=", ")
        ).otherwise(reasons_expr)

    if de_col:
        pass_expr = pass_expr & (pl.col(de_col) <= MAX_DEBT_EQUITY)
        reasons_expr = pl.when(pl.col(de_col) > MAX_DEBT_EQUITY).then(
            pl.concat_str([reasons_expr, _format_reason(pl.col(de_col), "High D/E")], separator=", ")
        ).otherwise(reasons_expr)

    if eps_col:
        pass_expr = pass_expr & (pl.col(eps_col) > MIN_EPS_TTM)
        reasons_expr = pl.when(pl.col(eps_col) <= MIN_EPS_TTM).then(
            pl.concat_str([reasons_expr, pl.lit("Negative EPS")], separator=", ")
        ).otherwise(reasons_expr)

    if gnpa_col:
        pass_expr = pass_expr & (pl.col(gnpa_col) <= MAX_GROSS_NPA_PCT)
        reasons_expr = pl.when(pl.col(gnpa_col) > MAX_GROSS_NPA_PCT).then(
            pl.concat_str([reasons_expr, _format_reason(pl.col(gnpa_col), "High Gross NPA")], separator=", ")
        ).otherwise(reasons_expr)

    if nnpa_col:
        pass_expr = pass_expr & (pl.col(nnpa_col) <= MAX_NET_NPA_PCT)
        reasons_expr = pl.when(pl.col(nnpa_col) > MAX_NET_NPA_PCT).then(
            pl.concat_str([reasons_expr, _format_reason(pl.col(nnpa_col), "High Net NPA")], separator=", ")
        ).otherwise(reasons_expr)

    if pledge_col:
        pass_expr = pass_expr & (pl.col(pledge_col) <= MAX_PROMOTER_PLEDGE_PCT)
        reasons_expr = pl.when(pl.col(pledge_col) > MAX_PROMOTER_PLEDGE_PCT).then(
            pl.concat_str([reasons_expr, _format_reason(pl.col(pledge_col), "High Pledge")], separator=", ")
        ).otherwise(reasons_expr)

    # Growth checks (optional - only fail if significantly negative)
    if sales_cagr_col:
        pass_expr = pass_expr & (pl.col(sales_cagr_col) >= -10)
        reasons_expr = pl.when(pl.col(sales_cagr_col) < -10).then(
            pl.concat_str([reasons_expr, _format_reason(pl.col(sales_cagr_col), "Declining Sales")], separator=", ")
        ).otherwise(reasons_expr)

    if profit_cagr_col:
        pass_expr = pass_expr & (pl.col(profit_cagr_col) >= -20)
        reasons_expr = pl.when(pl.col(profit_cagr_col) < -20).then(
            pl.concat_str([reasons_expr, _format_reason(pl.col(profit_cagr_col), "Declining Profits")], separator=", ")
        ).otherwise(reasons_expr)

    # Trim leading comma and space from reasons
    reasons_expr = pl.when(reasons_expr.str.starts_with(", ")).then(
        reasons_expr.str.slice(2)
    ).otherwise(reasons_expr)

    df = df.with_columns([
        pass_expr.alias("Fundamental_Pass"),
        reasons_expr.alias("Fundamental_Fail_Reasons")
    ])

    passed = df.filter(pl.col("Fundamental_Pass")).height
    log.info(f"[FUND-SCORE] Pass/Fail: {passed}/{df.height} passed")

    return df


# ============================================================
# RANKINGS
# ============================================================

def add_rankings(df: pl.DataFrame) -> pl.DataFrame:
    """Add sector and global rankings.

    Adds columns:
        - Sector_Rank: Rank within sector (by PowerScore)
        - Global_Rank: Rank across all symbols
        - PowerScore_Rank: Alias for Global_Rank

    Args:
        df: Input DataFrame with PowerScore

    Returns:
        DataFrame with ranking columns

    """
    if df is None or df.is_empty():
        return df

    ps_col = _pick_col(df, ["PowerScore", "Intrinsic_Score"])
    if not ps_col:
        log.warning("[FUND-SCORE] No score column for ranking")
        return df

    sector_col = _pick_col(df, ["Sector", "sector"])

    # Global rank
    df = df.with_columns(
        pl.col(ps_col).rank(descending=True).alias("Global_Rank")
    )
    df = df.with_columns(
        pl.col("Global_Rank").alias("PowerScore_Rank")
    )

    # Sector rank
    if sector_col:
        df = df.with_columns(
            pl.col(ps_col).rank(descending=True).over(sector_col).alias("Sector_Rank")
        )

    return df


# ============================================================
# MAIN PIPELINE
# ============================================================

def score_and_filter(df: pl.DataFrame) -> pl.DataFrame:
    """Full scoring pipeline.

    1. Add z-scores (sector + global)
    2. Add Intrinsic Score and Bucket
    3. Add PowerScore
    4. Add Pass/Fail logic
    5. Add Rankings

    Args:
        df: Input DataFrame from fundamentals_polars_engine.load_all()

    Returns:
        Fully scored DataFrame

    """
    if df is None or df.is_empty():
        return df

    log.info(f"[FUND-SCORE] Starting scoring pipeline for {df.height} symbols")

    # Build registry first
    if REGISTRY is not None:
        REGISTRY.build(df, FUNDAMENTALS_METRIC_COLUMNS)

    # Step 1: Z-scores
    work = add_zscores(df)

    # Step 2: Intrinsic Score
    work = add_intrinsic_score(work)

    # Step 3: PowerScore
    work = add_powerscore(work)

    # Step 4: Pass/Fail
    work = add_pass_fail(work)

    # Step 5: Rankings
    work = add_rankings(work)

    log.info(f"[FUND-SCORE] Scoring complete: {work.height} symbols scored")

    return work


# ============================================================
# EXPORTS
# ============================================================

EXPORTS = {
    "fundamentals_score_engine": {
        "score_and_filter": score_and_filter,
        "add_zscores": add_zscores,
        "add_intrinsic_score": add_intrinsic_score,
        "add_powerscore": add_powerscore,
        "add_pass_fail": add_pass_fail,
        "add_rankings": add_rankings,
    }
}


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    import sys

    print("\n" + "="*60)
    print("FUNDAMENTALS SCORE ENGINE TEST")
    print("="*60)

    try:
        from queen.helpers.fundamentals_polars_engine import load_all
        from queen.settings.settings import PATHS

        processed_dir = PATHS.get("FUNDAMENTALS_PROCESSED")
        if processed_dir and processed_dir.exists():
            df = load_all(processed_dir)
        else:
            print("No processed dir found")
            sys.exit(1)
    except ImportError as e:
        print(f"Could not import required modules: {e}")
        sys.exit(1)

    if df.is_empty():
        print("No data loaded")
        sys.exit(1)

    print(f"\nLoaded {df.height} symbols")
    print(f"Columns before: {len(df.columns)}")

    # Run scoring pipeline
    df = score_and_filter(df)

    print(f"Columns after: {len(df.columns)}")

    # Show results
    display_cols = [
        "Symbol", "Sector", "PowerScore", "Intrinsic_Bucket",
        "Fundamental_Pass", "Global_Rank"
    ]
    available = [c for c in display_cols if c in df.columns]

    print("\nScoring Results:")
    print(df.select(available).sort("PowerScore", descending=True).head(15))

    # Show pass/fail stats
    if "Fundamental_Pass" in df.columns:
        passed = df.filter(pl.col("Fundamental_Pass")).height
        failed = df.height - passed
        print(f"\nPass/Fail: {passed} passed, {failed} failed")

    # Show bucket distribution
    if "Intrinsic_Bucket" in df.columns:
        print("\nBucket Distribution:")
        print(df.group_by("Intrinsic_Bucket").agg(pl.len().alias("count")).sort("Intrinsic_Bucket"))

    # Show failed symbols with reasons
    if "Fundamental_Fail_Reasons" in df.columns:
        failed_df = df.filter(~pl.col("Fundamental_Pass")).select([
            "Symbol", "Fundamental_Fail_Reasons"
        ]).head(10)

        if failed_df.height > 0:
            print("\nFailed Symbols (sample):")
            print(failed_df)

    print("\n" + "="*60)
