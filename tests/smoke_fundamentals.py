#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_fundamentals.py — v3.3 (FINAL, K1+G1 aligned)
# ------------------------------------------------------------
# Full smoke pipeline:
#   1. Scrape (optional)
#   2. Reveal extracted JSON (sanity)
#   3. Load Polars DF (adapter → engine)
#   4. Apply TS features
#   5. Intrinsic + PowerScore + MAX filters
# ============================================================

from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

from queen.fetchers.fundamentals_scraper import scrape_many
from queen.helpers.fundamentals_polars_engine import load_all
from queen.helpers.fundamentals_registry import REGISTRY
from queen.helpers.fundamentals_timeseries_engine import add_timeseries_features
from queen.settings.fundamentals_map import FUNDAMENTALS_METRIC_COLUMNS
from queen.settings.settings import FETCH, get_env
from queen.technicals.fundamentals_score_engine import score_and_filter


# Temporary simple logger for smoke tests
class Logger:
    def info(self, msg): print(msg)
    def warning(self, msg): print(msg)
    def error(self, msg): print(msg)

log = Logger()


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fundamentals Smoke Test v3.3")
    p.add_argument("--symbols", type=str,
                   default="GROWW,NETWEB,AXISBANK,INFY",
                   help="Comma-separated symbols")

    p.add_argument("--force-scrape", action="store_true",
                   help="Force fresh Screener scrape")

    return p.parse_args()


# ------------------------------------------------------------
# Extraction PREVIEW
# ------------------------------------------------------------
def _preview_extracted(symbol: str, processed_dir: Path) -> None:
    path = processed_dir / f"{symbol}.json"
    if not path.exists():
        print(f"\n🚫 No JSON for {symbol}")
        return

    data = json.loads(path.read_text())

    print("\n" + "=" * 70)
    print(f"EXTRACTION PREVIEW — {symbol}")
    print("=" * 70)

    # ---- Top Ratios
    tr = data.get("top_ratios", {})
    print("\n• Top Ratios:")
    for k, v in tr.items():
        print(f"  {k:25s} = {v}")

    # ---- Tables preview helper
    def show_table(name: str):
        tbl = data.get(name, {})
        print(f"\n• {name}: keys = {list(tbl.keys())[:10]}")
        if not tbl:
            print("  ❗ EMPTY TABLE")
            return
        k0 = next(iter(tbl.keys()))
        v0 = tbl[k0]

        # Check if v0 is a dictionary (period-value pairs) or a simple value
        if isinstance(v0, dict):
            periods = list(v0.keys())
            values = list(v0.values())
            print(f"  sample periods: {periods[:5]}")
            print(f"  sample values ({k0}): {values[:5]}")
        else:
            print(f"  {k0}: {v0} (single value)")

# ------------------------------------------------------------
# Null metrics warning
# ------------------------------------------------------------
def _warn_if_null_metrics(df: pl.DataFrame) -> None:
    if df.is_empty():
        return

    # K1-final metric names
    keys = [
        "market_cap", "pe_ratio", "debt_to_equity", "eps_ttm",
        "gross_npa_pct", "net_npa_pct"
    ]
    present = [k for k in keys if k in df.columns]
    if not present:
        log.warning("[SMOKE-FUND] No headline metrics at all (Drift?)")
        return

    null_rate = {
        c: float(df.select(pl.col(c).is_null().mean()).item())
        for c in present
    }

    high = [c for c, r in null_rate.items() if r >= 0.60]
    if high:
        log.warning(f"[SMOKE-FUND] High null rate (>=60%): {high}")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    args = _parse_args()

    env = get_env()
    s = FETCH["FUNDAMENTALS"]
    raw_dir = Path(s["RAW_DIR"])
    processed_dir = Path(s["PROCESSED_DIR"])

    log.info(f"[SMOKE-FUND] ENV={env}")
    log.info(f"[SMOKE-FUND] RAW_DIR={raw_dir}")
    log.info(f"[SMOKE-FUND] PROCESSED_DIR={processed_dir}")

    processed_dir.mkdir(parents=True, exist_ok=True)

    symbols = [x.strip().upper() for x in args.symbols.split(",")]

    # Scrape if needed
    if args.force_scrape:
        log.info("[SMOKE-FUND] FORCE SCRAPE ACTIVE")
        scrape_many(symbols)

    missing = [s for s in symbols if not (processed_dir / f"{s}.json").exists()]
    if missing:
        log.info(f"[SMOKE-FUND] Missing: {missing} → scraping…")
        scrape_many(missing)

    # ------------------------------------------------------------
    # 1) Extraction previews
    # ------------------------------------------------------------
    for sym in symbols:
        _preview_extracted(sym, processed_dir)

    # ------------------------------------------------------------
    # 2) Load DF (adapter → Polars)
    # ------------------------------------------------------------
    # With:
    log.info(f"[SMOKE-FUND] Loading from: {processed_dir}")
    if not processed_dir.exists():
        log.error(f"[SMOKE-FUND] Processed directory does not exist: {processed_dir}")
        return

    # Check if there are any JSON files
    json_files = list(processed_dir.glob("*.json"))
    log.info(f"[SMOKE-FUND] Found {len(json_files)} JSON files in processed directory")

    if not json_files:
        log.error("[SMOKE-FUND] No JSON files found in processed directory")
        return

    df = load_all(processed_dir)
    print("\n=== RAW FUNDAMENTALS DF (HEAD) ===")
    print(df.head())

    # ------------------------------------------------------------
    # 3) Registry baselines
    # ------------------------------------------------------------
    REGISTRY.build(df, FUNDAMENTALS_METRIC_COLUMNS)
    print(f"Sector groups: {len(REGISTRY.sector_map)}")

    _warn_if_null_metrics(df)

    # ------------------------------------------------------------
    # 4) Time-Series
    # ------------------------------------------------------------
    df_ts = add_timeseries_features(df)
    print("\n=== TIME-SERIES FEATURES (HEAD) ===")
    show_cols = [
        c for c in [
            "Symbol", "Sector",
            "ROCE_Slope", "Profit_Q_Slope", "EPS_Q_Slope",
            "NetNPA_Slope",
            "Fundamental_Momentum", "Earnings_Momentum",
            "Bank_Asset_Quality_Trend"
        ] if c in df_ts.columns
    ]
    print(df_ts.select(show_cols).head())

    # ------------------------------------------------------------
    # 5) Scoring (Intrinsic + PowerScore + MAX)
    # ------------------------------------------------------------
    scored = score_and_filter(df_ts)
    print("\n=== FINAL SCORED OUTPUT ===")
    print(
        scored.select(
            [
                "Symbol",
                "Intrinsic_Score",
                "Intrinsic_Bucket",
                "PowerScore",
                "Fundamental_Pass",
                "Fundamental_Fail_Reasons"
            ]
        )
        .sort("Intrinsic_Score", descending=True)
        .head(10)
    )

    log.info("[SMOKE-FUND] COMPLETE ✓")


if __name__ == "__main__":
    main()
