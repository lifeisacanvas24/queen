#!/usr/bin/env python3
# ============================================================
# queen/technicals/fundamentals_score_engine.py — v3.3 (CANONICAL)
# MAX + Intrinsic + PowerScore — Pure Polars
# ============================================================
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from queen.helpers.fundamentals_registry import REGISTRY
from queen.helpers.logger import log
from queen.settings.fundamentals_map import (
    FUNDAMENTALS_IMPORTANCE_MAP,
    FUNDAMENTALS_METRIC_COLUMNS,
    FUNDAMENTALS_TACTICAL_FILTERS,
    INTRINSIC_BUCKETS,
    POWERSCORE_WEIGHTS,
)

# normalize tactical filters contract
if isinstance(FUNDAMENTALS_TACTICAL_FILTERS, list):
    FUNDAMENTALS_TACTICAL_FILTERS = {"filters": FUNDAMENTALS_TACTICAL_FILTERS}
TACTICAL_FILTER_LIST = FUNDAMENTALS_TACTICAL_FILTERS.get("filters", [])

MIN_SECTOR_RANK_N = int(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_SECTOR_RANK_N", 5))
MIN_GLOBAL_RANK_N = int(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_GLOBAL_RANK_N", 20))

MAX_DEBT_EQUITY     = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MAX_DEBT_EQUITY", 2.0))
MAX_GROSS_NPA_PCT   = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MAX_GROSS_NPA_PCT", 8.0))
MAX_NET_NPA_PCT     = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MAX_NET_NPA_PCT", 4.0))

MIN_ROCE_PCT        = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_ROCE_PCT", 10.0))
MIN_ROE_PCT         = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_ROE_PCT", 10.0))
MIN_EPS_TTM         = float(FUNDAMENTALS_TACTICAL_FILTERS.get("MIN_EPS_TTM", 0.0))

def _safe_z(x: Optional[float], mean: Optional[float], std: Optional[float]) -> Optional[float]:
    if x is None or mean is None or std in (None, 0):
        return None
    return (x - mean) / std

def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))

def _bucket(score: float) -> str:
    for thr, b in INTRINSIC_BUCKETS:
        if score >= thr:
            return b
    return "D"

def _coalesce(*vals):
    for v in vals:
        if v is not None:
            return v
    return None

# ------------------------------------------------------------
# Z-scores (sector + global)
# ------------------------------------------------------------
def add_zscores(df: pl.DataFrame) -> pl.DataFrame:
    if df is None or df.is_empty():
        return df

    if not REGISTRY.columns:
        REGISTRY.load(df, FUNDAMENTALS_METRIC_COLUMNS)

    cols = REGISTRY.columns
    sector_col = "Sector" if "Sector" in df.columns else "sector"

    exprs: List[pl.Expr] = []
    for c in cols:
        mean_g = REGISTRY.global_metric(f"{c}_mean")
        std_g  = REGISTRY.global_metric(f"{c}_std")

        exprs.append(
            pl.col(c).map_elements(
                lambda x, m=mean_g, s=std_g: _safe_z(x, m, s),
                return_dtype=pl.Float64,
            ).alias(f"{c}_z_global")
        )

        exprs.append(
            pl.struct([sector_col, c]).map_elements(
                lambda s, col=c: _safe_z(
                    s.get(col),
                    (REGISTRY.sector_stats(s.get(sector_col)) or {}).get(f"{col}_mean"),
                    (REGISTRY.sector_stats(s.get(sector_col)) or {}).get(f"{col}_std"),
                ),
                return_dtype=pl.Float64,
            ).alias(f"{c}_z_sector")
        )

    return df.with_columns(exprs)

# ------------------------------------------------------------
# Intrinsic score
# ------------------------------------------------------------
def add_intrinsic_score(df: pl.DataFrame) -> pl.DataFrame:
    if df is None or df.is_empty():
        return df

    work = add_zscores(df)
    weight_map = FUNDAMENTALS_IMPORTANCE_MAP or {}

    z_cols = [f"{c}_z_sector" for c in REGISTRY.columns if f"{c}_z_sector" in work.columns]

    def _row_intrinsic(r: Dict[str, Any]) -> Optional[float]:
        total_w = 0.0
        sum_wz = 0.0
        for c in REGISTRY.columns:
            z = r.get(f"{c}_z_sector")
            if z is None:
                continue
            w = float(weight_map.get(c, 1.0))
            total_w += w
            sum_wz += w * z
        if total_w == 0:
            return None
        return _sigmoid(sum_wz / total_w) * 100.0

    work = work.with_columns(
        pl.struct(z_cols).map_elements(_row_intrinsic, return_dtype=pl.Float64)
        .alias("Intrinsic_Score")
    ).with_columns(
        pl.col("Intrinsic_Score")
        .map_elements(lambda s: _bucket(s or 0.0), return_dtype=pl.Utf8)
        .alias("Intrinsic_Bucket")
    )
    return work

# ------------------------------------------------------------
# PowerScore v1.0
# ------------------------------------------------------------
def add_powerscore(df: pl.DataFrame) -> pl.DataFrame:
    if df is None or df.is_empty():
        return df

    def dim_profitability(r):
        return (_coalesce(r.get("roce_pct"), 0) + _coalesce(r.get("roe_pct"), 0)) / 2.0

    def dim_growth(r):
        return _coalesce(r.get("sales_cagr_10y"), 0) * 0.6 + _coalesce(r.get("profit_cagr_10y"), 0) * 0.4

    def dim_efficiency(r):
        return _coalesce(r.get("ROCE_Slope"), 0)

    def dim_valuation(r):
        pe = r.get("pe_ratio")
        return 1.0 / pe if pe and pe > 0 else 0.0

    def dim_leverage(r):
        de = r.get("debt_to_equity")
        return 1.0 / (1.0 + de) if de is not None else 0.0

    def dim_momentum(r):
        lab = r.get("Fundamental_Momentum")
        return 1.0 if lab == "RISING" else 0.5 if lab else 0.0

    def dim_stability(r):
        cv = r.get("Profit_Q_CV")
        return 1.0 / (1.0 + cv) if cv is not None else 0.0

    def dim_ownership(r):
        return _coalesce(r.get("sh_promoters_pct_holding_latest"), 0)

    dims = {
        "profitability": dim_profitability,
        "growth": dim_growth,
        "efficiency": dim_efficiency,
        "valuation": dim_valuation,
        "leverage": dim_leverage,
        "momentum": dim_momentum,
        "stability": dim_stability,
        "ownership": dim_ownership,
    }

    def _powerscore_row(r: Dict[str, Any]) -> float:
        s = 0.0
        tw = 0.0
        for k, fn in dims.items():
            w = float(POWERSCORE_WEIGHTS.get(k, 0.0))
            tw += w
            s += w * float(fn(r) or 0.0)
        return _sigmoid(s / tw) * 100.0 if tw else 0.0

    return df.with_columns(
        pl.struct(df.columns)
        .map_elements(_powerscore_row, return_dtype=pl.Float64)
        .alias("PowerScore")
    )

# ------------------------------------------------------------
# Pass/Fail
# ------------------------------------------------------------
def add_pass_fail(df: pl.DataFrame) -> pl.DataFrame:
    if df is None or df.is_empty():
        return df

    def _fails(r: Dict[str, Any]) -> Tuple[bool, str]:
        fail_reasons = []

        roce = r.get("roce_pct")
        roe  = r.get("roe_pct")
        de   = r.get("debt_to_equity")
        eps  = r.get("eps_ttm")
        gnpa = r.get("gross_npa_pct")
        nnpa = r.get("net_npa_pct")

        if roce is not None and roce < MIN_ROCE_PCT:
            fail_reasons.append("Low ROCE")
        if roe is not None and roe < MIN_ROE_PCT:
            fail_reasons.append("Low ROE")
        if de is not None and de > MAX_DEBT_EQUITY:
            fail_reasons.append("High Debt/Equity")
        if eps is not None and eps <= MIN_EPS_TTM:
            fail_reasons.append("Negative EPS")

        if gnpa is not None and gnpa > MAX_GROSS_NPA_PCT:
            fail_reasons.append("High Gross NPA")
        if nnpa is not None and nnpa > MAX_NET_NPA_PCT:
            fail_reasons.append("High Net NPA")

        return (len(fail_reasons) > 0, ", ".join(fail_reasons))

    return df.with_columns(
        pl.struct(df.columns).map_elements(lambda r: not _fails(r)[0], return_dtype=pl.Boolean)
        .alias("Fundamental_Pass"),
        pl.struct(df.columns).map_elements(lambda r: _fails(r)[1], return_dtype=pl.Utf8)
        .alias("Fundamental_Fail_Reasons"),
    )

# ------------------------------------------------------------
# Public pipeline
# ------------------------------------------------------------
def score_and_filter(df: pl.DataFrame) -> pl.DataFrame:
    if df is None or df.is_empty():
        return df
    work = add_intrinsic_score(df)
    work = add_powerscore(work)
    work = add_pass_fail(work)
    log.info(f"[FUND-SCORE] Scored {work.height} symbols")
    return work

EXPORTS = {"fundamentals_score_engine": {
    "score_and_filter": score_and_filter,
    "add_intrinsic_score": add_intrinsic_score,
    "add_powerscore": add_powerscore,
    "add_pass_fail": add_pass_fail,
}}
