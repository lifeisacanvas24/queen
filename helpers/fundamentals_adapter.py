#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_adapter.py — v4.0 (COMPATIBLE WITH SCRAPER v7.0)
# ------------------------------------------------------------
# Converts scraper JSON output to flat row for Polars DataFrame
#
# Key features:
#   - Handles both flat (v7.0) and nested (legacy) scraper output
#   - Flattened fields at root level take priority
#   - Shareholding, Growth already flattened by scraper v7.0
#   - Maintains backward compatibility with older JSON files
#
# Usage:
#   from queen.helpers.fundamentals_adapter import to_row
#   row = to_row(scraped_json)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Try to import from project, fallback to empty dict
try:
    from queen.settings.fundamentals_map import (
        FUNDAMENTALS_ADAPTER_COLUMNS,
        SCRAPER_OUTPUT_FIELDS,
    )
except ImportError:
    FUNDAMENTALS_ADAPTER_COLUMNS = {}
    SCRAPER_OUTPUT_FIELDS = []


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _deep_get(d: Dict[str, Any], path: List[str]) -> Any:
    """Navigate nested dict by path list."""
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _deep_get_dot(d: Dict[str, Any], dot_path: str) -> Any:
    """Navigate nested dict by dot-separated path string."""
    return _deep_get(d, dot_path.split(".")) if dot_path else None


def _parse_numeric(v: Any) -> Optional[float]:
    """
    Convert value to float, handling:
    - Already numeric: return as-is
    - String with commas: remove commas and parse
    - Dict (time-series): get latest non-null value
    - Invalid: return None
    """
    if v is None:
        return None

    if isinstance(v, (int, float)):
        return float(v)

    if isinstance(v, str):
        s = v.strip().replace(",", "").replace("%", "")
        if not s or s in {"-", "NA", "N/A", "None", "null", ""}:
            return None
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    if isinstance(v, dict):
        # Time-series: get latest non-null value
        return _latest_non_null(v)

    return None


def _latest_non_null(series: Any) -> Optional[float]:
    """Get latest non-null numeric value from a time-series dict."""
    if not isinstance(series, dict):
        return _parse_numeric(series)

    # Iterate in reverse to get latest
    for val in reversed(list(series.values())):
        if val is None:
            continue
        parsed = _parse_numeric(val)
        if parsed is not None:
            return parsed

    return None


def _extract_latest_period(series: Dict[str, Any]) -> Tuple[Optional[str], Optional[float]]:
    """Extract latest period and its value from time-series."""
    if not isinstance(series, dict) or not series:
        return (None, None)

    items = list(series.items())
    for period, val in reversed(items):
        if val is not None:
            parsed = _parse_numeric(val)
            return (period, parsed)

    if items:
        return (items[-1][0], None)
    return (None, None)


def _promote_latest_series(out: Dict[str, Any], tbl: Dict[str, Any], prefix: str = "") -> None:
    """
    For each metric in a table (e.g., quarters), extract the latest value
    and add it to output with _latest suffix.
    """
    if not isinstance(tbl, dict):
        return

    for metric_key, series in tbl.items():
        if metric_key.startswith("_"):
            continue

        latest_val = _latest_non_null(series)
        if latest_val is not None:
            # Clean the key
            clean_key = metric_key.replace("+", "").replace(" ", "_").lower()
            out_key = f"{prefix}{clean_key}_latest" if prefix else f"{clean_key}_latest"
            out[out_key] = latest_val


def _safe_get_list(data: Dict[str, Any], key: str) -> List[Any]:
    """Safely get a list from dict, return empty list if not found or wrong type."""
    val = data.get(key)
    if isinstance(val, list):
        return val
    return []


# ============================================================
# MAIN ADAPTER FUNCTION
# ============================================================

def to_row(m: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a single scraped JSON to a flat row dict.

    Handles both:
    - v7.0 scraper output (flat fields at root)
    - Legacy output (nested under top_ratios, etc.)

    Args:
        m: Raw JSON dict from scraper

    Returns:
        Flat dict suitable for Polars DataFrame row
    """
    out: Dict[str, Any] = {}

    # ─────────────────────────────────────────────────────────
    # 1. IDENTITY FIELDS
    # ─────────────────────────────────────────────────────────
    out["Symbol"] = (m.get("symbol") or "").upper().strip()
    out["symbol"] = out["Symbol"]  # Keep both for compatibility

    # Sector/Industry (v7.0 has these at root)
    out["Sector"] = m.get("sector") or m.get("Sector")
    out["sector"] = out["Sector"]
    out["industry"] = m.get("industry")
    out["broad_sector"] = m.get("broad_sector")
    out["company_name"] = m.get("company_name")
    out["bse_code"] = m.get("bse_code")
    out["nse_code"] = m.get("nse_code")

    # ─────────────────────────────────────────────────────────
    # 2. SCALAR FIELDS FROM ADAPTER COLUMNS MAP
    # ─────────────────────────────────────────────────────────
    for col, spec in (FUNDAMENTALS_ADAPTER_COLUMNS or {}).items():
        src = spec.get("source", "")

        # v7.0: Try root level first (flat structure)
        if col in m:
            out[col] = _parse_numeric(m[col])
        # Legacy: Try nested path
        elif "." in src:
            raw_val = _deep_get_dot(m, src)
            out[col] = _parse_numeric(raw_val)
        elif src and src in m:
            out[col] = _parse_numeric(m[src])

        # If still not found, try source directly
        if out.get(col) is None and src:
            raw_val = m.get(src)
            if raw_val is not None:
                out[col] = _parse_numeric(raw_val)

    # ─────────────────────────────────────────────────────────
    # 3. TOP RATIOS (v7.0 has these at root, legacy has nested)
    # ─────────────────────────────────────────────────────────
    # Direct root-level metrics (v7.0 format)
    root_metrics = [
        "market_cap", "current_price", "pe_ratio", "book_value",
        "dividend_yield", "face_value", "eps_ttm", "debt_to_equity",
        "roce_pct", "roe_pct", "week_52_high", "week_52_low",
        "gross_npa_pct", "net_npa_pct", "casa_pct", "car_pct",
    ]

    for metric in root_metrics:
        if metric in m and out.get(metric) is None:
            out[metric] = _parse_numeric(m[metric])

    # Legacy: Copy from top_ratios if present
    top = m.get("top_ratios") or {}
    if isinstance(top, dict):
        for k, v in top.items():
            if k not in out or out[k] is None:
                out[k] = _parse_numeric(v) if not isinstance(v, (dict, list)) else v

    # Normalize ROCE/ROE naming
    if out.get("roce_pct") is None and "roce" in out:
        out["roce_pct"] = out.get("roce")
    if out.get("roe_pct") is None and "roe" in out:
        out["roe_pct"] = out.get("roe")

    # ─────────────────────────────────────────────────────────
    # 4. SHAREHOLDING (v7.0 flattens to root, legacy nested)
    # ─────────────────────────────────────────────────────────
    # v7.0: Flattened shareholding at root
    sh_fields = [
        "sh_promoters_pct", "sh_fii_pct", "sh_dii_pct",
        "sh_public_pct", "sh_govt_pct", "promoter_pledge_pct"
    ]
    for field in sh_fields:
        if field in m:
            out[field] = _parse_numeric(m[field])

    # Legacy: Extract from nested shareholding
    share = m.get("shareholding") or {}
    out["_shareholding"] = share

    if isinstance(share, dict):
        # Get latest values from quarterly/yearly
        for mode, suffix in [("quarterly", ""), ("yearly", "_yearly")]:
            part = share.get(mode) or {}
            if isinstance(part, dict):
                for key, series in part.items():
                    period, val = _extract_latest_period(series)

                    # Map to standard names
                    key_lower = key.lower()
                    if "promoter" in key_lower:
                        if out.get("sh_promoters_pct") is None and val is not None:
                            out["sh_promoters_pct"] = val
                    elif "fii" in key_lower or "foreign" in key_lower:
                        if out.get("sh_fii_pct") is None and val is not None:
                            out["sh_fii_pct"] = val
                    elif "dii" in key_lower or "domestic" in key_lower:
                        if out.get("sh_dii_pct") is None and val is not None:
                            out["sh_dii_pct"] = val
                    elif "public" in key_lower:
                        if out.get("sh_public_pct") is None and val is not None:
                            out["sh_public_pct"] = val
                    elif "gov" in key_lower:
                        if out.get("sh_govt_pct") is None and val is not None:
                            out["sh_govt_pct"] = val

                    # Also store with original naming
                    if val is not None:
                        out[f"{key}_holding{suffix}_latest"] = val
                    if period:
                        out[f"{key}_holding{suffix}_period"] = period

        # Latest summary (v7.0 format)
        latest = share.get("latest") or {}
        if isinstance(latest, dict):
            for key, val in latest.items():
                parsed = _parse_numeric(val)
                if parsed is not None:
                    out_key = f"sh_{key}_pct"
                    if out.get(out_key) is None:
                        out[out_key] = parsed

        # Pledge data
        pledge = share.get("pledge") or {}
        if isinstance(pledge, dict):
            pledge_pct = pledge.get("promoter_pledge_pct")
            if pledge_pct is not None and out.get("promoter_pledge_pct") is None:
                out["promoter_pledge_pct"] = _parse_numeric(pledge_pct)

    # ─────────────────────────────────────────────────────────
    # 5. GROWTH CAGR (v7.0 flattens to root)
    # ─────────────────────────────────────────────────────────
    growth_fields = [
        "sales_cagr_10y", "sales_cagr_5y", "sales_cagr_3y", "sales_cagr_ttm",
        "profit_cagr_10y", "profit_cagr_5y", "profit_cagr_3y", "profit_cagr_ttm",
        "price_cagr_10y", "price_cagr_5y", "price_cagr_3y", "price_cagr_1y",
        "roe_10y", "roe_5y", "roe_3y", "roe_last_year",
        "roce_10y", "roce_5y", "roce_3y", "roce_last_year",
    ]

    # v7.0: Check root level first
    for field in growth_fields:
        if field in m:
            out[field] = _parse_numeric(m[field])

    # Legacy/nested: Extract from growth dict
    growth = m.get("growth") or {}
    out["_growth"] = growth

    if isinstance(growth, dict):
        for k, v in growth.items():
            if k not in out or out[k] is None:
                out[k] = _parse_numeric(v)

    # ─────────────────────────────────────────────────────────
    # 6. FINANCIAL TABLES (keep nested, promote latest)
    # ─────────────────────────────────────────────────────────
    table_prefix_map = {
        "quarters": "q_",
        "profit_loss": "pl_",
        "balance_sheet": "bs_",
        "cash_flow": "cf_",
        "ratios": "ratio_",
    }

    for tbl_name, prefix in table_prefix_map.items():
        tbl = m.get(tbl_name) or {}

        if isinstance(tbl, dict):
            # Promote latest values with prefix
            _promote_latest_series(out, tbl, prefix)

        # Keep full table for deep analysis
        out[f"_{tbl_name}"] = tbl

    # Also extract specific latest quarterly values (v7.0 format)
    q_latest_fields = [
        "q_sales_latest", "q_net_profit_latest", "q_eps_latest",
        "q_operating_profit_latest"
    ]
    for field in q_latest_fields:
        if field in m and out.get(field) is None:
            out[field] = _parse_numeric(m[field])

    # TTM values
    ttm_fields = ["pl_sales_ttm", "pl_net_profit_ttm", "pl_operating_profit_ttm"]
    for field in ttm_fields:
        if field in m and out.get(field) is None:
            out[field] = _parse_numeric(m[field])

    # Ratio fields from v7.0
    ratio_fields = [
        "ratio_debtor_days", "ratio_inventory_days", "ratio_days_payable",
        "ratio_cash_conversion_cycle", "ratio_working_capital_days",
        "interest_coverage"
    ]
    for field in ratio_fields:
        if field in m and out.get(field) is None:
            out[field] = _parse_numeric(m[field])

    # ─────────────────────────────────────────────────────────
    # 7. TEXT FIELDS
    # ─────────────────────────────────────────────────────────
    out["about"] = m.get("about")
    out["pros"] = _safe_get_list(m, "pros")
    out["cons"] = _safe_get_list(m, "cons")

    # ─────────────────────────────────────────────────────────
    # 8. PEERS (v7.0 format)
    # ─────────────────────────────────────────────────────────
    peers = m.get("peers") or []
    out["_peers"] = peers
    out["peers_count"] = len(peers) if isinstance(peers, list) else 0

    # Extract peer metrics if available
    if isinstance(peers, list) and len(peers) > 0:
        peer_names = []
        for peer in peers[:10]:  # Limit to 10 peers
            if isinstance(peer, dict):
                name = peer.get("name") or peer.get("peer_name")
                if name:
                    peer_names.append(name)
        out["peer_names"] = peer_names

    # ─────────────────────────────────────────────────────────
    # 9. METADATA
    # ─────────────────────────────────────────────────────────
    out["_extracted_at"] = m.get("_extracted_at")

    return out


# ============================================================
# EXPORTS
# ============================================================

EXPORTS = {
    "fundamentals_adapter": {
        "to_row": to_row,
    }
}


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fundamentals_adapter.py <path_to_json>")
        sys.exit(1)

    json_path = sys.argv[1]

    with open(json_path, "r") as f:
        data = json.load(f)

    row = to_row(data)

    print("\n" + "="*60)
    print("ADAPTER OUTPUT")
    print("="*60)

    # Key fields to display
    key_fields = [
        "Symbol", "Sector", "company_name", "industry",
        "market_cap", "current_price", "pe_ratio", "book_value",
        "roce_pct", "roe_pct", "debt_to_equity", "eps_ttm",
        "week_52_high", "week_52_low", "dividend_yield",
        "sh_promoters_pct", "sh_fii_pct", "sh_dii_pct",
        "promoter_pledge_pct",
        "sales_cagr_10y", "sales_cagr_5y", "sales_cagr_3y",
        "profit_cagr_10y", "profit_cagr_5y", "profit_cagr_3y",
        "peers_count",
    ]

    for field in key_fields:
        val = row.get(field)
        if val is not None:
            if isinstance(val, float):
                print(f"  {field:25}: {val:,.2f}")
            else:
                print(f"  {field:25}: {val}")

    print("="*60)
    print(f"\nTotal fields in row: {len(row)}")

    # Show nested table names
    nested = [k for k in row.keys() if k.startswith("_")]
    print(f"Nested tables: {nested}")
