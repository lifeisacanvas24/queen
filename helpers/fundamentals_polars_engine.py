#!/usr/bin/env python3
# ============================================================
# queen/helpers/fundamentals_polars_engine.py — v4.0 (SAFE AUTO-SCHEMA)
# ------------------------------------------------------------
# Converts fundamentals JSON files to Polars DataFrame
#
# Compatible with scraper v7.0 output format.
#
# Mode: SAFE AUTO-SCHEMA
#   - Builds DF from adapter rows without crashing on mixed types
#   - If any non-numeric string appears, dtype becomes Utf8
#   - Deep tables (_quarters, _ratios, etc.) always Object
#   - Numeric candidates cast with strict=False (bad strings -> null)
#
# Public API:
#   load_all(processed_dir)           - Load all JSONs to DataFrame
#   load_one_processed(dir, symbol)   - Load single symbol
#   to_polars_row(json_dict)          - Convert JSON to row
#   build_df_from_rows(rows)          - Build DF from row dicts
#   build_df_from_all_processed(dir)  - Load all from directory
#
# Usage:
#   from queen.helpers.fundamentals_polars_engine import load_all
#   df = load_all(PATHS['FUNDAMENTALS_PROCESSED'])
# ============================================================
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Union

import polars as pl

# Import adapter
try:
    from queen.helpers.fundamentals_adapter import to_row
except ImportError:
    # Fallback: import from same directory
    from fundamentals_adapter import to_row

# Import settings
try:
    from queen.settings.fundamentals_map import (
        FUNDAMENTALS_ADAPTER_COLUMNS,
        FUNDAMENTALS_METRIC_COLUMNS,
        FUNDAMENTALS_BASE_SCHEMA,
    )
except ImportError:
    FUNDAMENTALS_ADAPTER_COLUMNS = {}
    FUNDAMENTALS_METRIC_COLUMNS = []
    FUNDAMENTALS_BASE_SCHEMA = {}

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

# Try to import schema validator, make optional
try:
    from queen.helpers.fundamentals_schema import FundamentalsModel
    HAS_SCHEMA = True
except ImportError:
    HAS_SCHEMA = False


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _read_json(p: Path) -> Optional[Dict[str, Any]]:
    """Read and parse a JSON file."""
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"[FUND-POLAR] JSON read failed: {p.name}: {e}")
        return None


def _validate_or_fallback(raw: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Try Pydantic validation/coercion if available.
    Fallback to raw dict if validation fails or not available.
    """
    if not HAS_SCHEMA:
        return raw

    try:
        model = FundamentalsModel.model_validate(raw)
        return model.model_dump()
    except Exception as e:
        log.debug(f"[FUND-POLAR] Validation fallback for {source}: {e}")
        return raw


def _is_numeric_like_str(s: str) -> bool:
    """
    Check if string is numeric-like:
      Accepts: "12.3", "-4", "0.08", "1,234", "78.4%"
      Rejects: "TTM", "Sep 2024", "NA", ""
    """
    if s is None:
        return False

    t = s.strip().replace(",", "").replace("%", "")
    if t in {"", "-", "NA", "N/A", "None", "null"}:
        return False

    try:
        float(t)
        return True
    except (ValueError, TypeError):
        return False


def _infer_dtype_for_col(values: List[Any], col: str) -> pl.DataType:
    """
    Infer Polars dtype for a column based on values.

    Rules:
    - Deep cols (starting with _) => Object
    - Any dict/list => Object
    - Any real string (non-numeric) => Utf8
    - Otherwise => Float64
    """
    # Deep columns always Object
    if col.startswith("_"):
        return pl.Object

    saw_text = False
    saw_object = False
    saw_numeric = False

    for v in values:
        if v is None:
            continue

        if isinstance(v, (dict, list)):
            saw_object = True
            break

        if isinstance(v, str):
            if _is_numeric_like_str(v):
                saw_numeric = True
            else:
                saw_text = True
                break

        elif isinstance(v, (int, float)):
            saw_numeric = True

        else:
            saw_object = True
            break

    if saw_object:
        return pl.Object
    if saw_text:
        return pl.Utf8
    if saw_numeric:
        return pl.Float64

    # All nulls -> default to Float64
    return pl.Float64


def _build_safe_schema(rows: List[Dict[str, Any]]) -> Dict[str, pl.DataType]:
    """
    Scan ALL rows to infer safe dtype per column.
    """
    all_cols: Set[str] = set()
    for r in rows:
        all_cols.update(r.keys())

    schema: Dict[str, pl.DataType] = {}
    for c in sorted(all_cols):
        col_vals = [r.get(c) for r in rows]
        schema[c] = _infer_dtype_for_col(col_vals, c)

    # Force identity columns to Utf8
    for idc in ("Symbol", "symbol"):
        if idc in schema:
            schema[idc] = pl.Utf8

    for sc in ("Sector", "sector", "industry", "broad_sector", "company_name"):
        if sc in schema:
            schema[sc] = pl.Utf8

    # Force codes to Utf8
    for code in ("bse_code", "nse_code", "_extracted_at"):
        if code in schema:
            schema[code] = pl.Utf8

    # Force text fields
    for txt in ("about",):
        if txt in schema:
            schema[txt] = pl.Utf8

    return schema


def _ensure_symbol_sector(df: pl.DataFrame) -> pl.DataFrame:
    """Ensure Symbol and Sector columns exist with proper names."""
    # Rename lowercase to titlecase if needed
    if "symbol" in df.columns and "Symbol" not in df.columns:
        df = df.rename({"symbol": "Symbol"})
    if "sector" in df.columns and "Sector" not in df.columns:
        df = df.rename({"sector": "Sector"})
    return df


def _numeric_candidates(df: pl.DataFrame) -> List[str]:
    """
    Get list of columns that should be numeric.

    Includes:
    - Baseline metric columns
    - Adapter baseline columns
    - *_latest, *_holding_latest
    - CAGR keys
    - Slope/Accel/CV keys
    - Z-score columns
    - Known numeric fields
    """
    base = set(FUNDAMENTALS_METRIC_COLUMNS or [])
    base.update(FUNDAMENTALS_ADAPTER_COLUMNS.keys())

    # Known numeric fields
    known_numeric = {
        "market_cap", "current_price", "pe_ratio", "book_value",
        "eps_ttm", "debt_to_equity", "roce_pct", "roe_pct",
        "dividend_yield", "face_value", "week_52_high", "week_52_low",
        "gross_npa_pct", "net_npa_pct", "casa_pct", "car_pct",
        "promoter_pledge_pct", "peers_count",
        "sh_promoters_pct", "sh_fii_pct", "sh_dii_pct", "sh_public_pct", "sh_govt_pct",
        "sales_cagr_10y", "sales_cagr_5y", "sales_cagr_3y", "sales_cagr_ttm",
        "profit_cagr_10y", "profit_cagr_5y", "profit_cagr_3y", "profit_cagr_ttm",
        "price_cagr_10y", "price_cagr_5y", "price_cagr_3y", "price_cagr_1y",
        "roe_10y", "roe_5y", "roe_3y", "roe_last_year",
        "roce_10y", "roce_5y", "roce_3y", "roce_last_year",
        "ratio_debtor_days", "ratio_inventory_days", "ratio_days_payable",
        "ratio_cash_conversion_cycle", "ratio_working_capital_days",
        "interest_coverage",
        "q_sales_latest", "q_net_profit_latest", "q_eps_latest",
        "pl_sales_ttm", "pl_net_profit_ttm",
    }
    base.update(known_numeric)

    out: List[str] = []
    for c in df.columns:
        if c in {"Symbol", "Sector", "symbol", "sector"} or c.startswith("_"):
            continue

        if (
            c in base
            or c.endswith("_latest")
            or c.endswith("_holding_latest")
            or "_cagr_" in c
            or c.endswith("_Slope")
            or c.endswith("_Accel")
            or c.endswith("_CV")
            or c.endswith("_z_sector")
            or c.endswith("_z_global")
            or c.endswith("_pct")
        ):
            out.append(c)

    return out


def _cast_numeric_candidates(df: pl.DataFrame) -> pl.DataFrame:
    """
    Cast numeric candidates to Float64 safely.
    Stray text values become null.
    """
    cands = _numeric_candidates(df)
    if not cands:
        return df

    exprs = []
    for c in cands:
        if c in df.columns:
            # Check if already numeric
            if df.schema.get(c) in (pl.Float64, pl.Float32, pl.Int64, pl.Int32):
                continue
            exprs.append(pl.col(c).cast(pl.Float64, strict=False).alias(c))

    return df.with_columns(exprs) if exprs else df


# ============================================================
# PUBLIC API
# ============================================================

def load_one_processed(
    processed_dir: Union[str, Path],
    symbol: str
) -> Optional[Dict[str, Any]]:
    """
    Load a single symbol's processed JSON.

    Args:
        processed_dir: Path to processed JSON directory
        symbol: Stock symbol (case-insensitive)

    Returns:
        Validated/raw JSON dict, or None if not found
    """
    processed_dir = Path(processed_dir)
    p = processed_dir / f"{symbol.upper()}.json"

    if not p.exists():
        log.warning(f"[FUND-POLAR] File not found: {p}")
        return None

    raw = _read_json(p)
    if not raw:
        return None

    return _validate_or_fallback(raw, p.name)


def to_polars_row(symbol_fund_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a single symbol's JSON to a flat row dict.

    Args:
        symbol_fund_json: Raw JSON dict from scraper

    Returns:
        Flat row dict suitable for DataFrame
    """
    safe = _validate_or_fallback(symbol_fund_json, "inline")
    return to_row(safe)


def build_df_from_rows(rows: Iterable[Dict[str, Any]]) -> pl.DataFrame:
    """
    Build Polars DataFrame from row dicts.

    Args:
        rows: Iterable of flat row dicts

    Returns:
        Polars DataFrame with inferred schema
    """
    rows = list(rows)
    if not rows:
        return pl.DataFrame()

    # Build safe auto-schema
    schema = _build_safe_schema(rows)

    # Create DataFrame
    df = pl.DataFrame(rows, schema=schema, strict=False)
    df = _ensure_symbol_sector(df)

    # Safe numeric cast pass
    df = _cast_numeric_candidates(df)

    return df


def build_df_from_all_processed(processed_dir: Union[str, Path]) -> pl.DataFrame:
    """
    Load all processed JSONs from directory into DataFrame.

    Args:
        processed_dir: Path to processed JSON directory

    Returns:
        Polars DataFrame with all symbols
    """
    processed_dir = Path(processed_dir)

    # Find all JSON files (exclude _checkpoint, _all_symbols)
    files = [
        f for f in sorted(processed_dir.glob("*.json"))
        if not f.name.startswith("_")
    ]

    if not files:
        log.warning(f"[FUND-POLAR] No processed JSONs in {processed_dir}")
        return pl.DataFrame()

    rows: List[Dict[str, Any]] = []
    log.info(f"[FUND-POLAR] Processing {len(files)} fundamental files...")

    success_count = 0
    error_count = 0

    for p in files:
        raw = _read_json(p)
        if not raw:
            error_count += 1
            continue

        safe = _validate_or_fallback(raw, p.name)

        try:
            row = to_row(safe)
            symbol = row.get("Symbol") or row.get("symbol")
            if symbol:
                rows.append(row)
                success_count += 1
            else:
                log.warning(f"[FUND-POLAR] Missing Symbol in {p.name}, skipped")
                error_count += 1
        except Exception as e:
            log.error(f"[FUND-POLAR] Adapter failed for {p.name}: {e}")
            error_count += 1

    if not rows:
        log.warning("[FUND-POLAR] No rows after adapter conversion")
        return pl.DataFrame()

    df = build_df_from_rows(rows)

    log.info(
        f"[FUND-POLAR] Built DataFrame: {df.height} symbols, {len(df.columns)} columns "
        f"(success={success_count}, errors={error_count})"
    )

    return df


# ============================================================
# BACK-COMPAT ALIAS (devcheck/smoke tests expect load_all)
# ============================================================

def load_all(processed_dir: Union[str, Path]) -> pl.DataFrame:
    """
    Alias for build_df_from_all_processed().
    Maintained for backward compatibility.
    """
    return build_df_from_all_processed(processed_dir)


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_column_summary(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Get a summary of columns in the DataFrame.

    Returns:
        Dict with column categories and counts
    """
    cols = df.columns

    summary = {
        "total": len(cols),
        "identity": [c for c in cols if c in ("Symbol", "Sector", "symbol", "sector", "company_name", "industry")],
        "numeric": [c for c in cols if df.schema.get(c) == pl.Float64],
        "text": [c for c in cols if df.schema.get(c) == pl.Utf8],
        "nested": [c for c in cols if c.startswith("_")],
        "shareholding": [c for c in cols if "sh_" in c or "holding" in c],
        "growth": [c for c in cols if "cagr" in c or c.startswith("roe_") or c.startswith("roce_")],
        "quarterly": [c for c in cols if c.startswith("q_")],
        "pl": [c for c in cols if c.startswith("pl_")],
        "ratios": [c for c in cols if c.startswith("ratio_")],
    }

    return summary


def print_df_summary(df: pl.DataFrame) -> None:
    """Print a summary of the DataFrame."""
    summary = get_column_summary(df)

    print("\n" + "="*60)
    print("FUNDAMENTALS DATAFRAME SUMMARY")
    print("="*60)
    print(f"  Rows (symbols): {df.height}")
    print(f"  Total columns: {summary['total']}")
    print(f"  Numeric columns: {len(summary['numeric'])}")
    print(f"  Text columns: {len(summary['text'])}")
    print(f"  Nested tables: {len(summary['nested'])}")
    print()
    print("  Column categories:")
    print(f"    Identity: {summary['identity']}")
    print(f"    Shareholding: {len(summary['shareholding'])} cols")
    print(f"    Growth: {len(summary['growth'])} cols")
    print(f"    Quarterly: {len(summary['quarterly'])} cols")
    print(f"    P&L: {len(summary['pl'])} cols")
    print(f"    Ratios: {len(summary['ratios'])} cols")
    print("="*60)


# ============================================================
# EXPORTS
# ============================================================

EXPORTS = {
    "fundamentals_polars_engine": {
        "load_all": load_all,
        "load_one_processed": load_one_processed,
        "to_polars_row": to_polars_row,
        "build_df_from_rows": build_df_from_rows,
        "build_df_from_all_processed": build_df_from_all_processed,
        "get_column_summary": get_column_summary,
        "print_df_summary": print_df_summary,
    }
}


# ============================================================
# CLI TEST
# ============================================================

if __name__ == "__main__":
    import sys

    # Default to project path or command line arg
    if len(sys.argv) > 1:
        processed_dir = Path(sys.argv[1])
    else:
        # Try project path
        try:
            from queen.settings.settings import PATHS
            processed_dir = PATHS["FUNDAMENTALS_PROCESSED"]
        except ImportError:
            processed_dir = Path("data/fundamentals/processed")

    print(f"\nLoading fundamentals from: {processed_dir}")

    if not processed_dir.exists():
        print(f"Error: Directory not found: {processed_dir}")
        sys.exit(1)

    df = load_all(processed_dir)

    if df.height == 0:
        print("No data loaded!")
        sys.exit(1)

    print_df_summary(df)

    # Show sample data
    key_cols = [
        "Symbol", "Sector", "market_cap", "pe_ratio",
        "roce_pct", "roe_pct", "debt_to_equity", "eps_ttm",
        "sh_promoters_pct", "sh_fii_pct",
        "sales_cagr_5y", "profit_cagr_5y",
    ]

    available_cols = [c for c in key_cols if c in df.columns]

    print("\n📊 Sample Data (first 5 rows):")
    print(df.select(available_cols).head(5))

    # Save test output
    output_path = processed_dir / "_test_dataframe.csv"
    df.select(available_cols).write_csv(output_path)
    print(f"\n✅ Saved test CSV to: {output_path}")
