#!/usr/bin/env python3
# ============================================================
# queen/settings/fundamentals_map.py — v4.3 (COMPLETE SYSTEM CONSTANTS)
# ------------------------------------------------------------
# Canonical snake_case contract across the entire fundamentals system:
#   scraper → adapter → polars → registry → score → gate → cli → timeseries → schema
#
# UPDATED to match screener_scraper.py v7.0 output
# Fully integrated with queen.settings.settings
#
# Units:
#   • roce_pct / roe_pct / gross_npa_pct / net_npa_pct are PERCENT (0–100)
#   • cagr / growth are PERCENT (0–100), NOT decimal
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# ------------------------------------------------------------
# Screener label → internal key mapping (for scraper)
# Keys are NORMALIZED (lowercase, no spaces, no special chars)
# This matches the scraper's normalize_key() function
# ------------------------------------------------------------
SCREENER_FIELDS: Dict[str, Dict[str, Any]] = {
    "top_ratios": {
        # Core metrics
        "marketcap": "market_cap",
        "currentprice": "current_price",
        "stockpe": "pe_ratio",
        "pe": "pe_ratio",
        "bookvalue": "book_value",
        "dividendyield": "dividend_yield",
        "roce": "roce_pct",
        "roe": "roe_pct",
        "debttoequity": "debt_to_equity",
        "eps": "eps_ttm",
        "epsttm": "eps_ttm",
        "facevalue": "face_value",
        "highlow": "price_high_low",

        # 52-week range (parsed separately)
        "week52high": "week_52_high",
        "week52low": "week_52_low",

        # Banks / NBFC specific
        "grossnpa": "gross_npa_pct",
        "netnpa": "net_npa_pct",
        "casa": "casa_pct",
        "car": "car_pct",
        "capitaladequacyratio": "car_pct",
        "advances": "advances",
        "deposits": "deposits",
    },

    "quarters": {
        "sales": "q_sales",
        "revenue": "q_sales",
        "operatingprofit": "q_operating_profit",
        "opm": "q_opm_pct",
        "netprofit": "q_net_profit",
        "epsinrs": "q_eps",
        "eps": "q_eps",
    },

    "profit_loss": {
        "sales": "pl_sales",
        "revenue": "pl_sales",
        "operatingprofit": "pl_operating_profit",
        "opm": "pl_opm_pct",
        "npm": "pl_npm_pct",
        "netprofit": "pl_net_profit",
        "epsinrs": "pl_eps",
        "eps": "pl_eps",
        "dividendpayout": "pl_dividend_payout_pct",
    },

    "balance_sheet": {
        "equitycapital": "bs_equity_capital",
        "reserves": "bs_reserves",
        "borrowings": "bs_borrowings",
        "otherliabilities": "bs_other_liabilities",
        "totalliabilities": "bs_total_liabilities",
        "fixedassets": "bs_fixed_assets",
        "cwip": "bs_cwip",
        "investments": "bs_investments",
        "otherassets": "bs_other_assets",
        "totalassets": "bs_total_assets",
        # Bank specific
        "deposits": "bs_deposits",
        "advances": "bs_advances",
    },

    "cash_flow": {
        "cashfromoperatingactivity": "cf_operating",
        "cashfrominvestingactivity": "cf_investing",
        "cashfromfinancingactivity": "cf_financing",
        "netcashflow": "cf_net",
        "freecashflow": "cf_free",
    },

    "ratios": {
        "roce": "ratio_roce_pct",
        "roe": "ratio_roe_pct",
        "debttoequity": "debt_equity",
        "interestcoverage": "interest_coverage",
        "interestcoverageratio": "interest_coverage",
        "grossnpa": "gross_npa_pct",
        "netnpa": "net_npa_pct",
        "debtordays": "ratio_debtor_days",
        "inventorydays": "ratio_inventory_days",
        "dayspayable": "ratio_days_payable",
        "cashconversioncycle": "ratio_cash_conversion_cycle",
        "workingcapitaldays": "ratio_working_capital_days",
    },

    "shareholding": {
        "promoters": "sh_promoters_pct",
        "promoter": "sh_promoters_pct",
        "fiis": "sh_fii_pct",
        "fii": "sh_fii_pct",
        "foreign": "sh_fii_pct",
        "diis": "sh_dii_pct",
        "dii": "sh_dii_pct",
        "domestic": "sh_dii_pct",
        "public": "sh_public_pct",
        "retail": "sh_public_pct",
        "government": "sh_govt_pct",
        "govt": "sh_govt_pct",
    },

    "peers": {
        "name": "peer_name",
        "cmp": "peer_cmp",
        "pe": "peer_pe",
        "marcap": "peer_market_cap",
        "marketcap": "peer_market_cap",
        "divyld": "peer_div_yield",
        "dividendyield": "peer_div_yield",
        "npqtr": "peer_np_qtr",
        "qtrprofit": "peer_np_qtr",
        "salesqtr": "peer_sales_qtr",
        "qtrsales": "peer_sales_qtr",
        "roce": "peer_roce",
        "np": "peer_net_profit",
        "sales": "peer_sales",
    },
}

# ------------------------------------------------------------
# Growth fields mapping (category → period → internal_key)
# Used by scraper for analysis section parsing
# ------------------------------------------------------------
GROWTH_FIELDS: Dict[str, Dict[str, str]] = {
    "compounded sales growth": {
        "10 years": "sales_cagr_10y",
        "5 years": "sales_cagr_5y",
        "3 years": "sales_cagr_3y",
        "ttm": "sales_cagr_ttm",
    },
    "compounded profit growth": {
        "10 years": "profit_cagr_10y",
        "5 years": "profit_cagr_5y",
        "3 years": "profit_cagr_3y",
        "ttm": "profit_cagr_ttm",
    },
    "stock price cagr": {
        "10 years": "price_cagr_10y",
        "5 years": "price_cagr_5y",
        "3 years": "price_cagr_3y",
        "1 year": "price_cagr_1y",
    },
    "return on equity": {
        "10 years": "roe_10y",
        "5 years": "roe_5y",
        "3 years": "roe_3y",
        "last year": "roe_last_year",
    },
    "return on capital employed": {
        "10 years": "roce_10y",
        "5 years": "roce_5y",
        "3 years": "roce_3y",
        "last year": "roce_last_year",
    },
}

# ------------------------------------------------------------
# Peer fields mapping
# Used by scraper for peers table parsing
# ------------------------------------------------------------
PEER_FIELDS: Dict[str, str] = {
    "name": "peer_name",
    "s.no.": "_skip",
    "cmp": "peer_cmp",
    "p/e": "peer_pe",
    "pe": "peer_pe",
    "mar cap": "peer_market_cap",
    "market cap": "peer_market_cap",
    "div yld": "peer_div_yield",
    "dividend yield": "peer_div_yield",
    "np qtr": "peer_np_qtr",
    "qtr profit": "peer_np_qtr",
    "qtr sales": "peer_sales_qtr",
    "sales qtr": "peer_sales_qtr",
    "roce": "peer_roce",
    "roce %": "peer_roce",
}

# ------------------------------------------------------------
# Baseline schema (minimal, canonical) for Polars DataFrame
# ------------------------------------------------------------
FUNDAMENTALS_BASE_SCHEMA: Dict[str, str] = {
    # Identifiers
    "symbol": "Utf8",
    "company_name": "Utf8",
    "sector": "Utf8",
    "industry": "Utf8",
    "broad_sector": "Utf8",
    "bse_code": "Utf8",
    "nse_code": "Utf8",

    # Core metrics
    "market_cap": "Float64",
    "current_price": "Float64",
    "pe_ratio": "Float64",
    "book_value": "Float64",
    "dividend_yield": "Float64",
    "face_value": "Float64",
    "eps_ttm": "Float64",
    "debt_to_equity": "Float64",
    "roce_pct": "Float64",
    "roe_pct": "Float64",

    # 52-week range
    "week_52_high": "Float64",
    "week_52_low": "Float64",

    # Bank/NBFC specific
    "gross_npa_pct": "Float64",
    "net_npa_pct": "Float64",
    "casa_pct": "Float64",
    "car_pct": "Float64",

    # Shareholding (flattened latest)
    "sh_promoters_pct": "Float64",
    "sh_fii_pct": "Float64",
    "sh_dii_pct": "Float64",
    "sh_public_pct": "Float64",
    "sh_govt_pct": "Float64",
    "promoter_pledge_pct": "Float64",

    # Growth CAGR
    "sales_cagr_10y": "Float64",
    "sales_cagr_5y": "Float64",
    "sales_cagr_3y": "Float64",
    "sales_cagr_ttm": "Float64",
    "profit_cagr_10y": "Float64",
    "profit_cagr_5y": "Float64",
    "profit_cagr_3y": "Float64",
    "profit_cagr_ttm": "Float64",
    "price_cagr_10y": "Float64",
    "price_cagr_5y": "Float64",
    "price_cagr_3y": "Float64",
    "price_cagr_1y": "Float64",

    # Historical ROE/ROCE
    "roe_10y": "Float64",
    "roe_5y": "Float64",
    "roe_3y": "Float64",
    "roe_last_year": "Float64",
    "roce_10y": "Float64",
    "roce_5y": "Float64",
    "roce_3y": "Float64",
    "roce_last_year": "Float64",

    # Latest quarterly (flattened)
    "q_sales_latest": "Float64",
    "q_net_profit_latest": "Float64",
    "q_operating_profit_latest": "Float64",
    "q_eps_latest": "Float64",

    # TTM P&L (flattened)
    "pl_sales_ttm": "Float64",
    "pl_net_profit_ttm": "Float64",
    "pl_operating_profit_ttm": "Float64",

    # Ratios (flattened)
    "ratio_debtor_days": "Float64",
    "ratio_inventory_days": "Float64",
    "ratio_days_payable": "Float64",
    "ratio_cash_conversion_cycle": "Float64",
    "ratio_working_capital_days": "Float64",
    "interest_coverage": "Float64",
}

# ------------------------------------------------------------
# Adapter-driven scalar columns (canonical)
# Maps internal keys to their sources in the scraped JSON
# Note: For v7.0 scraper, fields are flattened at top level
# ------------------------------------------------------------
FUNDAMENTALS_ADAPTER_COLUMNS: Dict[str, Dict[str, str]] = {
    # Core metrics (top-level in scraped JSON)
    "market_cap": {"source": "market_cap", "polars": "Float64", "type": "float"},
    "current_price": {"source": "current_price", "polars": "Float64", "type": "float"},
    "pe_ratio": {"source": "pe_ratio", "polars": "Float64", "type": "float"},
    "book_value": {"source": "book_value", "polars": "Float64", "type": "float"},
    "dividend_yield": {"source": "dividend_yield", "polars": "Float64", "type": "float"},
    "face_value": {"source": "face_value", "polars": "Float64", "type": "float"},
    "eps_ttm": {"source": "eps_ttm", "polars": "Float64", "type": "float"},
    "debt_to_equity": {"source": "debt_to_equity", "polars": "Float64", "type": "float"},
    "roce_pct": {"source": "roce_pct", "polars": "Float64", "type": "float"},
    "roe_pct": {"source": "roe_pct", "polars": "Float64", "type": "float"},
    "week_52_high": {"source": "week_52_high", "polars": "Float64", "type": "float"},
    "week_52_low": {"source": "week_52_low", "polars": "Float64", "type": "float"},

    # Bank/NBFC
    "gross_npa_pct": {"source": "gross_npa_pct", "polars": "Float64", "type": "float"},
    "net_npa_pct": {"source": "net_npa_pct", "polars": "Float64", "type": "float"},
    "casa_pct": {"source": "casa_pct", "polars": "Float64", "type": "float"},
    "car_pct": {"source": "car_pct", "polars": "Float64", "type": "float"},

    # Shareholding (flattened by scraper v7.0)
    "sh_promoters_pct": {"source": "sh_promoters_pct", "polars": "Float64", "type": "float"},
    "sh_fii_pct": {"source": "sh_fii_pct", "polars": "Float64", "type": "float"},
    "sh_dii_pct": {"source": "sh_dii_pct", "polars": "Float64", "type": "float"},
    "sh_public_pct": {"source": "sh_public_pct", "polars": "Float64", "type": "float"},
    "sh_govt_pct": {"source": "sh_govt_pct", "polars": "Float64", "type": "float"},
    "promoter_pledge_pct": {"source": "promoter_pledge_pct", "polars": "Float64", "type": "float"},

    # Growth CAGR (flattened by scraper v7.0)
    "sales_cagr_10y": {"source": "sales_cagr_10y", "polars": "Float64", "type": "float"},
    "sales_cagr_5y": {"source": "sales_cagr_5y", "polars": "Float64", "type": "float"},
    "sales_cagr_3y": {"source": "sales_cagr_3y", "polars": "Float64", "type": "float"},
    "sales_cagr_ttm": {"source": "sales_cagr_ttm", "polars": "Float64", "type": "float"},
    "profit_cagr_10y": {"source": "profit_cagr_10y", "polars": "Float64", "type": "float"},
    "profit_cagr_5y": {"source": "profit_cagr_5y", "polars": "Float64", "type": "float"},
    "profit_cagr_3y": {"source": "profit_cagr_3y", "polars": "Float64", "type": "float"},
    "profit_cagr_ttm": {"source": "profit_cagr_ttm", "polars": "Float64", "type": "float"},
    "price_cagr_10y": {"source": "price_cagr_10y", "polars": "Float64", "type": "float"},
    "price_cagr_5y": {"source": "price_cagr_5y", "polars": "Float64", "type": "float"},
    "price_cagr_3y": {"source": "price_cagr_3y", "polars": "Float64", "type": "float"},
    "price_cagr_1y": {"source": "price_cagr_1y", "polars": "Float64", "type": "float"},

    # Historical ROE/ROCE
    "roe_10y": {"source": "roe_10y", "polars": "Float64", "type": "float"},
    "roe_5y": {"source": "roe_5y", "polars": "Float64", "type": "float"},
    "roe_3y": {"source": "roe_3y", "polars": "Float64", "type": "float"},
    "roe_last_year": {"source": "roe_last_year", "polars": "Float64", "type": "float"},
    "roce_10y": {"source": "roce_10y", "polars": "Float64", "type": "float"},
    "roce_5y": {"source": "roce_5y", "polars": "Float64", "type": "float"},
    "roce_3y": {"source": "roce_3y", "polars": "Float64", "type": "float"},
    "roce_last_year": {"source": "roce_last_year", "polars": "Float64", "type": "float"},

    # Ratios (flattened by scraper v7.0)
    "ratio_debtor_days": {"source": "ratio_debtor_days", "polars": "Float64", "type": "float"},
    "ratio_inventory_days": {"source": "ratio_inventory_days", "polars": "Float64", "type": "float"},
    "ratio_days_payable": {"source": "ratio_days_payable", "polars": "Float64", "type": "float"},
    "ratio_cash_conversion_cycle": {"source": "ratio_cash_conversion_cycle", "polars": "Float64", "type": "float"},
    "ratio_working_capital_days": {"source": "ratio_working_capital_days", "polars": "Float64", "type": "float"},
    "interest_coverage": {"source": "interest_coverage", "polars": "Float64", "type": "float"},

    # Latest quarterly (flattened)
    "q_sales_latest": {"source": "q_sales_latest", "polars": "Float64", "type": "float"},
    "q_net_profit_latest": {"source": "q_net_profit_latest", "polars": "Float64", "type": "float"},
    "q_eps_latest": {"source": "q_eps_latest", "polars": "Float64", "type": "float"},

    # TTM (flattened)
    "pl_sales_ttm": {"source": "pl_sales_ttm", "polars": "Float64", "type": "float"},
    "pl_net_profit_ttm": {"source": "pl_net_profit_ttm", "polars": "Float64", "type": "float"},
}

# ------------------------------------------------------------
# Baseline metric columns (registry auto-extends)
# These are the core columns for scoring/ranking
# ------------------------------------------------------------
FUNDAMENTALS_METRIC_COLUMNS: List[str] = [
    # Core valuation/profitability
    "market_cap",
    "pe_ratio",
    "debt_to_equity",
    "eps_ttm",
    "roce_pct",
    "roe_pct",
    "book_value",
    "dividend_yield",

    # 52-week range
    "week_52_high",
    "week_52_low",

    # Bank/NBFC specific
    "gross_npa_pct",
    "net_npa_pct",
    "casa_pct",
    "car_pct",

    # Growth metrics
    "sales_cagr_10y",
    "sales_cagr_5y",
    "sales_cagr_3y",
    "profit_cagr_10y",
    "profit_cagr_5y",
    "profit_cagr_3y",
    "price_cagr_10y",
    "price_cagr_5y",
    "price_cagr_3y",
    "price_cagr_1y",

    # Shareholding
    "sh_promoters_pct",
    "sh_fii_pct",
    "sh_dii_pct",
    "promoter_pledge_pct",

    # Working capital efficiency
    "ratio_debtor_days",
    "ratio_working_capital_days",
    "interest_coverage",

    # Historical performance
    "roe_3y",
    "roe_5y",
    "roce_3y",
    "roce_5y",
]

# ------------------------------------------------------------
# Importance map (canonical keys) for scoring
# Higher weight = more important in PowerScore calculation
# ------------------------------------------------------------
FUNDAMENTALS_IMPORTANCE_MAP: Dict[str, float] = {
    # Profitability (highest weight)
    "roce_pct": 2.0,
    "roe_pct": 1.8,
    "roe_3y": 1.6,
    "roce_3y": 1.6,
    "roe_5y": 1.4,
    "roce_5y": 1.4,

    # Leverage / Safety
    "debt_to_equity": 1.4,
    "interest_coverage": 1.2,
    "promoter_pledge_pct": 1.5,  # High weight - pledge is a risk indicator

    # Valuation
    "pe_ratio": 1.2,
    "eps_ttm": 1.2,
    "book_value": 0.8,

    # Size
    "market_cap": 0.6,

    # Growth (very important)
    "sales_cagr_10y": 1.4,
    "profit_cagr_10y": 1.4,
    "sales_cagr_5y": 1.2,
    "profit_cagr_5y": 1.2,
    "sales_cagr_3y": 1.0,
    "profit_cagr_3y": 1.0,
    "price_cagr_10y": 0.8,
    "price_cagr_5y": 0.8,
    "price_cagr_3y": 0.6,
    "price_cagr_1y": 0.4,

    # Ownership
    "sh_promoters_pct": 0.8,
    "sh_fii_pct": 0.6,
    "sh_dii_pct": 0.4,

    # Bank/NBFC specific (higher weight for banks)
    "gross_npa_pct": 1.5,
    "net_npa_pct": 1.7,
    "casa_pct": 1.0,
    "car_pct": 1.2,

    # Efficiency
    "ratio_debtor_days": 0.6,
    "ratio_working_capital_days": 0.6,

    # Dividend
    "dividend_yield": 0.4,
}

# ------------------------------------------------------------
# Tactical filters (percent units!)
# Used for pre-filtering before detailed scoring
# ------------------------------------------------------------
FUNDAMENTALS_TACTICAL_FILTERS = {
    "MIN_SECTOR_RANK_N": 5,
    "MIN_GLOBAL_RANK_N": 20,

    # Debt filters
    "MAX_DEBT_EQUITY": 5.0,  # Increased from 3.0

    # NPA filters (for banks)
    "MAX_GROSS_NPA_PCT": 15.0,   # Increased from 10.0
    "MAX_NET_NPA_PCT": 10.0,     # Increased from 6.0

    # Pledge filter (NEW)
    "MAX_PROMOTER_PLEDGE_PCT": 75.0,  # Increased from 60.0

    # Profitability filters
    "MIN_ROCE_PCT": 0.0,       # Decreased from 5.0
    "MIN_ROE_PCT": 0.0,        # Decreased from 5.0
    "MIN_EPS_TTM": 0.0,

    # Growth filters
    "MIN_SALES_CAGR_3Y": -20.0,   # Decreased from 0.0
    "MIN_PROFIT_CAGR_3Y": -30.0,  # Decreased from 0.0

    # Filter list for programmatic application
    "filters": [
        {"col": "roce_pct", "op": ">=", "value": 0.0, "reason": "Low ROCE"},
        {"col": "roe_pct", "op": ">=", "value": 0.0, "reason": "Low ROE"},
        {"col": "debt_to_equity", "op": "<=", "value": 5.0, "reason": "High D/E"},
        {"col": "eps_ttm", "op": ">", "value": 0.0, "reason": "Negative EPS"},
        {"col": "gross_npa_pct", "op": "<=", "value": 15.0, "reason": "High Gross NPA"},
        {"col": "net_npa_pct", "op": "<=", "value": 10.0, "reason": "High Net NPA"},
        {"col": "promoter_pledge_pct", "op": "<=", "value": 75.0, "reason": "High Promoter Pledge"},
        {"col": "sales_cagr_3y", "op": ">=", "value": -20.0, "reason": "Low Sales Growth"},
        {"col": "profit_cagr_3y", "op": ">=", "value": -30.0, "reason": "Low Profit Growth"},
    ],
}
FUNDAMENTALS_TACTICAL_FILTER_LIST = FUNDAMENTALS_TACTICAL_FILTERS["filters"]

# ------------------------------------------------------------
# PowerScore dimension weights
# Used for multi-dimensional scoring
# ------------------------------------------------------------
POWERSCORE_WEIGHTS: Dict[str, float] = {
    "profitability": 0.18,   # ROCE, ROE, margins
    "growth": 0.18,          # Sales/Profit CAGR
    "efficiency": 0.12,      # Working capital, debtor days
    "valuation": 0.10,       # P/E, P/B
    "leverage": 0.10,        # Debt/Equity, interest coverage
    "momentum": 0.12,        # Price CAGR
    "stability": 0.10,       # Historical ROE/ROCE consistency
    "ownership": 0.10,       # Promoter/FII/DII holdings, pledge
}

# PowerScore dimension -> metric mapping
POWERSCORE_DIMENSION_METRICS: Dict[str, List[str]] = {
    "profitability": ["roce_pct", "roe_pct", "roe_3y", "roce_3y"],
    "growth": ["sales_cagr_10y", "sales_cagr_5y", "sales_cagr_3y",
               "profit_cagr_10y", "profit_cagr_5y", "profit_cagr_3y"],
    "efficiency": ["ratio_debtor_days", "ratio_working_capital_days"],
    "valuation": ["pe_ratio", "book_value", "dividend_yield"],
    "leverage": ["debt_to_equity", "interest_coverage"],
    "momentum": ["price_cagr_10y", "price_cagr_5y", "price_cagr_3y", "price_cagr_1y"],
    "stability": ["roe_10y", "roe_5y", "roce_10y", "roce_5y"],
    "ownership": ["sh_promoters_pct", "sh_fii_pct", "sh_dii_pct", "promoter_pledge_pct"],
}

# ------------------------------------------------------------
# Intrinsic value buckets for grading
# ------------------------------------------------------------
INTRINSIC_BUCKETS = [
    (60, "A"),   # Excellent
    (52, "B"),   # Good
    (45, "C"),   # Average
    (0, "D"),    # Below Average
]

# ------------------------------------------------------------
# Sector-specific metric adjustments
# Some metrics matter more/less for certain sectors
# ------------------------------------------------------------
SECTOR_METRIC_ADJUSTMENTS: Dict[str, Dict[str, float]] = {
    "Banking": {
        "gross_npa_pct": 2.0,
        "net_npa_pct": 2.0,
        "casa_pct": 1.5,
        "car_pct": 1.5,
        "debt_to_equity": 0.1,  # Banks have high leverage by nature
    },
    "Financial Services": {
        "gross_npa_pct": 2.0,
        "net_npa_pct": 2.0,
        "debt_to_equity": 0.5,
    },
    "NBFC": {
        "gross_npa_pct": 2.0,
        "net_npa_pct": 2.0,
        "debt_to_equity": 0.5,
    },
    "Information Technology": {
        "debt_to_equity": 0.5,  # IT companies usually have low debt
        "roce_pct": 1.5,
        "roe_pct": 1.5,
    },
    "IT Services": {
        "debt_to_equity": 0.5,
        "roce_pct": 1.5,
        "roe_pct": 1.5,
    },
    "Pharmaceuticals": {
        "sales_cagr_5y": 1.2,
        "profit_cagr_5y": 1.2,
    },
    "Oil, Gas & Consumable Fuels": {
        "debt_to_equity": 0.8,  # Capital intensive
    },
    "Metals & Mining": {
        "debt_to_equity": 0.8,
    },
}

# ------------------------------------------------------------
# CLI Display Groups (for fundamentals_cli.py)
# ------------------------------------------------------------
CLI_DISPLAY_GROUPS: Dict[str, List[Tuple[str, str, str]]] = {
    "key_metrics": [
        ("Market Cap", "market_cap", "Cr"),
        ("Current Price", "current_price", "₹"),
        ("P/E Ratio", "pe_ratio", ""),
        ("Book Value", "book_value", "₹"),
        ("EPS (TTM)", "eps_ttm", "₹"),
        ("ROCE", "roce_pct", "%"),
        ("ROE", "roe_pct", "%"),
        ("Debt/Equity", "debt_to_equity", ""),
        ("Dividend Yield", "dividend_yield", "%"),
        ("Face Value", "face_value", "₹"),
        ("52W High", "week_52_high", "₹"),
        ("52W Low", "week_52_low", "₹"),
    ],
    "bank_metrics": [
        ("Gross NPA", "gross_npa_pct", "%"),
        ("Net NPA", "net_npa_pct", "%"),
        ("CASA", "casa_pct", "%"),
        ("CAR", "car_pct", "%"),
    ],
}

CLI_SHAREHOLDING_FIELDS: List[Tuple[str, str]] = [
    ("Promoters", "sh_promoters_pct"),
    ("FII", "sh_fii_pct"),
    ("DII", "sh_dii_pct"),
    ("Public", "sh_public_pct"),
    ("Government", "sh_govt_pct"),
    ("Pledge", "promoter_pledge_pct"),
]

CLI_GROWTH_FIELDS: List[Tuple[str, str]] = [
    ("Sales 10Y", "sales_cagr_10y"),
    ("Sales 5Y", "sales_cagr_5y"),
    ("Sales 3Y", "sales_cagr_3y"),
    ("Profit 10Y", "profit_cagr_10y"),
    ("Profit 5Y", "profit_cagr_5y"),
    ("Profit 3Y", "profit_cagr_3y"),
    ("Price 10Y", "price_cagr_10y"),
    ("Price 5Y", "price_cagr_5y"),
    ("Price 3Y", "price_cagr_3y"),
]

# ------------------------------------------------------------
# PowerScore Normalization Ranges (for fundamentals_score_engine.py)
# ------------------------------------------------------------
POWERSCORE_NORMALIZATION_RANGES: Dict[str, Tuple[float, float]] = {
    "roce_pct": (0, 50),
    "roe_pct": (0, 50),
    "sales_cagr_5y": (-20, 30),
    "profit_cagr_5y": (-20, 30),
    "price_cagr_5y": (-50, 50),
    "debt_to_equity": (0, 2),
    "interest_coverage": (1, 10),
    "dividend_yield": (0, 5),
    "promoter_pledge_pct": (0, 100),
    "sh_promoters_pct": (0, 75),
    "sh_fii_pct": (0, 30),
}

# ------------------------------------------------------------
# Export Column Groups (for fundamentals_cli.py and fundamentals_gate.py)
# ------------------------------------------------------------
EXPORT_COLUMN_GROUPS: Dict[str, List[str]] = {
    "scoring": ["Symbol", "Sector", "PowerScore", "Intrinsic_Bucket", "Fundamental_Pass"],
    "comparison": [
        "Symbol", "Sector", "market_cap", "pe_ratio", "roce_pct", "roe_pct",
        "debt_to_equity", "eps_ttm", "sh_promoters_pct",
        "sales_cagr_5y", "profit_cagr_5y",
    ],
    "sector": ["Symbol", "PowerScore", "Intrinsic_Bucket", "roce_pct", "roe_pct", "market_cap"],
    "gate_overlay": [
        "Fundamental_Pass", "Fundamental_Fail_Reasons", "Intrinsic_Bucket",
        "Intrinsic_Score", "PowerScore", "PowerScore_v1",
    ],
}

# ------------------------------------------------------------
# Boost Maps (for fundamentals_gate.py)
# ------------------------------------------------------------
BOOST_MAPS: Dict[str, Dict[str, float]] = {
    "default": {"A": 1.5, "B": 1.2, "C": 1.0, "D": 0.8},
    "aggressive": {"A": 1.8, "B": 1.3, "C": 0.9, "D": 0.6},
    "conservative": {"A": 1.3, "B": 1.1, "C": 1.0, "D": 0.9},
}

# ------------------------------------------------------------
# Trend Column Definitions (for fundamentals_gate.py)
# ------------------------------------------------------------
TREND_COLUMNS: List[str] = [
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

# ------------------------------------------------------------
# Timeseries Metric Candidates (for fundamentals_timeseries_engine.py)
# ------------------------------------------------------------
TIMESERIES_METRIC_CANDIDATES: Dict[str, List[str]] = {
    "Q_SALES_CANDIDATES": ["Sales", "Sales+", "Revenue", "Total Revenue", "q_sales"],
    "Q_PROFIT_CANDIDATES": ["Net Profit", "Net Profit+", "PAT", "q_np", "q_net_profit"],
    "Q_EPS_CANDIDATES": ["EPS in Rs", "EPS", "q_eps"],
    "Q_OPM_CANDIDATES": ["OPM %", "OPM", "Operating Margin", "q_opm_pct"],
    "PL_SALES_CANDIDATES": ["Sales", "Sales+", "Revenue", "pl_sales"],
    "PL_PROFIT_CANDIDATES": ["Net Profit", "Net Profit+", "PAT", "pl_np", "pl_net_profit"],
    "PL_EPS_CANDIDATES": ["EPS in Rs", "EPS", "pl_eps"],
    "PL_OPM_CANDIDATES": ["OPM %", "OPM", "pl_opm_pct"],
    "ROCE_CANDIDATES": ["ROCE %", "ROCE", "roce_pct", "ratio_roce_pct"],
    "ROE_CANDIDATES": ["ROE %", "ROE", "roe_pct", "ratio_roe_pct"],
    "GROSS_NPA_CANDIDATES": ["Gross NPA %", "Gross NPA", "gross_npa_pct"],
    "NET_NPA_CANDIDATES": ["Net NPA %", "Net NPA", "net_npa_pct"],
    "DEBTOR_DAYS_CANDIDATES": ["Debtor Days", "Debtors Days", "ratio_debtor_days"],
    "WORKING_CAPITAL_CANDIDATES": ["Working Capital Days", "ratio_working_capital_days"],
    "BS_BORROWINGS_CANDIDATES": ["Borrowings", "Borrowings+", "bs_borrowings"],
    "BS_RESERVES_CANDIDATES": ["Reserves", "bs_reserves"],
    "BS_DEPOSITS_CANDIDATES": ["Deposits", "bs_deposits"],
    "BS_ASSETS_CANDIDATES": ["Total Assets", "bs_assets", "bs_total_assets"],
}

# ------------------------------------------------------------
# All fields that the scraper outputs (for validation)
# ------------------------------------------------------------
SCRAPER_OUTPUT_FIELDS: List[str] = [
    # Identifiers
    "symbol",
    "company_name",
    "sector",
    "industry",
    "broad_sector",
    "bse_code",
    "nse_code",

    # Core metrics
    "market_cap",
    "current_price",
    "pe_ratio",
    "book_value",
    "dividend_yield",
    "face_value",
    "eps_ttm",
    "debt_to_equity",
    "roce_pct",
    "roe_pct",
    "week_52_high",
    "week_52_low",

    # Bank/NBFC
    "gross_npa_pct",
    "net_npa_pct",
    "casa_pct",
    "car_pct",

    # Shareholding (flattened)
    "sh_promoters_pct",
    "sh_fii_pct",
    "sh_dii_pct",
    "sh_public_pct",
    "sh_govt_pct",
    "promoter_pledge_pct",

    # Growth (flattened)
    "sales_cagr_10y",
    "sales_cagr_5y",
    "sales_cagr_3y",
    "sales_cagr_ttm",
    "profit_cagr_10y",
    "profit_cagr_5y",
    "profit_cagr_3y",
    "profit_cagr_ttm",
    "price_cagr_10y",
    "price_cagr_5y",
    "price_cagr_3y",
    "price_cagr_1y",
    "roe_10y",
    "roe_5y",
    "roe_3y",
    "roe_last_year",
    "roce_10y",
    "roce_5y",
    "roce_3y",
    "roce_last_year",

    # Ratios (flattened)
    "ratio_debtor_days",
    "ratio_inventory_days",
    "ratio_days_payable",
    "ratio_cash_conversion_cycle",
    "ratio_working_capital_days",
    "interest_coverage",

    # Latest quarterly
    "q_sales_latest",
    "q_net_profit_latest",
    "q_eps_latest",

    # TTM
    "pl_sales_ttm",
    "pl_net_profit_ttm",

    # Text
    "about",
    "pros",
    "cons",

    # Nested (kept for detailed access)
    "quarters",
    "profit_loss",
    "balance_sheet",
    "cash_flow",
    "ratios",
    "growth",
    "shareholding",
    "peers",

    # Metadata
    "_extracted_at",
]

# ------------------------------------------------------------
# Export configuration
# ------------------------------------------------------------
EXPORTS = {
    "fundamentals_map": {
        "SCREENER_FIELDS": SCREENER_FIELDS,
        "GROWTH_FIELDS": GROWTH_FIELDS,
        "PEER_FIELDS": PEER_FIELDS,
        "FUNDAMENTALS_BASE_SCHEMA": FUNDAMENTALS_BASE_SCHEMA,
        "FUNDAMENTALS_ADAPTER_COLUMNS": FUNDAMENTALS_ADAPTER_COLUMNS,
        "FUNDAMENTALS_METRIC_COLUMNS": FUNDAMENTALS_METRIC_COLUMNS,
        "FUNDAMENTALS_IMPORTANCE_MAP": FUNDAMENTALS_IMPORTANCE_MAP,
        "FUNDAMENTALS_TACTICAL_FILTERS": FUNDAMENTALS_TACTICAL_FILTERS,
        "FUNDAMENTALS_TACTICAL_FILTER_LIST": FUNDAMENTALS_TACTICAL_FILTER_LIST,
        "POWERSCORE_WEIGHTS": POWERSCORE_WEIGHTS,
        "POWERSCORE_DIMENSION_METRICS": POWERSCORE_DIMENSION_METRICS,
        "INTRINSIC_BUCKETS": INTRINSIC_BUCKETS,
        "SECTOR_METRIC_ADJUSTMENTS": SECTOR_METRIC_ADJUSTMENTS,
        "CLI_DISPLAY_GROUPS": CLI_DISPLAY_GROUPS,
        "CLI_SHAREHOLDING_FIELDS": CLI_SHAREHOLDING_FIELDS,
        "CLI_GROWTH_FIELDS": CLI_GROWTH_FIELDS,
        "POWERSCORE_NORMALIZATION_RANGES": POWERSCORE_NORMALIZATION_RANGES,
        "EXPORT_COLUMN_GROUPS": EXPORT_COLUMN_GROUPS,
        "BOOST_MAPS": BOOST_MAPS,
        "TREND_COLUMNS": TREND_COLUMNS,
        "TIMESERIES_METRIC_CANDIDATES": TIMESERIES_METRIC_CANDIDATES,
        "SCRAPER_OUTPUT_FIELDS": SCRAPER_OUTPUT_FIELDS,
    }
}



# For backwards compatibility
__all__ = [
    "SCREENER_FIELDS",
    "GROWTH_FIELDS",
    "PEER_FIELDS",
    "FUNDAMENTALS_BASE_SCHEMA",
    "FUNDAMENTALS_ADAPTER_COLUMNS",
    "FUNDAMENTALS_METRIC_COLUMNS",
    "FUNDAMENTALS_IMPORTANCE_MAP",
    "FUNDAMENTALS_TACTICAL_FILTERS",
    "FUNDAMENTALS_TACTICAL_FILTER_LIST",
    "POWERSCORE_WEIGHTS",
    "POWERSCORE_DIMENSION_METRICS",
    "INTRINSIC_BUCKETS",
    "SECTOR_METRIC_ADJUSTMENTS",
    "CLI_DISPLAY_GROUPS",
    "CLI_SHAREHOLDING_FIELDS",
    "CLI_GROWTH_FIELDS",
    "POWERSCORE_NORMALIZATION_RANGES",
    "EXPORT_COLUMN_GROUPS",
    "BOOST_MAPS",
    "TREND_COLUMNS",
    "TIMESERIES_METRIC_CANDIDATES",
    "SCRAPER_OUTPUT_FIELDS",
    "EXPORTS",
]
