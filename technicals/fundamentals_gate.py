#!/usr/bin/env python3
# ============================================================
# queen/technicals/fundamentals_gate.py — v4.0 (COMPATIBLE WITH SCRAPER v7.0)
# ------------------------------------------------------------
# Final integration layer for fundamental filtering and boosting.
#
# Features:
#   - Hard gate: Block alerts if fundamentals fail
#   - Soft boost: Apply multiplier based on quality bucket
#   - PowerScore-based gating
#   - Trend-aware gating
#   - Sector-relative filtering
#
# Usage:
#   from queen.technicals.fundamentals_gate import (
#       fundamentals_overlay_df,
#       fundamentals_gate_and_boost,
#       apply_comprehensive_gate,
#   )
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

# Try to import settings
try:
    from queen.settings.fundamentals_map import (
        FUNDAMENTALS_TACTICAL_FILTERS,
        POWERSCORE_WEIGHTS,
    )
except ImportError:
    FUNDAMENTALS_TACTICAL_FILTERS = {}
    POWERSCORE_WEIGHTS = {}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _pick_col(df: pl.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    """Return the name of the first column that exists in the DataFrame."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _ensure_symbol_col(df: pl.DataFrame, preferred: str = "Symbol") -> str:
    """Ensure a symbol column exists and return its name."""
    col = _pick_col(df, [preferred, preferred.lower(), "symbol", "SYMBOL"])
    if not col:
        raise ValueError(
            "[FUND-GATE] No symbol column found. Expected: Symbol/symbol/SYMBOL"
        )
    return col


def _coalesce(*vals):
    """Return first non-None value."""
    for v in vals:
        if v is not None:
            return v
    return None


# ============================================================
# OVERLAY SELECTION
# ============================================================

def fundamentals_overlay_df(
    fundamentals_df: pl.DataFrame,
    *,
    symbol_col: str = "Symbol",
    include_trends: bool = True,
    include_raw_metrics: bool = False,
) -> pl.DataFrame:
    """
    Select and return only the necessary scoring/filtering columns
    from the full fundamentals DataFrame.

    Args:
        fundamentals_df: Full fundamentals DataFrame with all columns
        symbol_col: Name of symbol column
        include_trends: Include trend/momentum columns
        include_raw_metrics: Include raw metric values (market_cap, pe_ratio, etc.)

    Returns:
        DataFrame with selected overlay columns
    """
    if fundamentals_df is None or fundamentals_df.is_empty():
        return pl.DataFrame()

    f_sym = _ensure_symbol_col(fundamentals_df, symbol_col)

    # Core scoring columns (always included)
    core_cols = [
        "Fundamental_Pass",
        "Fundamental_Fail_Reasons",
        "Intrinsic_Bucket",
        "Intrinsic_Score",
        "PowerScore",
        "PowerScore_v1",  # Legacy alias
    ]

    # Trend/momentum columns (optional)
    trend_cols = [
        "Fundamental_Momentum",
        "Earnings_Momentum",
        "Sales_Momentum",
        "Bank_Asset_Quality_Trend",
        "Trend_Composite_Score",
        "Quality_Trend_Score",
        "Growth_Trend_Score",
        "Earnings_Momentum_Score",
        "Sales_Momentum_Score",
    ]

    # Rank columns
    rank_cols = [
        "Sector_Rank",
        "Global_Rank",
        "PowerScore_Rank",
    ]

    # Raw metric columns (optional)
    raw_metric_cols = [
        "Sector",
        "sector",
        "market_cap",
        "pe_ratio",
        "roce_pct",
        "roe_pct",
        "debt_to_equity",
        "eps_ttm",
        "sh_promoters_pct",
        "sh_fii_pct",
        "promoter_pledge_pct",
        "sales_cagr_5y",
        "profit_cagr_5y",
    ]

    # Build selection list
    selection = [f_sym]

    # Add core columns
    for col in core_cols:
        if col in fundamentals_df.columns:
            selection.append(col)

    # Add trend columns if requested
    if include_trends:
        for col in trend_cols:
            if col in fundamentals_df.columns:
                selection.append(col)

    # Add rank columns
    for col in rank_cols:
        if col in fundamentals_df.columns:
            selection.append(col)

    # Add raw metrics if requested
    if include_raw_metrics:
        for col in raw_metric_cols:
            if col in fundamentals_df.columns:
                selection.append(col)

    # Remove duplicates while preserving order
    seen = set()
    unique_selection = []
    for col in selection:
        if col not in seen:
            seen.add(col)
            unique_selection.append(col)

    if len(unique_selection) <= 1:
        log.warning("[FUND-GATE] Fundamentals DF missing core scoring columns.")
        return fundamentals_df.select(f_sym)

    return fundamentals_df.select(unique_selection)


# ============================================================
# GATE AND BOOST LOGIC
# ============================================================

def fundamentals_gate_and_boost(
    joined: pl.DataFrame,
    *,
    hard_gate: bool = True,
    boost_map: Optional[Dict[str, float]] = None,
    score_col: str = "Technical_Score",
    alert_col: str = "Technical_Alert",
    out_score_col: Optional[str] = None,
    out_alert_col: str = "Final_Alert",
    pass_col: str = "Fundamental_Pass",
    bucket_col: str = "Intrinsic_Bucket",
) -> pl.DataFrame:
    """
    Apply fundamental pass/fail as a hard filter and optional score boost.

    Args:
        joined: DataFrame with both technical and fundamental columns
        hard_gate: If True, block alerts when Fundamental_Pass is False
        boost_map: Dict mapping bucket to boost multiplier (e.g., {"A": 1.5, "B": 1.2})
        score_col: Input score column to boost
        alert_col: Input alert column to gate
        out_score_col: Output boosted score column name
        out_alert_col: Output gated alert column name
        pass_col: Column containing pass/fail boolean
        bucket_col: Column containing quality bucket (A/B/C/D)

    Returns:
        DataFrame with gated alerts and boosted scores
    """
    if joined is None or joined.is_empty():
        return pl.DataFrame()

    # Find actual column names
    pass_c = _pick_col(joined, [pass_col, "Fundamental_Pass"])
    bucket_c = _pick_col(joined, [bucket_col, "Intrinsic_Bucket"])

    # Set default alert column if missing
    if alert_col not in joined.columns:
        joined = joined.with_columns(pl.lit("➡️ Stable").alias(alert_col))

    # ─────────────────────────────────────────────────────────
    # 1. HARD GATE: Block Alert if Fundamental_Pass is False or NULL
    # ─────────────────────────────────────────────────────────
    if hard_gate and pass_c:
        is_blocked = pl.col(pass_c).is_null() | (pl.col(pass_c) == False)

        joined = joined.with_columns(
            pl.when(is_blocked)
            .then(pl.lit("⛔ Fundamentals Blocked"))
            .otherwise(pl.col(alert_col))
            .alias(out_alert_col)
        )
    else:
        # If hard_gate is False, just copy the alert
        joined = joined.with_columns(pl.col(alert_col).alias(out_alert_col))

    # ─────────────────────────────────────────────────────────
    # 2. SOFT BOOST: Apply multiplier to an existing score column
    # ─────────────────────────────────────────────────────────
    if boost_map and bucket_c and score_col in joined.columns and pass_c:
        out_score_col = out_score_col or f"{score_col}_FundBoost"

        # Build conditional boost expression
        boost_expr = pl.lit(1.0)  # Default factor

        for bucket, factor in boost_map.items():
            condition = (pl.col(bucket_c) == bucket) & (pl.col(pass_c) == True)
            boost_expr = pl.when(condition).then(pl.lit(float(factor))).otherwise(boost_expr)

        joined = joined.with_columns(
            (pl.col(score_col).cast(pl.Float64) * boost_expr).alias(out_score_col)
        )
        log.info(f"[FUND-GATE] Applied boost to '{score_col}' via bucket map.")

    return joined


# ============================================================
# POWERSCORE-BASED GATING
# ============================================================

def apply_powerscore_gate(
    df: pl.DataFrame,
    *,
    min_powerscore: float = 50.0,
    powerscore_col: str = "PowerScore",
    out_col: str = "PowerScore_Pass",
) -> pl.DataFrame:
    """
    Gate based on PowerScore threshold.

    Args:
        df: Input DataFrame
        min_powerscore: Minimum PowerScore to pass (0-100)
        powerscore_col: Column containing PowerScore
        out_col: Output column name for pass/fail

    Returns:
        DataFrame with PowerScore_Pass column
    """
    if df is None or df.is_empty():
        return df

    ps_col = _pick_col(df, [powerscore_col, "PowerScore", "PowerScore_v1"])

    if not ps_col:
        log.warning("[FUND-GATE] No PowerScore column found for gating")
        return df.with_columns(pl.lit(True).alias(out_col))

    df = df.with_columns(
        (pl.col(ps_col) >= min_powerscore).alias(out_col)
    )

    passed = df.filter(pl.col(out_col)).height
    log.info(f"[FUND-GATE] PowerScore gate: {passed}/{df.height} passed (>= {min_powerscore})")

    return df


# ============================================================
# TREND-BASED GATING
# ============================================================

def apply_trend_gate(
    df: pl.DataFrame,
    *,
    require_rising: bool = False,
    block_falling: bool = True,
    momentum_col: str = "Fundamental_Momentum",
    out_col: str = "Trend_Pass",
) -> pl.DataFrame:
    """
    Gate based on fundamental momentum/trend.

    Args:
        df: Input DataFrame
        require_rising: If True, only pass RISING momentum
        block_falling: If True, block FALLING momentum
        momentum_col: Column containing momentum label
        out_col: Output column name

    Returns:
        DataFrame with Trend_Pass column
    """
    if df is None or df.is_empty():
        return df

    mom_col = _pick_col(df, [momentum_col, "Fundamental_Momentum", "Earnings_Momentum"])

    if not mom_col:
        log.warning("[FUND-GATE] No momentum column found for trend gating")
        return df.with_columns(pl.lit(True).alias(out_col))

    if require_rising:
        # Only pass if RISING
        df = df.with_columns(
            pl.col(mom_col).str.contains("RISING").fill_null(False).alias(out_col)
        )
    elif block_falling:
        # Pass unless FALLING (without RECOVERING)
        df = df.with_columns(
            (~(pl.col(mom_col) == "FALLING")).fill_null(True).alias(out_col)
        )
    else:
        df = df.with_columns(pl.lit(True).alias(out_col))

    passed = df.filter(pl.col(out_col)).height
    log.info(f"[FUND-GATE] Trend gate: {passed}/{df.height} passed")

    return df


# ============================================================
# BANK-SPECIFIC ASSET QUALITY GATE
# ============================================================

def apply_bank_asset_gate(
    df: pl.DataFrame,
    *,
    block_deteriorating: bool = True,
    out_col: str = "Bank_Asset_Pass",
) -> pl.DataFrame:
    """
    Gate banks based on asset quality trend.

    Args:
        df: Input DataFrame
        block_deteriorating: If True, block banks with deteriorating asset quality
        out_col: Output column name

    Returns:
        DataFrame with Bank_Asset_Pass column
    """
    if df is None or df.is_empty():
        return df

    aq_col = _pick_col(df, ["Bank_Asset_Quality_Trend"])

    if not aq_col:
        # No bank asset quality column - pass all
        return df.with_columns(pl.lit(True).alias(out_col))

    if block_deteriorating:
        df = df.with_columns(
            (pl.col(aq_col) != "DETERIORATING").fill_null(True).alias(out_col)
        )
    else:
        df = df.with_columns(pl.lit(True).alias(out_col))

    passed = df.filter(pl.col(out_col)).height
    log.info(f"[FUND-GATE] Bank asset gate: {passed}/{df.height} passed")

    return df


# ============================================================
# SECTOR-RELATIVE GATING
# ============================================================

def apply_sector_rank_gate(
    df: pl.DataFrame,
    *,
    max_sector_rank: int = 10,
    rank_col: str = "Sector_Rank",
    out_col: str = "Sector_Rank_Pass",
) -> pl.DataFrame:
    """
    Gate based on sector rank.

    Args:
        df: Input DataFrame
        max_sector_rank: Maximum sector rank to pass
        rank_col: Column containing sector rank
        out_col: Output column name

    Returns:
        DataFrame with Sector_Rank_Pass column
    """
    if df is None or df.is_empty():
        return df

    r_col = _pick_col(df, [rank_col, "Sector_Rank", "sector_rank"])

    if not r_col:
        log.warning("[FUND-GATE] No sector rank column found")
        return df.with_columns(pl.lit(True).alias(out_col))

    df = df.with_columns(
        (pl.col(r_col) <= max_sector_rank).fill_null(True).alias(out_col)
    )

    passed = df.filter(pl.col(out_col)).height
    log.info(f"[FUND-GATE] Sector rank gate: {passed}/{df.height} passed (<= {max_sector_rank})")

    return df


# ============================================================
# COMPREHENSIVE GATE (COMBINES ALL)
# ============================================================

def apply_comprehensive_gate(
    df: pl.DataFrame,
    *,
    require_fundamental_pass: bool = True,
    min_powerscore: float = 40.0,
    block_falling_trend: bool = True,
    block_deteriorating_banks: bool = True,
    max_sector_rank: Optional[int] = None,
    out_col: str = "Gate_Pass",
) -> pl.DataFrame:
    """
    Apply comprehensive gating combining all filters.

    Args:
        df: Input DataFrame
        require_fundamental_pass: Require Fundamental_Pass = True
        min_powerscore: Minimum PowerScore threshold
        block_falling_trend: Block FALLING momentum
        block_deteriorating_banks: Block banks with deteriorating asset quality
        max_sector_rank: Maximum sector rank (None = no filter)
        out_col: Output column for combined pass/fail

    Returns:
        DataFrame with Gate_Pass column and all intermediate gate columns
    """
    if df is None or df.is_empty():
        return df

    work = df.clone()
    gate_cols = []

    # 1. Fundamental Pass
    if require_fundamental_pass:
        pass_col = _pick_col(work, ["Fundamental_Pass"])
        if pass_col:
            gate_cols.append(pass_col)

    # 2. PowerScore Gate
    if min_powerscore > 0:
        work = apply_powerscore_gate(work, min_powerscore=min_powerscore)
        gate_cols.append("PowerScore_Pass")

    # 3. Trend Gate
    if block_falling_trend:
        work = apply_trend_gate(work, block_falling=True)
        gate_cols.append("Trend_Pass")

    # 4. Bank Asset Gate
    if block_deteriorating_banks:
        work = apply_bank_asset_gate(work, block_deteriorating=True)
        gate_cols.append("Bank_Asset_Pass")

    # 5. Sector Rank Gate
    if max_sector_rank is not None:
        work = apply_sector_rank_gate(work, max_sector_rank=max_sector_rank)
        gate_cols.append("Sector_Rank_Pass")

    # Combine all gates
    if not gate_cols:
        work = work.with_columns(pl.lit(True).alias(out_col))
    else:
        # Filter to only existing columns
        existing_gates = [c for c in gate_cols if c in work.columns]

        if not existing_gates:
            work = work.with_columns(pl.lit(True).alias(out_col))
        else:
            # AND all gate conditions
            combined = pl.lit(True)
            for col in existing_gates:
                combined = combined & pl.col(col).fill_null(True)

            work = work.with_columns(combined.alias(out_col))

    passed = work.filter(pl.col(out_col)).height
    log.info(f"[FUND-GATE] Comprehensive gate: {passed}/{work.height} passed")

    return work


# ============================================================
# ALERT ENHANCEMENT
# ============================================================

def enhance_alerts_with_fundamentals(
    alerts_df: pl.DataFrame,
    fundamentals_df: pl.DataFrame,
    *,
    symbol_col: str = "Symbol",
    boost_map: Optional[Dict[str, float]] = None,
) -> pl.DataFrame:
    """
    Enhance technical alerts with fundamental data.

    Args:
        alerts_df: DataFrame with technical alerts
        fundamentals_df: DataFrame with fundamental scores
        symbol_col: Symbol column name for joining
        boost_map: Optional boost multipliers by bucket

    Returns:
        Enhanced alerts DataFrame
    """
    if alerts_df is None or alerts_df.is_empty():
        return alerts_df

    if fundamentals_df is None or fundamentals_df.is_empty():
        log.warning("[FUND-GATE] No fundamentals data for enhancement")
        return alerts_df

    # Get overlay columns
    overlay = fundamentals_overlay_df(fundamentals_df, include_trends=True)

    # Ensure consistent symbol column
    a_sym = _ensure_symbol_col(alerts_df, symbol_col)
    f_sym = _ensure_symbol_col(overlay, symbol_col)

    # Join
    if a_sym != f_sym:
        overlay = overlay.rename({f_sym: a_sym})

    joined = alerts_df.join(overlay, on=a_sym, how="left")

    # Apply gate and boost
    if boost_map is None:
        boost_map = {"A": 1.5, "B": 1.2, "C": 1.0, "D": 0.8}

    joined = fundamentals_gate_and_boost(
        joined,
        hard_gate=True,
        boost_map=boost_map,
        score_col="score" if "score" in joined.columns else "Technical_Score",
        alert_col="alert" if "alert" in joined.columns else "Technical_Alert",
    )

    return joined


# ============================================================
# RANKING HELPERS
# ============================================================

def add_combined_rank(
    df: pl.DataFrame,
    *,
    powerscore_weight: float = 0.6,
    trend_weight: float = 0.4,
    out_col: str = "Combined_Rank",
) -> pl.DataFrame:
    """
    Add combined rank based on PowerScore and trend scores.

    Args:
        df: Input DataFrame
        powerscore_weight: Weight for PowerScore
        trend_weight: Weight for Trend_Composite_Score
        out_col: Output column name

    Returns:
        DataFrame with Combined_Rank column
    """
    if df is None or df.is_empty():
        return df

    ps_col = _pick_col(df, ["PowerScore", "PowerScore_v1"])
    ts_col = _pick_col(df, ["Trend_Composite_Score"])

    if not ps_col:
        log.warning("[FUND-GATE] No PowerScore column for combined ranking")
        return df

    if ts_col:
        # Weighted combination
        df = df.with_columns(
            (
                pl.col(ps_col).fill_null(0) * powerscore_weight +
                pl.col(ts_col).fill_null(0) * trend_weight
            ).alias("_combined_score")
        )
    else:
        # Just use PowerScore
        df = df.with_columns(
            pl.col(ps_col).fill_null(0).alias("_combined_score")
        )

    # Rank (descending - higher score = better rank)
    df = df.with_columns(
        pl.col("_combined_score").rank(descending=True).alias(out_col)
    ).drop("_combined_score")

    return df


# ============================================================
# EXPORTS
# ============================================================

EXPORTS = {
    "fundamentals_gate": {
        "fundamentals_overlay_df": fundamentals_overlay_df,
        "fundamentals_gate_and_boost": fundamentals_gate_and_boost,
        "apply_powerscore_gate": apply_powerscore_gate,
        "apply_trend_gate": apply_trend_gate,
        "apply_bank_asset_gate": apply_bank_asset_gate,
        "apply_sector_rank_gate": apply_sector_rank_gate,
        "apply_comprehensive_gate": apply_comprehensive_gate,
        "enhance_alerts_with_fundamentals": enhance_alerts_with_fundamentals,
        "add_combined_rank": add_combined_rank,
    }
}


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    import sys

    print("\n" + "="*60)
    print("FUNDAMENTALS GATE TEST")
    print("="*60)

    try:
        from queen.helpers.fundamentals_polars_engine import load_all
        from queen.helpers.fundamentals_timeseries_engine import add_timeseries_features
        from queen.technicals.fundamentals_score_engine import score_and_filter
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

    # Add trends
    df = add_timeseries_features(df)
    print(f"Added timeseries features")

    # Score
    df = score_and_filter(df)
    print(f"Added scores")

    # Apply comprehensive gate
    df = apply_comprehensive_gate(
        df,
        require_fundamental_pass=True,
        min_powerscore=40.0,
        block_falling_trend=True,
    )

    # Show results
    passed = df.filter(pl.col("Gate_Pass")).height
    print(f"\nComprehensive gate: {passed}/{df.height} passed")

    # Show sample
    display_cols = ["Symbol", "PowerScore", "Fundamental_Pass", "Gate_Pass"]
    available = [c for c in display_cols if c in df.columns]

    if available:
        print("\nSample data (passed only):")
        print(df.filter(pl.col("Gate_Pass")).select(available).head(10))

    print("\n" + "="*60)
