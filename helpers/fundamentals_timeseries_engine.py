#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_timeseries_engine.py — v2.0 (COMPATIBLE WITH SCRAPER v7.0)
# ------------------------------------------------------------
# Adds trend features over time-series fundamentals:
#   • slopes (ROCE/ROE/Sales/Profit/EPS/NPA)
#   • QoQ acceleration
#   • earnings stability (CV)
#   • momentum labels
#   • composite scores
#
# Zero pandas. Zero numpy. 100% Polars-safe.
#
# Input DF = output of fundamentals_polars_engine.load_all()
# Deep tables live under: _quarters / _profit_loss / _balance_sheet / _ratios
#
# Usage:
#   from queen.helpers.fundamentals_timeseries_engine import add_timeseries_features
#   df = add_timeseries_features(df)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import polars as pl

# Try to import logger, fallback to print
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
# PYTHON HELPERS (safe, no pandas/numpy)
# ============================================================

def _is_series_dict(x: Any) -> bool:
    """Check if x is a non-empty dict (time-series data)."""
    return isinstance(x, dict) and len(x) > 0


def _series_values(series_dict: Dict[str, Any]) -> List[float]:
    """Extract numeric values from a time-series dict.
    Screener.in preserves chronological order in the dict.
    """
    out: List[float] = []
    for _, v in series_dict.items():
        if v is None:
            continue
        try:
            if isinstance(v, str):
                # Handle string values with commas
                v = v.replace(",", "").replace("%", "").strip()
                if v in ("", "-", "NA", "N/A"):
                    continue
            out.append(float(v))
        except (ValueError, TypeError):
            continue
    return out


def _first_last_slope(vals: List[float]) -> Optional[float]:
    """Calculate simple slope: (last - first) / (n - 1)
    Returns change per period.
    """
    if not vals or len(vals) < 2:
        return None
    n = len(vals)
    return (vals[-1] - vals[0]) / max(1, n - 1)


def _linear_regression_slope(vals: List[float]) -> Optional[float]:
    """Calculate slope using simple linear regression.
    More robust than first-last for noisy data.
    """
    if not vals or len(vals) < 3:
        return _first_last_slope(vals)

    n = len(vals)
    x_mean = (n - 1) / 2.0
    y_mean = sum(vals) / n

    numerator = 0.0
    denominator = 0.0

    for i, y in enumerate(vals):
        x_diff = i - x_mean
        numerator += x_diff * (y - y_mean)
        denominator += x_diff * x_diff

    if denominator == 0:
        return None

    return numerator / denominator


def _qoq_accel(vals: List[float]) -> Optional[float]:
    """Calculate QoQ acceleration (second derivative).
    Positive = accelerating growth, Negative = decelerating.
    """
    if not vals or len(vals) < 3:
        return None
    # (latest change) - (previous change)
    return (vals[-1] - vals[-2]) - (vals[-2] - vals[-3])


def _cv(vals: List[float]) -> Optional[float]:
    """Calculate Coefficient of Variation (std / mean).
    Lower CV = more stable earnings.
    """
    if not vals or len(vals) < 2:
        return None

    n = len(vals)
    mean = sum(vals) / n

    if mean == 0:
        return None

    variance = sum((x - mean) ** 2 for x in vals) / (n - 1)
    std = variance ** 0.5

    return std / abs(mean)


def _growth_rate(vals: List[float]) -> Optional[float]:
    """Calculate CAGR-like growth rate.
    """
    if not vals or len(vals) < 2:
        return None

    first = vals[0]
    last = vals[-1]

    if first == 0 or first is None:
        return None

    n = len(vals) - 1
    if n <= 0:
        return None

    # Simple CAGR: (last/first)^(1/n) - 1
    try:
        if last / first < 0:
            return None  # Can't take root of negative
        return ((last / first) ** (1.0 / n) - 1) * 100
    except (ValueError, ZeroDivisionError):
        return None


def _pick_series_from_table(
    table: Any,
    candidates: Sequence[str]
) -> Optional[List[float]]:
    """Return list of floats for first available metric key in table.

    Args:
        table: Dict of {metric_name: {period: value}}
        candidates: List of metric names to try

    Returns:
        List of float values, or None if not found

    """
    if not isinstance(table, dict):
        return None

    for k in candidates:
        sdict = table.get(k)
        if _is_series_dict(sdict):
            vals = _series_values(sdict)
            if vals:
                return vals

    # Also try with common suffixes/variations
    for k in candidates:
        for suffix in ["", "+", " "]:
            for prefix in ["", " "]:
                key = f"{prefix}{k}{suffix}".strip()
                sdict = table.get(key)
                if _is_series_dict(sdict):
                    vals = _series_values(sdict)
                    if vals:
                        return vals

    return None


def _trend_label(slope: Optional[float], accel: Optional[float]) -> Optional[str]:
    """Generate human-readable trend label from slope and acceleration.
    """
    if slope is None:
        return None

    if slope > 0.5:
        if accel is None or accel >= 0:
            return "RISING"
        return "RISING_BUT_SLOWING"

    if slope < -0.5:
        if accel is None or accel <= 0:
            return "FALLING"
        return "FALLING_BUT_RECOVERING"

    return "FLAT"


def _momentum_score(slope: Optional[float], cv: Optional[float]) -> Optional[float]:
    """Calculate momentum score combining slope and stability.
    Higher slope + lower CV = better momentum.
    """
    if slope is None:
        return None

    # Normalize slope to 0-1 range (assuming typical slopes are -10 to +10)
    slope_norm = max(0, min(1, (slope + 10) / 20))

    # Stability factor (lower CV is better)
    if cv is not None and cv > 0:
        stability = 1 / (1 + cv)
    else:
        stability = 0.5

    return (slope_norm * 0.7 + stability * 0.3) * 100


# ============================================================
# POLARS EXPRESSION BUILDERS
# ============================================================

def _slope_expr(
    table_col: str,
    candidates: Sequence[str],
    *,
    out_name: str,
    use_regression: bool = False
) -> pl.Expr:
    """Create Polars expression to calculate slope from nested table."""
    slope_fn = _linear_regression_slope if use_regression else _first_last_slope

    return (
        pl.col(table_col)
        .map_elements(
            lambda t: slope_fn(_pick_series_from_table(t, candidates) or []),
            return_dtype=pl.Float64,
        )
        .alias(out_name)
    )


def _accel_expr(
    table_col: str,
    candidates: Sequence[str],
    *,
    out_name: str
) -> pl.Expr:
    """Create Polars expression to calculate acceleration from nested table."""
    return (
        pl.col(table_col)
        .map_elements(
            lambda t: _qoq_accel(_pick_series_from_table(t, candidates) or []),
            return_dtype=pl.Float64,
        )
        .alias(out_name)
    )


def _cv_expr(
    table_col: str,
    candidates: Sequence[str],
    *,
    out_name: str
) -> pl.Expr:
    """Create Polars expression to calculate CV from nested table."""
    return (
        pl.col(table_col)
        .map_elements(
            lambda t: _cv(_pick_series_from_table(t, candidates) or []),
            return_dtype=pl.Float64,
        )
        .alias(out_name)
    )


def _growth_expr(
    table_col: str,
    candidates: Sequence[str],
    *,
    out_name: str
) -> pl.Expr:
    """Create Polars expression to calculate growth rate from nested table."""
    return (
        pl.col(table_col)
        .map_elements(
            lambda t: _growth_rate(_pick_series_from_table(t, candidates) or []),
            return_dtype=pl.Float64,
        )
        .alias(out_name)
    )


def _label_expr(
    slope_col: str,
    accel_col: str,
    *,
    out_name: str
) -> pl.Expr:
    """Create Polars expression to generate trend label."""
    return (
        pl.struct([slope_col, accel_col])
        .map_elements(
            lambda s: _trend_label(s.get(slope_col), s.get(accel_col)),
            return_dtype=pl.Utf8,
        )
        .alias(out_name)
    )


def _momentum_expr(
    slope_col: str,
    cv_col: str,
    *,
    out_name: str
) -> pl.Expr:
    """Create Polars expression to calculate momentum score."""
    return (
        pl.struct([slope_col, cv_col])
        .map_elements(
            lambda s: _momentum_score(s.get(slope_col), s.get(cv_col)),
            return_dtype=pl.Float64,
        )
        .alias(out_name)
    )


# ============================================================
# METRIC CANDIDATE DEFINITIONS
# ============================================================

# Quarterly metrics (from _quarters table)
Q_SALES_CANDIDATES = ["Sales", "Sales+", "Revenue", "Total Revenue", "q_sales"]
Q_PROFIT_CANDIDATES = ["Net Profit", "Net Profit+", "PAT", "q_np", "q_net_profit"]
Q_EPS_CANDIDATES = ["EPS in Rs", "EPS", "q_eps"]
Q_OPM_CANDIDATES = ["OPM %", "OPM", "Operating Margin", "q_opm_pct"]

# Annual metrics (from _profit_loss table)
PL_SALES_CANDIDATES = ["Sales", "Sales+", "Revenue", "pl_sales"]
PL_PROFIT_CANDIDATES = ["Net Profit", "Net Profit+", "PAT", "pl_np", "pl_net_profit"]
PL_EPS_CANDIDATES = ["EPS in Rs", "EPS", "pl_eps"]
PL_OPM_CANDIDATES = ["OPM %", "OPM", "pl_opm_pct"]

# Ratio metrics (from _ratios table)
ROCE_CANDIDATES = ["ROCE %", "ROCE", "roce_pct", "ratio_roce_pct"]
ROE_CANDIDATES = ["ROE %", "ROE", "roe_pct", "ratio_roe_pct"]
GROSS_NPA_CANDIDATES = ["Gross NPA %", "Gross NPA", "gross_npa_pct"]
NET_NPA_CANDIDATES = ["Net NPA %", "Net NPA", "net_npa_pct"]
DEBTOR_DAYS_CANDIDATES = ["Debtor Days", "Debtors Days", "ratio_debtor_days"]
WORKING_CAPITAL_CANDIDATES = ["Working Capital Days", "ratio_working_capital_days"]

# Balance sheet metrics (from _balance_sheet table)
BS_BORROWINGS_CANDIDATES = ["Borrowings", "Borrowings+", "bs_borrowings"]
BS_RESERVES_CANDIDATES = ["Reserves", "bs_reserves"]
BS_DEPOSITS_CANDIDATES = ["Deposits", "bs_deposits"]
BS_ASSETS_CANDIDATES = ["Total Assets", "bs_assets", "bs_total_assets"]


# ============================================================
# MAIN ENGINE
# ============================================================

def add_timeseries_features(df: pl.DataFrame) -> pl.DataFrame:
    """Add time-series trend features to the fundamentals DataFrame.

    Adds columns:
        - Sales_Q_Slope, Sales_Q_Accel, Sales_Q_CV
        - Profit_Q_Slope, Profit_Q_Accel, Profit_Q_CV
        - EPS_Q_Slope, EPS_Q_Accel
        - Sales_Y_Slope, Profit_Y_Slope, EPS_Y_Slope
        - ROCE_Slope, ROE_Slope
        - GrossNPA_Slope, NetNPA_Slope
        - Borrowings_Slope, Deposits_Slope
        - Fundamental_Momentum, Earnings_Momentum
        - Bank_Asset_Quality_Trend

    Args:
        df: DataFrame from fundamentals_polars_engine.load_all()

    Returns:
        DataFrame with additional trend columns

    """
    if df is None or df.is_empty():
        return df

    exprs: List[pl.Expr] = []

    # ─────────────────────────────────────────────────────────
    # QUARTERLY TRENDS
    # ─────────────────────────────────────────────────────────
    if "_quarters" in df.columns:
        exprs.extend([
            # Sales trends
            _slope_expr("_quarters", Q_SALES_CANDIDATES, out_name="Sales_Q_Slope"),
            _accel_expr("_quarters", Q_SALES_CANDIDATES, out_name="Sales_Q_Accel"),
            _cv_expr("_quarters", Q_SALES_CANDIDATES, out_name="Sales_Q_CV"),
            _growth_expr("_quarters", Q_SALES_CANDIDATES, out_name="Sales_Q_Growth"),

            # Profit trends
            _slope_expr("_quarters", Q_PROFIT_CANDIDATES, out_name="Profit_Q_Slope"),
            _accel_expr("_quarters", Q_PROFIT_CANDIDATES, out_name="Profit_Q_Accel"),
            _cv_expr("_quarters", Q_PROFIT_CANDIDATES, out_name="Profit_Q_CV"),

            # EPS trends
            _slope_expr("_quarters", Q_EPS_CANDIDATES, out_name="EPS_Q_Slope"),
            _accel_expr("_quarters", Q_EPS_CANDIDATES, out_name="EPS_Q_Accel"),
            _cv_expr("_quarters", Q_EPS_CANDIDATES, out_name="EPS_Q_CV"),

            # OPM trends
            _slope_expr("_quarters", Q_OPM_CANDIDATES, out_name="OPM_Q_Slope"),
        ])

    # ─────────────────────────────────────────────────────────
    # ANNUAL TRENDS (from P&L)
    # ─────────────────────────────────────────────────────────
    if "_profit_loss" in df.columns:
        exprs.extend([
            _slope_expr("_profit_loss", PL_SALES_CANDIDATES, out_name="Sales_Y_Slope", use_regression=True),
            _slope_expr("_profit_loss", PL_PROFIT_CANDIDATES, out_name="Profit_Y_Slope", use_regression=True),
            _slope_expr("_profit_loss", PL_EPS_CANDIDATES, out_name="EPS_Y_Slope", use_regression=True),
            _growth_expr("_profit_loss", PL_SALES_CANDIDATES, out_name="Sales_Y_CAGR"),
            _growth_expr("_profit_loss", PL_PROFIT_CANDIDATES, out_name="Profit_Y_CAGR"),
        ])

    # ─────────────────────────────────────────────────────────
    # RATIO TRENDS
    # ─────────────────────────────────────────────────────────
    if "_ratios" in df.columns:
        exprs.extend([
            _slope_expr("_ratios", ROCE_CANDIDATES, out_name="ROCE_Slope"),
            _slope_expr("_ratios", ROE_CANDIDATES, out_name="ROE_Slope"),
            _slope_expr("_ratios", GROSS_NPA_CANDIDATES, out_name="GrossNPA_Slope"),
            _slope_expr("_ratios", NET_NPA_CANDIDATES, out_name="NetNPA_Slope"),
            _slope_expr("_ratios", DEBTOR_DAYS_CANDIDATES, out_name="DebtorDays_Slope"),
            _slope_expr("_ratios", WORKING_CAPITAL_CANDIDATES, out_name="WorkingCapital_Slope"),
        ])

    # ─────────────────────────────────────────────────────────
    # BALANCE SHEET TRENDS
    # ─────────────────────────────────────────────────────────
    if "_balance_sheet" in df.columns:
        exprs.extend([
            _slope_expr("_balance_sheet", BS_BORROWINGS_CANDIDATES, out_name="Borrowings_Slope"),
            _slope_expr("_balance_sheet", BS_RESERVES_CANDIDATES, out_name="Reserves_Slope"),
            _slope_expr("_balance_sheet", BS_DEPOSITS_CANDIDATES, out_name="Deposits_Slope"),
            _slope_expr("_balance_sheet", BS_ASSETS_CANDIDATES, out_name="Assets_Slope"),
            _growth_expr("_balance_sheet", BS_RESERVES_CANDIDATES, out_name="Reserves_Growth"),
        ])

    # Apply all expressions
    if exprs:
        df = df.with_columns(exprs)

    # ─────────────────────────────────────────────────────────
    # MOMENTUM LABELS
    # ─────────────────────────────────────────────────────────
    label_exprs = []

    # Fundamental Momentum (ROCE-based)
    if "ROCE_Slope" in df.columns:
        accel_col = "Sales_Q_Accel" if "Sales_Q_Accel" in df.columns else "ROCE_Slope"
        label_exprs.append(
            _label_expr("ROCE_Slope", accel_col, out_name="Fundamental_Momentum")
        )

    # Earnings Momentum (Profit-based)
    if "Profit_Q_Slope" in df.columns and "Profit_Q_Accel" in df.columns:
        label_exprs.append(
            _label_expr("Profit_Q_Slope", "Profit_Q_Accel", out_name="Earnings_Momentum")
        )

    # Sales Momentum
    if "Sales_Q_Slope" in df.columns and "Sales_Q_Accel" in df.columns:
        label_exprs.append(
            _label_expr("Sales_Q_Slope", "Sales_Q_Accel", out_name="Sales_Momentum")
        )

    # Bank Asset Quality Trend
    if "NetNPA_Slope" in df.columns:
        label_exprs.append(
            pl.when(pl.col("NetNPA_Slope") < -0.1)
            .then(pl.lit("IMPROVING"))
            .when(pl.col("NetNPA_Slope") > 0.1)
            .then(pl.lit("DETERIORATING"))
            .otherwise(pl.lit("STABLE"))
            .alias("Bank_Asset_Quality_Trend")
        )

    # Apply label expressions
    if label_exprs:
        df = df.with_columns(label_exprs)

    # ─────────────────────────────────────────────────────────
    # MOMENTUM SCORES
    # ─────────────────────────────────────────────────────────
    score_exprs = []

    if "Profit_Q_Slope" in df.columns and "Profit_Q_CV" in df.columns:
        score_exprs.append(
            _momentum_expr("Profit_Q_Slope", "Profit_Q_CV", out_name="Earnings_Momentum_Score")
        )

    if "Sales_Q_Slope" in df.columns and "Sales_Q_CV" in df.columns:
        score_exprs.append(
            _momentum_expr("Sales_Q_Slope", "Sales_Q_CV", out_name="Sales_Momentum_Score")
        )

    if score_exprs:
        df = df.with_columns(score_exprs)

    log.info(f"[FUND-TS] Added time-series features to {df.height} rows")
    return df


def add_composite_scores(df: pl.DataFrame) -> pl.DataFrame:
    """Add composite scores combining multiple trends.

    Adds:
        - Trend_Composite_Score: Weighted average of all trend signals
        - Quality_Trend_Score: Focus on quality metrics (ROCE, ROE, margins)
        - Growth_Trend_Score: Focus on growth metrics (sales, profit)
    """
    if df is None or df.is_empty():
        return df

    def _composite_score(row: Dict[str, Any]) -> Optional[float]:
        scores = []
        weights = []

        # Earnings momentum (weight: 0.3)
        if row.get("Earnings_Momentum_Score") is not None:
            scores.append(row["Earnings_Momentum_Score"])
            weights.append(0.3)

        # Sales momentum (weight: 0.2)
        if row.get("Sales_Momentum_Score") is not None:
            scores.append(row["Sales_Momentum_Score"])
            weights.append(0.2)

        # ROCE trend (weight: 0.25)
        roce_slope = row.get("ROCE_Slope")
        if roce_slope is not None:
            # Normalize slope to 0-100
            roce_score = max(0, min(100, 50 + roce_slope * 5))
            scores.append(roce_score)
            weights.append(0.25)

        # ROE trend (weight: 0.15)
        roe_slope = row.get("ROE_Slope")
        if roe_slope is not None:
            roe_score = max(0, min(100, 50 + roe_slope * 5))
            scores.append(roe_score)
            weights.append(0.15)

        # Profit stability (weight: 0.1)
        profit_cv = row.get("Profit_Q_CV")
        if profit_cv is not None:
            stability_score = max(0, min(100, 100 - profit_cv * 100))
            scores.append(stability_score)
            weights.append(0.1)

        if not scores:
            return None

        total_weight = sum(weights)
        return sum(s * w for s, w in zip(scores, weights)) / total_weight

    def _quality_trend(row: Dict[str, Any]) -> Optional[float]:
        scores = []

        for col in ["ROCE_Slope", "ROE_Slope", "OPM_Q_Slope"]:
            val = row.get(col)
            if val is not None:
                scores.append(max(0, min(100, 50 + val * 5)))

        return sum(scores) / len(scores) if scores else None

    def _growth_trend(row: Dict[str, Any]) -> Optional[float]:
        scores = []

        for col in ["Sales_Q_Slope", "Profit_Q_Slope", "EPS_Q_Slope"]:
            val = row.get(col)
            if val is not None:
                scores.append(max(0, min(100, 50 + val * 2)))

        return sum(scores) / len(scores) if scores else None

    # Apply composite calculations
    df = df.with_columns([
        pl.struct(df.columns)
        .map_elements(_composite_score, return_dtype=pl.Float64)
        .alias("Trend_Composite_Score"),

        pl.struct(df.columns)
        .map_elements(_quality_trend, return_dtype=pl.Float64)
        .alias("Quality_Trend_Score"),

        pl.struct(df.columns)
        .map_elements(_growth_trend, return_dtype=pl.Float64)
        .alias("Growth_Trend_Score"),
    ])

    return df


def analyze_timeseries(df: pl.DataFrame) -> Dict[str, Any]:
    """Get summary statistics for time-series features.

    Returns:
        Dict with summary stats for each trend column

    """
    if df is None or df.is_empty():
        return {}

    trend_cols = [
        c for c in df.columns
        if any(x in c for x in ["_Slope", "_Accel", "_CV", "_Momentum", "_Growth", "_Trend"])
    ]

    if not trend_cols:
        return {"message": "No trend columns found"}

    summary = {}

    for col in trend_cols:
        if col in df.columns and df[col].dtype.is_numeric():
            stats = df.select([
                pl.col(col).mean().alias("mean"),
                pl.col(col).std().alias("std"),
                pl.col(col).min().alias("min"),
                pl.col(col).max().alias("max"),
                pl.col(col).null_count().alias("null_count"),
            ]).row(0, named=True)
            summary[col] = stats

    return summary


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def add_timeseries_and_score(df: pl.DataFrame, scorer_fn) -> pl.DataFrame:
    """Add time-series features and then apply a scoring function.

    Args:
        df: Input DataFrame
        scorer_fn: Function that takes DataFrame and returns scored DataFrame

    Returns:
        DataFrame with trends and scores

    """
    work = add_timeseries_features(df)
    work = add_composite_scores(work)
    return scorer_fn(work)


def get_trend_columns() -> List[str]:
    """Get list of all trend column names that might be added."""
    return [
        # Quarterly slopes
        "Sales_Q_Slope", "Sales_Q_Accel", "Sales_Q_CV", "Sales_Q_Growth",
        "Profit_Q_Slope", "Profit_Q_Accel", "Profit_Q_CV",
        "EPS_Q_Slope", "EPS_Q_Accel", "EPS_Q_CV",
        "OPM_Q_Slope",

        # Annual slopes
        "Sales_Y_Slope", "Profit_Y_Slope", "EPS_Y_Slope",
        "Sales_Y_CAGR", "Profit_Y_CAGR",

        # Ratio slopes
        "ROCE_Slope", "ROE_Slope",
        "GrossNPA_Slope", "NetNPA_Slope",
        "DebtorDays_Slope", "WorkingCapital_Slope",

        # Balance sheet slopes
        "Borrowings_Slope", "Reserves_Slope", "Deposits_Slope", "Assets_Slope",
        "Reserves_Growth",

        # Labels
        "Fundamental_Momentum", "Earnings_Momentum", "Sales_Momentum",
        "Bank_Asset_Quality_Trend",

        # Scores
        "Earnings_Momentum_Score", "Sales_Momentum_Score",
        "Trend_Composite_Score", "Quality_Trend_Score", "Growth_Trend_Score",
    ]


# ============================================================
# EXPORTS
# ============================================================

EXPORTS = {
    "fundamentals_timeseries_engine": {
        "add_timeseries_features": add_timeseries_features,
        "add_composite_scores": add_composite_scores,
        "add_timeseries_and_score": add_timeseries_and_score,
        "analyze_timeseries": analyze_timeseries,
        "get_trend_columns": get_trend_columns,
    }
}


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    import sys

    print("\n" + "="*60)
    print("FUNDAMENTALS TIMESERIES ENGINE TEST")
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

    # Add timeseries features
    df = add_timeseries_features(df)
    df = add_composite_scores(df)

    print(f"Columns after: {len(df.columns)}")

    # Show trend columns
    trend_cols = [c for c in df.columns if any(x in c for x in ["_Slope", "_Momentum", "_Score"])]
    print(f"\nTrend columns added: {len(trend_cols)}")
    for col in trend_cols[:10]:
        print(f"  - {col}")
    if len(trend_cols) > 10:
        print(f"  ... and {len(trend_cols) - 10} more")

    # Show sample
    display_cols = ["Symbol", "Fundamental_Momentum", "Earnings_Momentum", "Trend_Composite_Score"]
    available = [c for c in display_cols if c in df.columns]

    if available:
        print("\nSample data:")
        print(df.select(available).head(10))

    # Show summary stats
    summary = analyze_timeseries(df)
    print(f"\nSummary stats for {len(summary)} trend columns")

    print("\n" + "="*60)
