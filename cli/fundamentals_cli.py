#!/usr/bin/env python3
# ============================================================
# queen/cli/fundamentals_cli.py — v2.2 (FIXED CONSTANTS USAGE + IMPORTS)
# ------------------------------------------------------------
# CLI for fundamentals operations:
#   - View fundamentals for a symbol
#   - Run scoring pipeline
#   - Compare multiple symbols
#   - Export to CSV
#   - Show sector rankings
#   - Run full analysis pipeline
#
# Usage:
#   python -m queen.cli.fundamentals_cli show TCS
#   python -m queen.cli.fundamentals_cli score --all
#   python -m queen.cli.fundamentals_cli compare TCS INFY WIPRO
#   python -m queen.cli.fundamentals_cli export --output fundamentals.csv
#   python -m queen.cli.fundamentals_cli sector "Information Technology"
#   python -m queen.cli.fundamentals_cli pipeline --symbols TCS RELIANCE
# ============================================================
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import polars as pl
# Add this import at the top of fundamentals_cli.py with other imports
from bs4 import BeautifulSoup as BS
# ============================================================
# PROJECT INTEGRATION (CENTRALIZED IMPORTS)
# ============================================================

_PROJECT_INTEGRATED = False

try:
    from queen.settings.settings import PATHS
    _PROJECT_INTEGRATED = True

    # Set default paths from project
    DEFAULT_PROCESSED_DIR = PATHS.get("FUNDAMENTALS_PROCESSED", Path("data/fundamentals/processed"))
    DEFAULT_RAW_DIR = PATHS.get("FUNDAMENTALS_RAW", Path("data/fundamentals/raw"))

except ImportError as e:
    # Standalone mode
    print(f"Warning: Could not import settings: {e}", file=sys.stderr)
    DEFAULT_PROCESSED_DIR = Path("data/fundamentals/processed")
    DEFAULT_RAW_DIR = Path("data/fundamentals/raw")

# Try to import fundamentals_map for centralized constants
try:
    from queen.settings.fundamentals_map import (
        CLI_DISPLAY_GROUPS,
        CLI_SHAREHOLDING_FIELDS,
        CLI_GROWTH_FIELDS,
        EXPORT_COLUMN_GROUPS,
        FUNDAMENTALS_METRIC_COLUMNS,
    )
    HAS_FUNDAMENTALS_MAP = True
except ImportError:
    HAS_FUNDAMENTALS_MAP = False
    # Fallback defaults
    CLI_DISPLAY_GROUPS = {
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
    CLI_SHAREHOLDING_FIELDS = [
        ("Promoters", "sh_promoters_pct"),
        ("FII", "sh_fii_pct"),
        ("DII", "sh_dii_pct"),
        ("Public", "sh_public_pct"),
        ("Government", "sh_govt_pct"),
        ("Pledge", "promoter_pledge_pct"),
    ]
    CLI_GROWTH_FIELDS = [
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
    EXPORT_COLUMN_GROUPS = {
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
    FUNDAMENTALS_METRIC_COLUMNS = []

# Try to import helpers with error handling
HAS_POLARS_ENGINE = False
HAS_SCORE_ENGINE = False
HAS_TIMESERIES = False
HAS_GATE = False

try:
    from queen.helpers.fundamentals_polars_engine import (
        load_all,
        load_one_processed,
        build_df_from_rows,
    )
    from queen.helpers.fundamentals_adapter import to_row
    HAS_POLARS_ENGINE = True
except ImportError as e:
    print(f"Warning: Could not import polars engine: {e}", file=sys.stderr)

# Try to import scoring
try:
    from queen.technicals.fundamentals_score_engine import score_and_filter
    HAS_SCORE_ENGINE = True
except ImportError as e:
    print(f"Warning: Could not import score engine: {e}", file=sys.stderr)

# Try to import timeseries
try:
    from queen.helpers.fundamentals_timeseries_engine import add_timeseries_features
    HAS_TIMESERIES = True
except ImportError as e:
    print(f"Warning: Could not import timeseries engine: {e}", file=sys.stderr)

# Try to import gate
try:
    from queen.technicals.fundamentals_gate import apply_comprehensive_gate
    HAS_GATE = True
except ImportError as e:
    print(f"Warning: Could not import gate: {e}", file=sys.stderr)

# Try to import logger
try:
    from queen.helpers.logger import log
except ImportError:
    class _FallbackLog:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARNING] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
        def debug(self, msg): print(f"[DEBUG] {msg}")
        def success(self, msg): print(f"[SUCCESS] {msg}")
    log = _FallbackLog()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _format_number(val: Any, decimals: int = 2) -> str:
    """Format a number for display."""
    if val is None:
        return "-"
    try:
        num = float(val)
        if abs(num) >= 1e9:
            return f"{num/1e9:,.{decimals}f}B"
        elif abs(num) >= 1e7:
            return f"{num/1e7:,.{decimals}f}Cr"
        elif abs(num) >= 1e5:
            return f"{num/1e5:,.{decimals}f}L"
        else:
            return f"{num:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(val)


def _format_percent(val: Any, decimals: int = 2) -> str:
    """Format a percentage for display."""
    if val is None:
        return "-"
    try:
        return f"{float(val):.{decimals}f}%"
    except (ValueError, TypeError):
        return str(val)


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load a JSON file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"Failed to load {path}: {e}")
        return None


def _get_processed_dir(args) -> Path:
    """Get processed directory from args or default."""
    if hasattr(args, 'processed_dir') and args.processed_dir:
        return Path(args.processed_dir)
    return DEFAULT_PROCESSED_DIR


def _print_divider(char: str = "=", width: int = 70):
    """Print a divider line."""
    print(char * width)


def _get_column_group(group_name: str) -> List[str]:
    """Get column group from centralized constants."""
    return EXPORT_COLUMN_GROUPS.get(group_name, [])


def _filter_existing_columns(df: pl.DataFrame, columns: List[str]) -> List[str]:
    """Filter column list to only those that exist in DataFrame."""
    return [col for col in columns if col in df.columns]

def fix_pe_in_existing_data(processed_dir: Path):
    """Fix PE ratio in existing JSON files."""
    import json
    from pathlib import Path

    for json_file in processed_dir.glob("*.json"):
        if json_file.name.startswith("_"):
            continue

        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            # Skip if PE already exists
            if data.get("pe_ratio"):
                continue

            # Try to calculate PE from price and EPS
            if data.get("current_price") and data.get("eps_ttm"):
                try:
                    price = float(data["current_price"])
                    eps = float(data["eps_ttm"])
                    if eps > 0:
                        data["pe_ratio"] = round(price / eps, 2)

                        # Save back to file
                        with open(json_file, "w") as f:
                            json.dump(data, f, indent=2)

                        print(f"Fixed PE for {json_file.stem}: {data['pe_ratio']}")
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            print(f"Error fixing {json_file}: {e}")

def cmd_fix_pe(args):
    """Fix PE ratio in existing data."""
    processed_dir = _get_processed_dir(args)

    if not processed_dir.exists():
        log.error(f"Processed directory not found: {processed_dir}")
        return 1

    fix_pe_in_existing_data(processed_dir)
    return 0
# ============================================================
# COMMAND: show
# ============================================================

def cmd_show(args):
    """Show fundamentals for a single symbol."""
    symbol = args.symbol.upper().strip()
    processed_dir = _get_processed_dir(args)

    json_path = processed_dir / f"{symbol}.json"

    if not json_path.exists():
        log.error(f"No data found for {symbol} at {json_path}")
        print(f"\n❌ No fundamentals data for {symbol}")
        print(f"   Expected file: {json_path}")
        print(f"\n   Run: python -m queen.fetchers.fundamentals_scraper --symbol {symbol}")
        return 1

    data = _load_json(json_path)
    if not data:
        return 1

    # Print header
    _print_divider()
    print(f"  📊 FUNDAMENTALS: {symbol}")
    _print_divider()

    # Company Info
    print(f"\n  🏢 COMPANY INFO:")
    print(f"    Name          : {data.get('company_name', '-')}")
    print(f"    Sector        : {data.get('sector', '-')}")
    print(f"    Industry      : {data.get('industry', '-')}")
    print(f"    BSE Code      : {data.get('bse_code', '-')}")

    # Key Metrics from centralized constants
    print(f"\n  💰 KEY METRICS:")
    key_metrics = CLI_DISPLAY_GROUPS.get("key_metrics", [])
    for label, key, unit in key_metrics:
        val = data.get(key)
        if val is not None:
            if unit == "%":
                display = _format_percent(val)
            elif unit in ("Cr", "₹"):
                display = f"{unit} {_format_number(val)}"
            else:
                display = _format_number(val)
            print(f"    {label:18}: {display}")

    # Bank-specific metrics from centralized constants
    if data.get("gross_npa_pct") is not None or data.get("net_npa_pct") is not None:
        print(f"\n  🏦 BANK METRICS:")
        bank_metrics = CLI_DISPLAY_GROUPS.get("bank_metrics", [])
        for label, key, unit in bank_metrics:
            val = data.get(key)
            if val is not None:
                print(f"    {label:18}: {_format_percent(val)}")

    # Shareholding from centralized constants
    print(f"\n  👥 SHAREHOLDING:")
    for label, key in CLI_SHAREHOLDING_FIELDS:
        val = data.get(key)
        if val is not None:
            print(f"    {label:18}: {_format_percent(val)}")

    # Growth from centralized constants
    print(f"\n  📈 GROWTH (CAGR):")
    has_growth = False
    for label, key in CLI_GROWTH_FIELDS:
        val = data.get(key)
        if val is not None:
            print(f"    {label:18}: {_format_percent(val)}")
            has_growth = True

    if not has_growth:
        print("    (No growth data available)")

    # Peers
    peers = data.get("peers", [])
    if peers:
        print(f"\n  🏢 PEERS ({len(peers)} companies):")
        for i, peer in enumerate(peers[:5], 1):
            name = peer.get("name", "?")
            pe = peer.get("peer_pe", "-")
            print(f"    {i}. {name[:30]:30} P/E: {pe}")
        if len(peers) > 5:
            print(f"    ... and {len(peers) - 5} more")

    # Pros/Cons
    if data.get("pros"):
        print(f"\n  ✅ PROS:")
        for pro in data["pros"][:3]:
            print(f"    • {pro[:70]}")

    if data.get("cons"):
        print(f"\n  ⚠️ CONS:")
        for con in data["cons"][:3]:
            print(f"    • {con[:70]}")

    # Data sections available
    sections = []
    for sec in ["quarters", "profit_loss", "balance_sheet", "cash_flow", "ratios", "shareholding", "growth"]:
        if data.get(sec):
            sections.append(sec)
    print(f"\n  📁 Data Sections: {', '.join(sections)}")

    # Metadata
    extracted = data.get("_extracted_at", "-")
    print(f"\n  ⏱️ Extracted: {extracted}")

    _print_divider()

    return 0


# ============================================================
# COMMAND: score
# ============================================================

def cmd_score(args):
    """Run scoring pipeline on fundamentals data."""
    if not HAS_POLARS_ENGINE:
        log.error("fundamentals_polars_engine not available")
        return 1

    if not HAS_SCORE_ENGINE:
        log.error("fundamentals_score_engine not available")
        return 1

    processed_dir = _get_processed_dir(args)

    if not processed_dir.exists():
        log.error(f"Processed directory not found: {processed_dir}")
        return 1

    # Load all data
    log.info(f"Loading fundamentals from {processed_dir}...")
    df = load_all(processed_dir)

    if df.is_empty():
        log.error("No data loaded")
        return 1

    log.info(f"Loaded {df.height} symbols")

    # Add timeseries features if available
    if HAS_TIMESERIES:
        log.info("Adding time-series features...")
        df = add_timeseries_features(df)

    # Run scoring
    log.info("Running scoring pipeline...")
    df = score_and_filter(df)

    # Apply gate if available
    if HAS_GATE and args.gate:
        log.info("Applying comprehensive gate...")
        df = apply_comprehensive_gate(df)

    # Filter by symbol if specified
    if hasattr(args, 'symbol') and args.symbol:
        symbol = args.symbol.upper().strip()
        df = df.filter(pl.col("Symbol") == symbol)

    # Sort by PowerScore
    if "PowerScore" in df.columns:
        df = df.sort("PowerScore", descending=True)

    # Select display columns from centralized constants
    display_cols = _get_column_group("scoring")

    if "Global_Rank" in df.columns:
        # Insert Global_Rank at position 3 if in scoring group
        if len(display_cols) > 2:
            display_cols.insert(3, "Global_Rank")
        else:
            display_cols.append("Global_Rank")

    if "Gate_Pass" in df.columns:
        display_cols.append("Gate_Pass")

    # Filter to existing columns
    available_cols = _filter_existing_columns(df, display_cols)

    # Print results
    _print_divider()
    print(f"  📊 FUNDAMENTALS SCORING RESULTS")
    passed_count = df.filter(pl.col('Fundamental_Pass')).height if 'Fundamental_Pass' in df.columns else 'N/A'
    print(f"  Symbols: {df.height} | Passed: {passed_count}")
    _print_divider()

    # Limit output
    limit = args.limit if hasattr(args, 'limit') and args.limit else 20

    print(df.select(available_cols).head(limit))

    if df.height > limit:
        print(f"\n  ... showing top {limit} of {df.height} symbols")

    # Summary stats
    if "PowerScore" in df.columns:
        ps_stats = df.select([
            pl.col("PowerScore").mean().alias("mean"),
            pl.col("PowerScore").std().alias("std"),
            pl.col("PowerScore").min().alias("min"),
            pl.col("PowerScore").max().alias("max"),
        ]).row(0, named=True)

        print(f"\n  📈 PowerScore Stats:")
        print(f"    Mean: {ps_stats['mean']:.1f} | Std: {ps_stats['std']:.1f} | Range: {ps_stats['min']:.1f} - {ps_stats['max']:.1f}")

    # Bucket distribution (FIXED DEPRECATION WARNING)
    if "Intrinsic_Bucket" in df.columns:
        print(f"\n  🎯 Bucket Distribution:")
        # FIXED: Changed pl.count() to pl.len()
        bucket_counts = df.group_by("Intrinsic_Bucket").agg(pl.len().alias("count")).sort("Intrinsic_Bucket")
        for row in bucket_counts.iter_rows(named=True):
            print(f"    {row['Intrinsic_Bucket']}: {row['count']} symbols")

    _print_divider()

    return 0


# ============================================================
# COMMAND: compare
# ============================================================

def cmd_compare(args):
    """Compare multiple symbols side by side."""
    if not HAS_POLARS_ENGINE:
        log.error("fundamentals_polars_engine not available")
        return 1

    symbols = [s.upper().strip() for s in args.symbols]
    processed_dir = _get_processed_dir(args)

    # Load all data
    df = load_all(processed_dir)

    if df.is_empty():
        log.error("No data loaded")
        return 1

    # Run scoring if available
    if HAS_SCORE_ENGINE:
        if HAS_TIMESERIES:
            df = add_timeseries_features(df)
        df = score_and_filter(df)

    # Filter to requested symbols
    df = df.filter(pl.col("Symbol").is_in(symbols))

    if df.is_empty():
        log.error(f"None of the symbols found: {symbols}")
        return 1

    # Display columns for comparison from centralized constants
    compare_cols = _get_column_group("comparison")

    if "PowerScore" in df.columns:
        compare_cols.insert(2, "PowerScore")

    if "Intrinsic_Bucket" in df.columns:
        compare_cols.insert(3, "Intrinsic_Bucket")

    available = _filter_existing_columns(df, compare_cols)

    _print_divider()
    print(f"  📊 COMPARISON: {', '.join(symbols)}")
    _print_divider()

    print(df.select(available))

    _print_divider()

    return 0


# ============================================================
# COMMAND: sector
# ============================================================

def cmd_sector(args):
    """Show sector rankings."""
    if not HAS_POLARS_ENGINE:
        log.error("fundamentals_polars_engine not available")
        return 1

    processed_dir = _get_processed_dir(args)

    # Load all data
    df = load_all(processed_dir)

    if df.is_empty():
        log.error("No data loaded")
        return 1

    # Run scoring if available
    if HAS_SCORE_ENGINE:
        if HAS_TIMESERIES:
            df = add_timeseries_features(df)
        df = score_and_filter(df)

    sector_col = "Sector" if "Sector" in df.columns else "sector"

    # Filter by sector if specified
    if args.sector_name:
        sector_name = args.sector_name
        df = df.filter(pl.col(sector_col).str.contains(sector_name, literal=False))

        if df.is_empty():
            log.error(f"No symbols found in sector matching: {sector_name}")
            return 1

        _print_divider()
        print(f"  📊 SECTOR: {sector_name}")
        print(f"  Symbols: {df.height}")
        _print_divider()

        # Sort by PowerScore
        if "PowerScore" in df.columns:
            df = df.sort("PowerScore", descending=True)

        # Use sector columns from centralized constants
        display_cols = _get_column_group("sector")
        available = _filter_existing_columns(df, display_cols)

        print(df.select(available).head(20))
    else:
        # Show sector summary
        _print_divider()
        print(f"  📊 SECTOR SUMMARY")
        _print_divider()

        # FIXED: Changed pl.count() to pl.len()
        agg_exprs = [pl.len().alias("count")]

        if "PowerScore" in df.columns:
            agg_exprs.append(pl.col("PowerScore").mean().alias("avg_powerscore"))
        if "roce_pct" in df.columns:
            agg_exprs.append(pl.col("roce_pct").mean().alias("avg_roce"))
        if "market_cap" in df.columns:
            agg_exprs.append(pl.col("market_cap").sum().alias("total_mcap"))

        sector_df = df.group_by(sector_col).agg(agg_exprs).sort("count", descending=True)

        print(sector_df.head(20))

    _print_divider()

    return 0


# ============================================================
# COMMAND: export
# ============================================================

def cmd_export(args):
    """Export fundamentals data to CSV."""
    if not HAS_POLARS_ENGINE:
        log.error("fundamentals_polars_engine not available")
        return 1

    processed_dir = _get_processed_dir(args)
    output_path = Path(args.output)

    # Load all data
    df = load_all(processed_dir)

    if df.is_empty():
        log.error("No data loaded")
        return 1

    # Run scoring if requested
    if args.scored and HAS_SCORE_ENGINE:
        if HAS_TIMESERIES:
            df = add_timeseries_features(df)
        df = score_and_filter(df)

    # Drop nested columns for CSV export
    drop_cols = [c for c in df.columns if c.startswith("_")]
    if drop_cols:
        df = df.drop(drop_cols)

    # Also drop list columns
    for col in df.columns:
        if df[col].dtype == pl.List:
            df = df.drop(col)

    # Write CSV
    df.write_csv(output_path)

    log.success(f"Exported {df.height} symbols to {output_path}")
    print(f"\n✅ Exported {df.height} symbols with {len(df.columns)} columns to {output_path}")

    return 0


# ============================================================
# COMMAND: pipeline
# ============================================================

def cmd_pipeline(args):
    """Run full fundamentals pipeline (scrape + score + gate)."""

    # Check for scraper
    try:
        from queen.fetchers.fundamentals_scraper import ThreadedFundamentalsScraper
        HAS_SCRAPER = True
    except ImportError:
        HAS_SCRAPER = False

    if not HAS_SCRAPER:
        log.error("fundamentals_scraper not available")
        return 1

    if not HAS_POLARS_ENGINE or not HAS_SCORE_ENGINE:
        log.error("Required modules not available")
        return 1

    symbols = [s.upper().strip() for s in args.symbols]

    if not symbols:
        log.error("No symbols provided")
        return 1

    _print_divider()
    print(f"  🚀 FULL PIPELINE: {len(symbols)} symbols")
    _print_divider()

    # Step 1: Scrape
    print(f"\n  📥 Step 1: Scraping...")
    scraper = ThreadedFundamentalsScraper(max_workers=args.workers)

    if len(symbols) > 3:
        results = scraper.scrape_parallel(symbols, save=True)
    else:
        results = scraper.scrape_sequential(symbols, save=True)

    success_count = sum(1 for d in results.values() if d.get("market_cap"))
    print(f"     Scraped: {success_count}/{len(symbols)}")

    # Step 2: Load
    print(f"\n  📂 Step 2: Loading...")
    processed_dir = _get_processed_dir(args)
    df = load_all(processed_dir)
    print(f"     Loaded: {df.height} symbols")

    # Step 3: Timeseries
    if HAS_TIMESERIES:
        print(f"\n  📈 Step 3: Adding time-series features...")
        df = add_timeseries_features(df)
        trend_cols = [c for c in df.columns if "Slope" in c or "Momentum" in c]
        print(f"     Added: {len(trend_cols)} trend columns")

    # Step 4: Score
    print(f"\n  🎯 Step 4: Scoring...")
    df = score_and_filter(df)
    passed = df.filter(pl.col("Fundamental_Pass")).height if "Fundamental_Pass" in df.columns else df.height
    print(f"     Passed: {passed}/{df.height}")

    # Step 5: Gate
    if HAS_GATE:
        print(f"\n  🚪 Step 5: Gating...")
        df = apply_comprehensive_gate(df)
        gated = df.filter(pl.col("Gate_Pass")).height if "Gate_Pass" in df.columns else df.height
        print(f"     Gated: {gated}/{df.height}")

    # Show results
    print(f"\n  📊 RESULTS:")

    # Use scoring columns from centralized constants
    display_cols = _get_column_group("scoring")
    if "Gate_Pass" in df.columns:
        display_cols.append("Gate_Pass")

    available = _filter_existing_columns(df, display_cols)

    # Filter to requested symbols
    df = df.filter(pl.col("Symbol").is_in(symbols))

    if "PowerScore" in df.columns:
        df = df.sort("PowerScore", descending=True)

    print(df.select(available))

    _print_divider()

    return 0


# ============================================================
# COMMAND: list
# ============================================================

def cmd_list(args):
    """List all available symbols."""
    processed_dir = _get_processed_dir(args)

    if not processed_dir.exists():
        log.error(f"Directory not found: {processed_dir}")
        return 1

    # Find all JSON files
    files = [f for f in processed_dir.glob("*.json") if not f.name.startswith("_")]

    if not files:
        print(f"\n❌ No fundamentals data found in {processed_dir}")
        return 1

    symbols = sorted([f.stem for f in files])

    _print_divider()
    print(f"  📋 AVAILABLE SYMBOLS ({len(symbols)})")
    _print_divider()

    # Print in columns
    cols = 5
    for i in range(0, len(symbols), cols):
        row = symbols[i:i+cols]
        print("  " + "  ".join(f"{s:12}" for s in row))

    _print_divider()

    return 0

def cmd_inspect(args):
    """Inspect raw HTML for a symbol."""
    symbol = args.symbol.upper()

    # Try to load from existing raw HTML file
    raw_file = PATHS["FUNDAMENTALS_RAW"] / f"{symbol}.html"

    if raw_file.exists():
        print(f"Loading existing HTML from {raw_file}")
        html_content = raw_file.read_text(encoding="utf-8")
    else:
        print(f"No existing HTML file found for {symbol} at {raw_file}")
        return

    # Parse with BeautifulSoup
    soup = BS(html_content, "lxml")

    # Find top ratios
    top_ratios_ul = soup.find("ul", id="top-ratios")
    if top_ratios_ul:
        print("\nTop Ratios:")
        for i, li in enumerate(top_ratios_ul.find_all("li")):
            text = li.get_text(separator=" | ", strip=True)
            print(f"  {i+1}. {text}")

            # Extract label and value separately
            name_span = li.find("span", class_="name")
            number_span = li.find("span", class_="number")

            if name_span:
                label = name_span.get_text(strip=True)
                print(f"    Label: '{label}'")
            else:
                print(f"    No label span found")

            if number_span:
                value = number_span.get_text(strip=True)
                print(f"    Value: '{value}'")
            else:
                print(f"    No number span found")
    else:
        print("\nNo top-ratios found")

    # Also show the raw HTML structure for top ratios
    print("\nRaw HTML structure for top-ratios:")
    top_ratios_section = soup.find("ul", id="top-ratios")
    if top_ratios_section:
        html_str = str(top_ratios_section)
        # Limit output to first 1000 characters to avoid flooding console
        if len(html_str) > 1000:
            html_str = html_str[:1000] + "..."
        print(html_str)

def cmd_debug(args):
    """Debug fundamentals data for specific symbols."""
    symbols = args.symbols if args.symbols else []

    # Load data
    df = load_all(PATHS["FUNDAMENTALS_PROCESSED"])

    # Add time-series features
    df = add_timeseries_features(df)

    # Run scoring pipeline
    df = score_and_filter(df)

    # Filter to requested symbols
    if symbols:
        df = df.filter(pl.col("Symbol").is_in(symbols))

    # Show key metrics
    key_cols = [
        "Symbol", "Sector", "roce_pct", "roe_pct", "debt_to_equity",
        "pe_ratio", "eps_ttm", "sales_cagr_3y", "profit_cagr_3y",
        "promoter_pledge_pct", "gross_npa_pct", "net_npa_pct",
        "Intrinsic_Score", "PowerScore", "Fundamental_Pass", "Fundamental_Fail_Reasons"
    ]

    available_cols = [c for c in key_cols if c in df.columns]
    print(df.select(available_cols))
# ============================================================
# MAIN CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        prog="fundamentals",
        description="Fundamentals CLI - View, Score, and Analyze Stock Fundamentals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show fundamentals for a symbol
    python -m queen.cli.fundamentals_cli show TCS

    # Run scoring on all data
    python -m queen.cli.fundamentals_cli score --all

    # Compare symbols
    python -m queen.cli.fundamentals_cli compare TCS INFY WIPRO

    # Show sector rankings
    python -m queen.cli.fundamentals_cli sector "Information Technology"

    # Export to CSV
    python -m queen.cli.fundamentals_cli export --output fundamentals.csv --scored

    # Run full pipeline
    python -m queen.cli.fundamentals_cli pipeline --symbols TCS RELIANCE HDFCBANK

    # List available symbols
    python -m queen.cli.fundamentals_cli list
        """
    )

    parser.add_argument(
        "--processed-dir", "-d",
        type=str,
        default=str(DEFAULT_PROCESSED_DIR),
        help="Directory containing processed JSON files"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # show command
    show_parser = subparsers.add_parser("show", help="Show fundamentals for a symbol")
    show_parser.add_argument("symbol", help="Stock symbol (e.g., TCS)")

    # score command
    score_parser = subparsers.add_parser("score", help="Run scoring pipeline")
    score_parser.add_argument("--all", "-a", action="store_true", help="Score all symbols")
    score_parser.add_argument("--symbol", "-s", help="Score specific symbol")
    score_parser.add_argument("--gate", "-g", action="store_true", help="Apply gating")
    score_parser.add_argument("--limit", "-l", type=int, default=20, help="Limit output rows")

    # compare command
    compare_parser = subparsers.add_parser("compare", help="Compare multiple symbols")
    compare_parser.add_argument("symbols", nargs="+", help="Symbols to compare")

    # sector command
    sector_parser = subparsers.add_parser("sector", help="Show sector rankings")
    sector_parser.add_argument("sector_name", nargs="?", help="Sector name (partial match)")

    # export command
    export_parser = subparsers.add_parser("export", help="Export to CSV")
    export_parser.add_argument("--output", "-o", default="fundamentals_export.csv", help="Output file")
    export_parser.add_argument("--scored", action="store_true", help="Include scores")
    # In fundamentals_cli.py, add to the subparsers:
    fix_parser = subparsers.add_parser("fix-pe", help="Fix PE ratio in existing data")
    # pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run full pipeline")
    pipeline_parser.add_argument("--symbols", "-s", nargs="+", required=True, help="Symbols to process")
    pipeline_parser.add_argument("--workers", "-w", type=int, default=3, help="Parallel workers")

    # list command
    list_parser = subparsers.add_parser("list", help="List available symbols")

    debug_parser = subparsers.add_parser("debug", help="Debug fundamentals data")
    debug_parser.add_argument("symbols", nargs="*", help="Symbols to debug")
    inspect_parser = subparsers.add_parser("inspect", help="Inspect raw HTML for a symbol")
    inspect_parser.add_argument("symbol", help="Symbol to inspect")
    args = parser.parse_args()



    if not args.command:
        parser.print_help()
        return 0

    # Route to command handler
    commands = {
        "show": cmd_show,
        "score": cmd_score,
        "compare": cmd_compare,
        "sector": cmd_sector,
        "export": cmd_export,
        "pipeline": cmd_pipeline,
        "list": cmd_list,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    elif args.command == "debug":
           cmd_debug(args)
    elif args.command == "inspect":
        cmd_inspect(args)

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
