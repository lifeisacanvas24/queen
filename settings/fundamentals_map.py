#!/usr/bin/env python3
# ============================================================
# queen/settings/fundamentals_map.py — v3.0 (CANONICAL INTERNAL)
# ------------------------------------------------------------
# Canonical snake_case contract across:
#   scraper → adapter → polars → registry → score → gate/tests
#
# Units:
#   • roce_pct / roe_pct / gross_npa_pct / net_npa_pct are PERCENT (0–100)
#   • cagr / growth are DECIMAL (0–1)
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

# ------------------------------------------------------------
# Screener label → internal key mapping (for scraper)
# ------------------------------------------------------------
SCREENER_FIELDS: Dict[str, Dict[str, Any]] = {
    "top_ratios": {
        "Market Cap": "market_cap",
        "Current Price": "current_price",
        "Stock P/E": "pe_ratio",
        "Book Value": "book_value",
        "Dividend Yield": "dividend_yield",
        "ROCE %": "roce_pct",
        "ROE %": "roe_pct",
        "Debt to Equity": "debt_to_equity",
        "EPS (TTM)": "eps_ttm",

        # Banks / NBFC
        "Gross NPA %": "gross_npa_pct",
        "Net NPA %": "net_npa_pct",
        "CASA %": "casa_pct",
    },

    "quarters": {
        "Sales": "q_sales",
        "Operating Profit": "q_op",
        "Net Profit": "q_np",
        "EPS in Rs": "q_eps",
    },

    "profit_loss": {
        "Sales": "pl_sales",
        "Operating Profit": "pl_op",
        "Net Profit": "pl_np",
        "EPS in Rs": "pl_eps",
        "OPM %": "pl_opm_pct",
        "NPM %": "pl_npm_pct",
    },

    "balance_sheet": {
        "Borrowings": "bs_borrowings",
        "Reserves": "bs_reserves",
        "Total Assets": "bs_assets",
        "Deposits": "bs_deposits",
    },

    "cash_flow": {
        "Cash from Operating Activity": "cf_cfo",
        "Cash from Investing Activity": "cf_cfi",
        "Cash from Financing Activity": "cf_cff",
        "Free Cash Flow": "cf_fcf",
    },

    "ratios": {
        "ROCE %": "roce_pct",
        "ROE %": "roe_pct",
        "Debt to Equity": "debt_equity",
        "Interest Coverage": "interest_cover",
        "Gross NPA %": "gross_npa_pct",
        "Net NPA %": "net_npa_pct",
    },

    "growth": {
        "Compounded Sales Growth 10 Yrs": "sales_cagr_10y",
        "Compounded Sales Growth 5 Yrs": "sales_cagr_5y",
        "Compounded Sales Growth 3 Yrs": "sales_cagr_3y",
        "Compounded Sales Growth TTM": "sales_cagr_ttm",

        "Compounded Profit Growth 10 Yrs": "profit_cagr_10y",
        "Compounded Profit Growth 5 Yrs": "profit_cagr_5y",
        "Compounded Profit Growth 3 Yrs": "profit_cagr_3y",
        "Compounded Profit Growth TTM": "profit_cagr_ttm",

        "Return on Equity 3 Yrs": "roe_3y",
        "Return on Equity 5 Yrs": "roe_5y",
        "Return on Equity 10 Yrs": "roe_10y",

        "Return on Capital Employed 3 Yrs": "roce_3y",
        "Return on Capital Employed 5 Yrs": "roce_5y",
        "Return on Capital Employed 10 Yrs": "roce_10y",
    },

    "shareholding": {
        "Promoters": "sh_promoters_pct",
        "FIIs": "sh_fii_pct",
        "DIIs": "sh_dii_pct",
        "Public": "sh_public_pct",
    },
}

# ------------------------------------------------------------
# Baseline schema (minimal, canonical)
# ------------------------------------------------------------
FUNDAMENTALS_BASE_SCHEMA: Dict[str, str] = {
    "Symbol": "Utf8",
    "Sector": "Utf8",
    "market_cap": "Float64",
    "current_price": "Float64",
    "pe_ratio": "Float64",
    "debt_to_equity": "Float64",
    "eps_ttm": "Float64",
    "roce_pct": "Float64",
    "roe_pct": "Float64",
    "gross_npa_pct": "Float64",
    "net_npa_pct": "Float64",
}

# ------------------------------------------------------------
# Adapter-driven scalar columns (canonical)
# ------------------------------------------------------------
FUNDAMENTALS_ADAPTER_COLUMNS: Dict[str, Dict[str, str]] = {
    "market_cap": {"source": "top_ratios.market_cap", "polars": "Float64", "type": "float"},
    "current_price": {"source": "top_ratios.current_price", "polars": "Float64", "type": "float"},
    "pe_ratio": {"source": "top_ratios.pe_ratio", "polars": "Float64", "type": "float"},
    "debt_to_equity": {"source": "top_ratios.debt_to_equity", "polars": "Float64", "type": "float"},
    "eps_ttm": {"source": "top_ratios.eps_ttm", "polars": "Float64", "type": "float"},
    "roce_pct": {"source": "top_ratios.roce_pct", "polars": "Float64", "type": "float"},
    "roe_pct": {"source": "top_ratios.roe_pct", "polars": "Float64", "type": "float"},
    "gross_npa_pct": {"source": "top_ratios.gross_npa_pct", "polars": "Float64", "type": "float"},
    "net_npa_pct": {"source": "top_ratios.net_npa_pct", "polars": "Float64", "type": "float"},
}

# ------------------------------------------------------------
# Baseline metric columns (registry auto-extends)
# ------------------------------------------------------------
FUNDAMENTALS_METRIC_COLUMNS: List[str] = [
    "market_cap",
    "pe_ratio",
    "debt_to_equity",
    "eps_ttm",
    "roce_pct",
    "roe_pct",
    "gross_npa_pct",
    "net_npa_pct",
]

# ------------------------------------------------------------
# Importance map (canonical keys)
# ------------------------------------------------------------
FUNDAMENTALS_IMPORTANCE_MAP: Dict[str, float] = {
    "roce_pct": 2.0,
    "roe_pct": 1.8,
    "debt_to_equity": 1.4,
    "pe_ratio": 1.2,
    "eps_ttm": 1.2,
    "market_cap": 0.6,

    "sales_cagr_10y": 1.2,
    "profit_cagr_10y": 1.2,
    "sales_cagr_5y": 1.0,
    "profit_cagr_5y": 1.0,

    "sh_promoters_pct_holding_latest": 0.8,
    "sh_fii_pct_holding_latest": 0.6,

    "gross_npa_pct": 1.5,
    "net_npa_pct": 1.7,
}

# ------------------------------------------------------------
# Tactical filters (percent units!)
# ------------------------------------------------------------
FUNDAMENTALS_TACTICAL_FILTERS = {
    "MIN_SECTOR_RANK_N": 5,
    "MIN_GLOBAL_RANK_N": 20,

    "MAX_DEBT_EQUITY": 2.0,
    "MAX_GROSS_NPA_PCT": 8.0,   # percent
    "MAX_NET_NPA_PCT": 4.0,     # percent

    "MIN_ROCE_PCT": 10.0,       # percent
    "MIN_ROE_PCT": 10.0,        # percent
    "MIN_EPS_TTM": 0.0,

    "filters": [
        {"col": "roce_pct", "op": ">=", "value": 10.0, "reason": "Low ROCE"},
        {"col": "roe_pct", "op": ">=", "value": 10.0, "reason": "Low ROE"},
        {"col": "debt_to_equity", "op": "<=", "value": 2.0, "reason": "High D/E"},
        {"col": "eps_ttm", "op": ">", "value": 0.0, "reason": "Negative EPS"},
        {"col": "gross_npa_pct", "op": "<=", "value": 8.0, "reason": "High Gross NPA"},
        {"col": "net_npa_pct", "op": "<=", "value": 4.0, "reason": "High Net NPA"},
    ],
}
FUNDAMENTALS_TACTICAL_FILTER_LIST = FUNDAMENTALS_TACTICAL_FILTERS["filters"]

# ------------------------------------------------------------
# PowerScore dimension weights
# ------------------------------------------------------------
POWERSCORE_WEIGHTS: Dict[str, float] = {
    "profitability": 0.18,
    "growth": 0.18,
    "efficiency": 0.12,
    "valuation": 0.10,
    "leverage": 0.10,
    "momentum": 0.12,
    "stability": 0.10,
    "ownership": 0.10,
}

INTRINSIC_BUCKETS = [
    (85, "A"),
    (70, "B"),
    (50, "C"),
    (0, "D"),
]

EXPORTS = {"fundamentals_map": globals()}
