#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_schema.py — v4.0 (COMPATIBLE WITH SCRAPER v7.0)
# ------------------------------------------------------------
# Pydantic v2 model for processed fundamentals JSON
#
# Handles both:
#   - v7.0 scraper output (flat fields at root)
#   - Legacy output (nested under top_ratios, etc.)
#
# Features:
#   - Automatic type coercion (strings to floats)
#   - Handles Indian number formats (commas, Cr, Lakh)
#   - Validates time-series data structures
#   - Extra fields allowed for forward compatibility
#
# Usage:
#   from queen.helpers.fundamentals_schema import FundamentalsModel
#   model = FundamentalsModel.model_validate(raw_json)
#   clean_data = model.model_dump()
# ============================================================
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ============================================================
# TYPE ALIASES
# ============================================================

Number = Union[int, float]
MaybeNumber = Optional[Number]
TimeSeries = Dict[str, MaybeNumber]  # e.g., {"Mar 2024": 123.45, "Mar 2023": 100.0}
TableSeries = Dict[str, TimeSeries]  # e.g., {"Sales": {"Mar 2024": 123.45}}


# ============================================================
# VALUE COERCION HELPERS
# ============================================================

# Regex for cleaning non-numeric characters
_CLEAN_RE = re.compile(r"[₹,]")
_UNIT_RE = re.compile(r"(Cr\.?|Crore|Lakh|L|%)\s*$", re.IGNORECASE)


def _clean_string(x: Any) -> str:
    """Clean string for numeric parsing."""
    if x is None:
        return ""
    return str(x).strip()


def _coerce_float(x: Any) -> MaybeNumber:
    """Coerce value to float, handling:
    - Already numeric: return as-is
    - Strings with commas, currency symbols: clean and parse
    - Units like Cr, Lakh, %: handle appropriately
    - Invalid: return None
    """
    if x is None:
        return None

    if isinstance(x, (int, float)):
        return float(x)

    s = _clean_string(x)
    if not s or s in {"-", "NA", "N/A", "None", "null", ""}:
        return None

    # Remove currency symbols and commas
    s = _CLEAN_RE.sub("", s).strip()

    # Handle units
    multiplier = 1.0
    low = s.lower()

    # Check for Crore
    if "cr" in low:
        s = re.sub(r"cr\.?|crore", "", s, flags=re.IGNORECASE).strip()
        # Note: We keep values in Crores as-is (no multiplier)
        # since that's the standard unit in Indian finance

    # Check for Lakh
    elif "lakh" in low or s.endswith("L"):
        s = re.sub(r"lakh|l$", "", s, flags=re.IGNORECASE).strip()
        multiplier = 0.01  # Convert Lakh to Crore

    # Check for percentage (but don't multiply - keep as percentage)
    if s.endswith("%"):
        s = s[:-1].strip()
        # Keep percentage as-is (e.g., 78.4% -> 78.4)

    try:
        return float(s) * multiplier
    except (ValueError, TypeError):
        return None


def _coerce_dict_values(d: Dict[str, Any]) -> Dict[str, MaybeNumber]:
    """Coerce all values in a dict to floats."""
    if not isinstance(d, dict):
        return {}
    return {str(k): _coerce_float(v) for k, v in d.items()}


def _coerce_table_series(d: Dict[str, Any]) -> TableSeries:
    """Coerce a table series (dict of dicts) to proper types.

    Example input:
        {"Sales": {"Mar 2024": "1,234", "Mar 2023": "1,000"}}

    Example output:
        {"Sales": {"Mar 2024": 1234.0, "Mar 2023": 1000.0}}
    """
    if not isinstance(d, dict):
        return {}

    out: TableSeries = {}
    for row_key, series in d.items():
        if not isinstance(series, dict):
            continue
        out[str(row_key)] = {str(p): _coerce_float(x) for p, x in series.items()}

    return out


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ShareholdingData(BaseModel):
    """Shareholding data structure."""

    model_config = ConfigDict(extra="allow")

    quarterly: TableSeries = Field(default_factory=dict)
    yearly: TableSeries = Field(default_factory=dict)
    latest: Dict[str, MaybeNumber] = Field(default_factory=dict)
    pledge: Dict[str, MaybeNumber] = Field(default_factory=dict)

    @field_validator("quarterly", "yearly", mode="before")
    @classmethod
    def _norm_table_series(cls, v: Any) -> TableSeries:
        return _coerce_table_series(v)

    @field_validator("latest", "pledge", mode="before")
    @classmethod
    def _norm_flat_dict(cls, v: Any) -> Dict[str, MaybeNumber]:
        return _coerce_dict_values(v)


class PeerData(BaseModel):
    """Single peer data."""

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    symbol: Optional[str] = None
    peer_cmp: MaybeNumber = None
    peer_pe: MaybeNumber = None
    peer_market_cap: MaybeNumber = None
    peer_div_yield: MaybeNumber = None
    peer_np_qtr: MaybeNumber = None
    peer_sales_qtr: MaybeNumber = None
    peer_roce: MaybeNumber = None


class FundamentalsModel(BaseModel):
    """Complete fundamentals data model.

    Compatible with both v7.0 (flat) and legacy (nested) scraper output.
    """

    model_config = ConfigDict(extra="allow")

    # ──────────────────────────────────────────────────────────
    # REQUIRED METADATA
    # ──────────────────────────────────────────────────────────
    symbol: str

    # ──────────────────────────────────────────────────────────
    # OPTIONAL METADATA
    # ──────────────────────────────────────────────────────────
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    broad_sector: Optional[str] = None
    bse_code: Optional[str] = None
    nse_code: Optional[str] = None
    last_updated_date: Optional[str] = None

    # ──────────────────────────────────────────────────────────
    # CORE METRICS (v7.0 flat format)
    # ──────────────────────────────────────────────────────────
    market_cap: MaybeNumber = None
    current_price: MaybeNumber = None
    pe_ratio: MaybeNumber = None
    book_value: MaybeNumber = None
    dividend_yield: MaybeNumber = None
    face_value: MaybeNumber = None
    eps_ttm: MaybeNumber = None
    debt_to_equity: MaybeNumber = None
    roce_pct: MaybeNumber = None
    roe_pct: MaybeNumber = None
    week_52_high: MaybeNumber = None
    week_52_low: MaybeNumber = None

    # Bank/NBFC specific
    gross_npa_pct: MaybeNumber = None
    net_npa_pct: MaybeNumber = None
    casa_pct: MaybeNumber = None
    car_pct: MaybeNumber = None

    # ──────────────────────────────────────────────────────────
    # SHAREHOLDING (v7.0 flat format)
    # ──────────────────────────────────────────────────────────
    sh_promoters_pct: MaybeNumber = None
    sh_fii_pct: MaybeNumber = None
    sh_dii_pct: MaybeNumber = None
    sh_public_pct: MaybeNumber = None
    sh_govt_pct: MaybeNumber = None
    promoter_pledge_pct: MaybeNumber = None

    # ──────────────────────────────────────────────────────────
    # GROWTH CAGR (v7.0 flat format)
    # ──────────────────────────────────────────────────────────
    sales_cagr_10y: MaybeNumber = None
    sales_cagr_5y: MaybeNumber = None
    sales_cagr_3y: MaybeNumber = None
    sales_cagr_ttm: MaybeNumber = None
    profit_cagr_10y: MaybeNumber = None
    profit_cagr_5y: MaybeNumber = None
    profit_cagr_3y: MaybeNumber = None
    profit_cagr_ttm: MaybeNumber = None
    price_cagr_10y: MaybeNumber = None
    price_cagr_5y: MaybeNumber = None
    price_cagr_3y: MaybeNumber = None
    price_cagr_1y: MaybeNumber = None

    # Historical ROE/ROCE
    roe_10y: MaybeNumber = None
    roe_5y: MaybeNumber = None
    roe_3y: MaybeNumber = None
    roe_last_year: MaybeNumber = None
    roce_10y: MaybeNumber = None
    roce_5y: MaybeNumber = None
    roce_3y: MaybeNumber = None
    roce_last_year: MaybeNumber = None

    # ──────────────────────────────────────────────────────────
    # LATEST VALUES (v7.0 flat format)
    # ──────────────────────────────────────────────────────────
    q_sales_latest: MaybeNumber = None
    q_net_profit_latest: MaybeNumber = None
    q_eps_latest: MaybeNumber = None
    pl_sales_ttm: MaybeNumber = None
    pl_net_profit_ttm: MaybeNumber = None

    # ──────────────────────────────────────────────────────────
    # LEGACY NESTED STRUCTURES (for backward compatibility)
    # ──────────────────────────────────────────────────────────
    top_ratios: Dict[str, MaybeNumber] = Field(default_factory=dict)

    # ──────────────────────────────────────────────────────────
    # FINANCIAL TABLES (TIME SERIES)
    # ──────────────────────────────────────────────────────────
    quarters: TableSeries = Field(default_factory=dict)
    profit_loss: TableSeries = Field(default_factory=dict)
    balance_sheet: TableSeries = Field(default_factory=dict)
    cash_flow: TableSeries = Field(default_factory=dict)
    ratios: Dict[str, MaybeNumber] = Field(default_factory=dict)
    growth: Dict[str, MaybeNumber] = Field(default_factory=dict)

    # ──────────────────────────────────────────────────────────
    # SHAREHOLDING (nested structure)
    # ──────────────────────────────────────────────────────────
    shareholding: Dict[str, Any] = Field(default_factory=dict)

    # ──────────────────────────────────────────────────────────
    # PEERS
    # ──────────────────────────────────────────────────────────
    peers: List[Dict[str, Any]] = Field(default_factory=list)

    # ──────────────────────────────────────────────────────────
    # TEXT DATA
    # ──────────────────────────────────────────────────────────
    about: Optional[str] = None
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    key_points: List[str] = Field(default_factory=list)

    # ──────────────────────────────────────────────────────────
    # METADATA
    # ──────────────────────────────────────────────────────────
    _extracted_at: Optional[str] = None

    # ══════════════════════════════════════════════════════════
    # VALIDATORS
    # ══════════════════════════════════════════════════════════

    @field_validator(
        "market_cap", "current_price", "pe_ratio", "book_value",
        "dividend_yield", "face_value", "eps_ttm", "debt_to_equity",
        "roce_pct", "roe_pct", "week_52_high", "week_52_low",
        "gross_npa_pct", "net_npa_pct", "casa_pct", "car_pct",
        "sh_promoters_pct", "sh_fii_pct", "sh_dii_pct", "sh_public_pct",
        "sh_govt_pct", "promoter_pledge_pct",
        "sales_cagr_10y", "sales_cagr_5y", "sales_cagr_3y", "sales_cagr_ttm",
        "profit_cagr_10y", "profit_cagr_5y", "profit_cagr_3y", "profit_cagr_ttm",
        "price_cagr_10y", "price_cagr_5y", "price_cagr_3y", "price_cagr_1y",
        "roe_10y", "roe_5y", "roe_3y", "roe_last_year",
        "roce_10y", "roce_5y", "roce_3y", "roce_last_year",
        "q_sales_latest", "q_net_profit_latest", "q_eps_latest",
        "pl_sales_ttm", "pl_net_profit_ttm",
        mode="before"
    )
    @classmethod
    def _coerce_numeric(cls, v: Any) -> MaybeNumber:
        return _coerce_float(v)

    @field_validator("top_ratios", "ratios", "growth", mode="before")
    @classmethod
    def _norm_flat_metrics(cls, v: Any) -> Dict[str, MaybeNumber]:
        return _coerce_dict_values(v)

    @field_validator(
        "quarters", "profit_loss", "balance_sheet", "cash_flow",
        mode="before"
    )
    @classmethod
    def _norm_table_series(cls, v: Any) -> TableSeries:
        return _coerce_table_series(v)

    @field_validator("shareholding", mode="before")
    @classmethod
    def _norm_shareholding(cls, v: Any) -> Dict[str, Any]:
        """Normalize shareholding structure."""
        if not isinstance(v, dict):
            return {}

        out: Dict[str, Any] = {}

        # Handle quarterly/yearly as TableSeries
        for key in ["quarterly", "yearly"]:
            if key in v and isinstance(v[key], dict):
                out[key] = _coerce_table_series(v[key])

        # Handle latest/pledge as flat dicts
        for key in ["latest", "pledge"]:
            if key in v and isinstance(v[key], dict):
                out[key] = _coerce_dict_values(v[key])

        return out

    @field_validator("peers", mode="before")
    @classmethod
    def _norm_peers(cls, v: Any) -> List[Dict[str, Any]]:
        """Normalize peers list."""
        if not isinstance(v, list):
            return []

        out = []
        for peer in v:
            if isinstance(peer, dict):
                # Coerce numeric fields
                normalized = {}
                for k, val in peer.items():
                    if k in ["name", "symbol"]:
                        normalized[k] = str(val) if val else None
                    elif k.startswith("peer_"):
                        normalized[k] = _coerce_float(val)
                    else:
                        normalized[k] = val
                out.append(normalized)

        return out

    @field_validator("pros", "cons", "key_points", mode="before")
    @classmethod
    def _norm_string_list(cls, v: Any) -> List[str]:
        """Ensure these are lists of strings."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return []

    @model_validator(mode="after")
    def _fill_from_nested(self) -> FundamentalsModel:
        """Fill flat fields from nested structures if not already set.
        This provides backward compatibility with legacy scraper output.
        """
        # Fill from top_ratios
        if self.top_ratios:
            if self.market_cap is None:
                self.market_cap = self.top_ratios.get("market_cap")
            if self.current_price is None:
                self.current_price = self.top_ratios.get("current_price")
            if self.pe_ratio is None:
                self.pe_ratio = self.top_ratios.get("pe_ratio")
            if self.roce_pct is None:
                self.roce_pct = self.top_ratios.get("roce_pct") or self.top_ratios.get("roce")
            if self.roe_pct is None:
                self.roe_pct = self.top_ratios.get("roe_pct") or self.top_ratios.get("roe")
            if self.eps_ttm is None:
                self.eps_ttm = self.top_ratios.get("eps_ttm")
            if self.debt_to_equity is None:
                self.debt_to_equity = self.top_ratios.get("debt_to_equity")

        # Fill from growth
        if self.growth:
            if self.sales_cagr_10y is None:
                self.sales_cagr_10y = self.growth.get("sales_cagr_10y")
            if self.sales_cagr_5y is None:
                self.sales_cagr_5y = self.growth.get("sales_cagr_5y")
            if self.profit_cagr_10y is None:
                self.profit_cagr_10y = self.growth.get("profit_cagr_10y")
            if self.profit_cagr_5y is None:
                self.profit_cagr_5y = self.growth.get("profit_cagr_5y")

        return self


# ============================================================
# VALIDATION FUNCTION
# ============================================================

def validate_fundamentals(raw: Dict[str, Any]) -> FundamentalsModel:
    """Validate and normalize raw fundamentals JSON.

    Args:
        raw: Raw JSON dict from scraper

    Returns:
        Validated FundamentalsModel instance

    """
    return FundamentalsModel.model_validate(raw)


def validate_fundamentals_safe(raw: Dict[str, Any]) -> Optional[FundamentalsModel]:
    """Safely validate fundamentals, returning None on error.

    Args:
        raw: Raw JSON dict from scraper

    Returns:
        FundamentalsModel or None if validation fails

    """
    try:
        return FundamentalsModel.model_validate(raw)
    except Exception:
        return None


# ============================================================
# EXPORTS
# ============================================================

EXPORTS = {
    "fundamentals_schema": {
        "FundamentalsModel": FundamentalsModel,
        "ShareholdingData": ShareholdingData,
        "PeerData": PeerData,
        "validate_fundamentals": validate_fundamentals,
        "validate_fundamentals_safe": validate_fundamentals_safe,
    }
}


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fundamentals_schema.py <path_to_json>")
        sys.exit(1)

    json_path = sys.argv[1]

    with open(json_path) as f:
        raw = json.load(f)

    try:
        model = FundamentalsModel.model_validate(raw)

        print("\n" + "="*60)
        print("VALIDATION SUCCESS")
        print("="*60)
        print(f"  Symbol: {model.symbol}")
        print(f"  Sector: {model.sector}")
        print(f"  Market Cap: {model.market_cap}")
        print(f"  P/E Ratio: {model.pe_ratio}")
        print(f"  ROCE %: {model.roce_pct}")
        print(f"  ROE %: {model.roe_pct}")
        print(f"  Debt/Equity: {model.debt_to_equity}")
        print(f"  EPS TTM: {model.eps_ttm}")
        print(f"  52W High: {model.week_52_high}")
        print(f"  52W Low: {model.week_52_low}")
        print()
        print(f"  Promoters %: {model.sh_promoters_pct}")
        print(f"  FII %: {model.sh_fii_pct}")
        print(f"  DII %: {model.sh_dii_pct}")
        print(f"  Pledge %: {model.promoter_pledge_pct}")
        print()
        print(f"  Sales CAGR 5Y: {model.sales_cagr_5y}")
        print(f"  Profit CAGR 5Y: {model.profit_cagr_5y}")
        print()
        print(f"  Quarters: {len(model.quarters)} rows")
        print(f"  P&L: {len(model.profit_loss)} rows")
        print(f"  Balance Sheet: {len(model.balance_sheet)} rows")
        print(f"  Peers: {len(model.peers)} companies")
        print("="*60)

    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        sys.exit(1)
