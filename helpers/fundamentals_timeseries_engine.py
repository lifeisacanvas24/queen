#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_timeseries_engine.py — v1.1 (PURE POLARS)
# ------------------------------------------------------------
# Adds trend features over time-series fundamentals:
#   • slopes (ROCE/ROE/Sales/Profit/EPS/NPA)
#   • QoQ acceleration
#   • earnings stability (CV)
#   • simple momentum labels
#
# Zero pandas. Zero numpy. 100% Polars-safe.
#
# Input DF  = output of fundamentals_polars_engine.load_all()
# Deep tables live under: _quarters / _profit_loss / _balance_sheet / _ratios
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import polars as pl
from queen.helpers.logger import log

# ------------------------------------------------------------
# Python helpers (safe, no pandas)
# ------------------------------------------------------------
def _is_series_dict(x: Any) -> bool:
    return isinstance(x, dict) and len(x) > 0


def _series_values(series_dict: Dict[str, Any]) -> List[float]:
    out: List[float] = []
    for _, v in series_dict.items():  # Screener preserves chronological order
        if v is None:
            continue
        try:
            out.append(float(v))
        except Exception:
            continue
    return out


def _first_last_slope(vals: List[float]) -> Optional[float]:
    if not vals or len(vals) < 2:
        return None
    return (vals[-1] - vals[0]) / max(1, len(vals) - 1)


def _qoq_accel(vals: List[float]) -> Optional[float]:
    if not vals or len(vals) < 3:
        return None
    return (vals[-1] - vals[-2]) - (vals[-2] - vals[-3])


def _cv(vals: List[float]) -> Optional[float]:
    if not vals or len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    if m == 0:
        return None
    var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    return (var ** 0.5) / abs(m)


def _pick_series_from_table(table: Any, candidates: Sequence[str]) -> Optional[List[float]]:
    """Return list of floats for first available metric key."""
    if not isinstance(table, dict):
        return None
    for k in candidates:
        sdict = table.get(k)
        if _is_series_dict(sdict):
            vals = _series_values(sdict)
            if vals:
                return vals
    return None


def _trend_label(slope: Optional[float], accel: Optional[float]) -> Optional[str]:
    if slope is None:
        return None

    if slope > 0 and (accel is None or accel >= 0):
        return "RISING"

    if slope > 0 and accel is not None and accel < 0:
        return "RISING_BUT_SLOWING"

    if slope < 0 and (accel is None or accel <= 0):
        return "FALLING"

    if slope < 0 and accel is not None and accel > 0:
        return "FALLING_BUT_RECOVERING"

    return "FLAT"


# ------------------------------------------------------------
# Polars expression builders
# ------------------------------------------------------------
def _slope_expr(table_col: str, candidates: Sequence[str], *, out_name: str) -> pl.Expr:
    return (
        pl.col(table_col)
        .map_elements(
            lambda t: _first_last_slope(_pick_series_from_table(t, candidates) or []),
            return_dtype=pl.Float64,
        )
        .alias(out_name)
    )


def _accel_expr(table_col: str, candidates: Sequence[str], *, out_name: str) -> pl.Expr:
    return (
        pl.col(table_col)
        .map_elements(
            lambda t: _qoq_accel(_pick_series_from_table(t, candidates) or []),
            return_dtype=pl.Float64,
        )
        .alias(out_name)
    )


def _cv_expr(table_col: str, candidates: Sequence[str], *, out_name: str) -> pl.Expr:
    return (
        pl.col(table_col)
        .map_elements(
            lambda t: _cv(_pick_series_from_table(t, candidates) or []),
            return_dtype=pl.Float64,
        )
        .alias(out_name)
    )


def _label_expr(slope_col: str, accel_col: str, *, out_name: str) -> pl.Expr:
    return (
        pl.struct([slope_col, accel_col])
        .map_elements(
            lambda s: _trend_label(s.get(slope_col), s.get(accel_col)),
            return_dtype=pl.Utf8,
        )
        .alias(out_name)
    )


# ------------------------------------------------------------
# 🚀 MAIN ENGINE
# ------------------------------------------------------------
def add_timeseries_features(df: pl.DataFrame) -> pl.DataFrame:
    if df is None or df.is_empty():
        return df

    exprs: List[pl.Expr] = []

    # -----------------------------
    # QUARTERLY trends
    # -----------------------------
    if "_quarters" in df.columns:
        exprs += [
            _slope_expr("_quarters", ["q_sales"], out_name="Sales_Q_Slope"),
            _accel_expr("_quarters", ["q_sales"], out_name="Sales_Q_Accel"),

            _slope_expr("_quarters", ["q_np"], out_name="Profit_Q_Slope"),
            _accel_expr("_quarters", ["q_np"], out_name="Profit_Q_Accel"),

            _slope_expr("_quarters", ["q_eps"], out_name="EPS_Q_Slope"),
            _accel_expr("_quarters", ["q_eps"], out_name="EPS_Q_Accel"),

            _cv_expr("_quarters", ["q_np"], out_name="Profit_Q_CV"),
        ]

    # -----------------------------
    # ANNUAL trends
    # -----------------------------
    if "_profit_loss" in df.columns:
        exprs += [
            _slope_expr("_profit_loss", ["pl_sales"], out_name="Sales_Y_Slope"),
            _slope_expr("_profit_loss", ["pl_np"], out_name="Profit_Y_Slope"),
            _slope_expr("_profit_loss", ["pl_eps"], out_name="EPS_Y_Slope"),
        ]

    # -----------------------------
    # RATIO trends (ROCE/ROE + NPA)
    # -----------------------------
    if "_ratios" in df.columns:
        exprs += [
            _slope_expr("_ratios", ["roce_pct"], out_name="ROCE_Slope"),
            _slope_expr("_ratios", ["roe_pct"], out_name="ROE_Slope"),

            _slope_expr("_ratios", ["gross_npa_pct"], out_name="GrossNPA_Slope"),
            _slope_expr("_ratios", ["net_npa_pct"], out_name="NetNPA_Slope"),
        ]

    # -----------------------------
    # BALANCE SHEET trends
    # -----------------------------
    if "_balance_sheet" in df.columns:
        exprs += [
            _slope_expr("_balance_sheet", ["bs_borrowings"], out_name="Borrowings_Slope"),
            _slope_expr("_balance_sheet", ["bs_deposits"], out_name="Deposits_Slope"),
        ]

    if exprs:
        df = df.with_columns(exprs)

    # -----------------------------
    # Human-readable momentum labels
    # -----------------------------
    label_exprs = []

    if "ROCE_Slope" in df.columns and "Sales_Q_Accel" in df.columns:
        label_exprs.append(
            _label_expr("ROCE_Slope", "Sales_Q_Accel", out_name="Fundamental_Momentum")
        )

    if "Profit_Q_Slope" in df.columns and "Profit_Q_Accel" in df.columns:
        label_exprs.append(
            _label_expr("Profit_Q_Slope", "Profit_Q_Accel", out_name="Earnings_Momentum")
        )

    if "NetNPA_Slope" in df.columns:
        label_exprs.append(
            pl.when(pl.col("NetNPA_Slope") < 0)
            .then(pl.lit("IMPROVING_ASSET_QUALITY"))
            .when(pl.col("NetNPA_Slope") > 0)
            .then(pl.lit("WORSENING_ASSET_QUALITY"))
            .otherwise(None)
            .alias("Bank_Asset_Quality_Trend")
        )

    if label_exprs:
        df = df.with_columns(label_exprs)

    log.info(f"[FUND-TS] Added time-series features to {df.height} rows")
    return df


# Convenience wrapper
def add_timeseries_and_score(df: pl.DataFrame, scorer_fn):
    work = add_timeseries_features(df)
    return scorer_fn(work)


EXPORTS = {
    "fundamentals_timeseries_engine": {
        "add_timeseries_features": add_timeseries_features,
        "add_timeseries_and_score": add_timeseries_and_score,
    }
}
