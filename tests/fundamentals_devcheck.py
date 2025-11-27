#!/usr/bin/env python3
# ============================================================
# queen/tests/fundamentals_devcheck.py — v2.0 (Polars-only, v3.1 aligned)
# ------------------------------------------------------------
# Devcheck / drift detector for Fundamentals subsystem.
#
# What this verifies:
#   1) Scraper JSON existence + optional force scrape
#   2) Polars engine can build DF from processed JSONs
#   3) Registry baselines load correctly (global + sector)
#   4) Null-rate drift check for headline metrics
#   5) Sample preview of extracted fundamentals
#   6) Optional: TS features + intrinsic/powerscore + pass/fail
#
# Compatible with:
#   • fundamentals_scraper.py v3.x  -> scrape_many
#   • fundamentals_polars_engine.py v3.1 -> build_df_from_all_processed
#   • fundamentals_registry.py v2.x -> REGISTRY.load
#   • fundamentals_timeseries_engine.py v1.x -> add_timeseries_features
#   • fundamentals_score_engine.py v3.x -> score_and_filter
# ============================================================
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

import polars as pl

from queen.fetchers.fundamentals_scraper import scrape_many
from queen.helpers.fundamentals_polars_engine import build_df_from_all_processed
from queen.helpers.fundamentals_registry import REGISTRY
from queen.helpers.fundamentals_timeseries_engine import add_timeseries_features
from queen.helpers.logger import log
from queen.settings.settings import FETCH, get_env
from queen.settings.fundamentals_map import FUNDAMENTALS_METRIC_COLUMNS

# score engine is optional in devcheck (don’t crash if missing)
try:
    from queen.technicals.fundamentals_score_engine import score_and_filter
except Exception:
    score_and_filter = None


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Queen Fundamentals Devcheck v2.0")
    p.add_argument(
        "--symbols",
        type=str,
        default="GROWW,MAZDOCK,GRSE,DATAPATTNS,VOLTAMP",
        help="Comma-separated symbol list",
    )
    p.add_argument(
        "--force-scrape",
        action="store_true",
        help="Scrape symbols even if JSON exists",
    )
    p.add_argument(
        "--sample",
        type=int,
        default=8,
        help="How many rows to print for dataframe head/sample",
    )
    p.add_argument(
        "--null-threshold",
        type=float,
        default=0.6,
        help="Warn if null-rate >= threshold for any key metric",
    )
    return p.parse_args()


# ------------------------------------------------------------
# Extraction preview (raw JSON)
# ------------------------------------------------------------
def _preview_extracted(symbol: str, processed_dir: Path) -> None:
    p = processed_dir / f"{symbol}.json"
    if not p.exists():
        log.warning(f"[DEV-FUND] No processed JSON for {symbol}")
        return

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"[DEV-FUND] JSON read failed for {symbol}: {e}")
        return

    print("\n" + "=" * 72)
    print(f"EXTRACTION PREVIEW — {symbol}")
    print("=" * 72)

    # top ratios
    tr = data.get("top_ratios") or {}
    print("\n• Top Ratios Extracted:")
    if not tr:
        print("  ❗ EMPTY top_ratios (possible login wall / drift)")
    else:
        for k, v in tr.items():
            print(f"  {k:24s} = {v}")

    # helper to show a table’s first key/series
    def show_table(name: str):
        tbl = data.get(name) or {}
        print(f"\n• {name} keys: {list(tbl.keys())[:10]}")
        if not tbl:
            print("  ❗ EMPTY TABLE")
            return
        k0 = next(iter(tbl.keys()))
        s0 = tbl.get(k0) or {}
        if isinstance(s0, dict):
            periods = list(s0.keys())[:5]
            values = list(s0.values())[:5]
            print(f"  sample periods: {periods}")
            print(f"  sample values ({k0}): {values}")
        else:
            print(f"  ❗ Unexpected series shape for {k0}")

    for name in ["quarters", "profit_loss", "balance_sheet", "cash_flow", "ratios"]:
        show_table(name)

    # growth
    growth = data.get("growth") or {}
    print("\n• Growth Flattened:")
    if not growth:
        print("  ❗ EMPTY")
    else:
        for k, v in list(growth.items())[:12]:
            print(f"  {k:28s} = {v}")

    # shareholding
    sh = data.get("shareholding") or {}
    print("\n• Shareholding:")
    for mode in ["quarterly", "yearly"]:
        part = sh.get(mode) or {}
        print(f"  {mode} keys: {list(part.keys())[:10]}")
        if not part:
            print("    ❗ EMPTY")
            continue
        k0 = next(iter(part.keys()))
        s0 = part.get(k0) or {}
        if isinstance(s0, dict):
            periods = list(s0.keys())[:5]
            values = list(s0.values())[:5]
            print(f"    sample periods: {periods}")
            print(f"    sample values ({k0}): {values}")


# ------------------------------------------------------------
# Null-rate drift warning
# ------------------------------------------------------------
def _warn_if_null_metrics(df: pl.DataFrame, thresh: float) -> None:
    if df is None or df.is_empty():
        return

    keys = [
        "Market Cap",
        "Stock P/E",
        "Debt to Equity",
        "EPS (TTM)",
        "Gross NPA %",
        "Net NPA %",
    ]

    present = [c for c in keys if c in df.columns]
    if not present:
        log.warning("[DEV-FUND] No headline metric columns found in DF (drift?)")
        return

    null_rate: Dict[str, float] = {}
    for c in present:
        try:
            r = float(df.select(pl.col(c).is_null().mean()).item())
            null_rate[c] = r
        except Exception:
            continue

    high = [c for c, r in null_rate.items() if r >= thresh]
    if high:
        log.warning(
            f"[DEV-FUND] HIGH NULL RATE >= {thresh:.0%} in: {high} "
            f"→ likely Screener drift/login wall. Check RAW HTML."
        )


# ------------------------------------------------------------
# Registry loader (back-compat)
# ------------------------------------------------------------
def _load_registry(df: pl.DataFrame) -> None:
    if df is None or df.is_empty():
        return
    # your registry file uses .load(...)
    if hasattr(REGISTRY, "load") and callable(getattr(REGISTRY, "load")):
        REGISTRY.load(df, FUNDAMENTALS_METRIC_COLUMNS)
        return
    # fallback older name .build(...)
    if hasattr(REGISTRY, "build") and callable(getattr(REGISTRY, "build")):
        REGISTRY.build(df, FUNDAMENTALS_METRIC_COLUMNS)
        return
    log.warning("[DEV-FUND] REGISTRY has no load/build method. Skipping stats.")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    args = _parse_args()

    env = get_env()
    s = FETCH["FUNDAMENTALS"]
    raw_dir = Path(s["RAW_DIR"])
    processed_dir = Path(s["PROCESSED_DIR"])

    log.info(f"[DEV-FUND] ENV={env}")
    log.info(f"[DEV-FUND] RAW_DIR={raw_dir}")
    log.info(f"[DEV-FUND] PROCESSED_DIR={processed_dir}")

    processed_dir.mkdir(parents=True, exist_ok=True)

    symbols = [x.strip().upper() for x in args.symbols.split(",") if x.strip()]
    if not symbols:
        log.error("[DEV-FUND] No symbols provided.")
        return

    # 1) Scrape stage
    if args.force_scrape:
        log.info("[DEV-FUND] Force scrape enabled")
        scrape_many(symbols)
    else:
        missing = [sym for sym in symbols if not (processed_dir / f"{sym}.json").exists()]
        if missing:
            log.info(f"[DEV-FUND] Missing JSON for {missing} → scraping")
            scrape_many(missing)

    # 2) Raw extraction preview
    for sym in symbols:
        _preview_extracted(sym, processed_dir)

    # 3) Build Polars DF
    df = build_df_from_all_processed(processed_dir)
    print("\n=== RAW FUNDAMENTALS DF (HEAD) ===")
    print(df.head(args.sample))

    # 4) Registry stats
    _load_registry(df)
    try:
        print(f"\nSector count: {len(REGISTRY.sector_map)}")
        print(f"Metric columns tracked: {len(REGISTRY.columns)}")
    except Exception:
        pass

    # 5) Null drift warnings
    _warn_if_null_metrics(df, args.null_threshold)

    # 6) Time-series features
    df_ts = add_timeseries_features(df)
    print("\n=== TIME-SERIES FEATURES (HEAD) ===")
    ts_cols = [
        c for c in [
            "Symbol",
            "Sector",
            "ROCE_Slope",
            "ROE_Slope",
            "Sales_Q_Slope",
            "Profit_Q_Slope",
            "EPS_Q_Slope",
            "GrossNPA_Slope",
            "NetNPA_Slope",
            "Fundamental_Momentum",
            "Earnings_Momentum",
            "Bank_Asset_Quality_Trend",
        ] if c in df_ts.columns
    ]
    if ts_cols:
        print(df_ts.select(ts_cols).head(args.sample))
    else:
        print("No TS columns produced (deep tables missing or drift).")

    # 7) Scoring (if engine available)
    if score_and_filter is not None:
        scored = score_and_filter(df_ts)
        print("\n=== FINAL SCORED OUTPUT (TOP) ===")
        cols = [
            c for c in [
                "Symbol",
                "Intrinsic_Score",
                "Intrinsic_Bucket",
                "PowerScore",
                "Fundamental_Pass",
                "Fundamental_Fail_Reasons",
            ] if c in scored.columns
        ]
        print(scored.select(cols).sort("Intrinsic_Score", descending=True).head(args.sample))
    else:
        log.warning("[DEV-FUND] score_and_filter not importable → skipping scoring stage")

    log.info("[DEV-FUND] DEVHECK COMPLETE ✓")


if __name__ == "__main__":
    main()
