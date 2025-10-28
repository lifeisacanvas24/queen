#!/usr/bin/env python3
# ============================================================
# queen/cli/validate_registry.py — v1.0
# Quick validator for indicator/signal registry + sample compute
# ============================================================
from __future__ import annotations

import argparse
import asyncio
from typing import Iterable

import polars as pl
from queen.fetchers.upstox_fetcher import fetch_unified
from queen.settings.indicator_policy import params_for as indicator_params_for
from queen.technicals.registry import (
    build_registry,
    get_indicator,
    list_indicators,
    list_signals,
)


def _mode_from_tf(tf: str) -> str:
    t = (tf or "").lower()
    return "intraday" if t.endswith(("m", "h")) else "daily"


def _print_header(title: str):
    print("\n" + "—" * 72)
    print(title)
    print("—" * 72)


async def _sample_compute(symbol: str, timeframe: str, names: Iterable[str], rows: int):
    mode = _mode_from_tf(timeframe)
    df = await fetch_unified(symbol, mode=mode, interval=timeframe)
    if df.is_empty():
        print(f"⚠️  Empty DF for {symbol} @ {timeframe} (mode={mode})")
        return
    if df.height > rows:
        df = df.tail(rows)

    for name in names:
        try:
            fn = get_indicator(name)
        except KeyError:
            print(f"✗ {name}: not found in registry")
            continue

        params = indicator_params_for(name, timeframe) or {}
        try:
            out = fn(df, **params)
        except Exception as e:
            print(f"✗ {name}: compute failed → {e}")
            continue

        # Print a compact tail for whatever shape we got back
        if isinstance(out, pl.DataFrame):
            # choose first numeric column
            num_cols = [c for c in out.columns if pl.datatypes.is_numeric(out[c].dtype)]
            if num_cols:
                vals = out[num_cols[0]].drop_nulls().tail(5).to_list()
                print(f"✓ {name:<18} ({num_cols[0]}) → tail5: {vals}")
            else:
                print(f"✓ {name:<18} (df:{out.columns}) → ok")
        elif isinstance(out, pl.Series):
            vals = out.drop_nulls().tail(5).to_list()
            print(f"✓ {name:<18} → tail5: {vals}")
        else:
            # dict or other object
            s = str(out)
            s = s if len(s) <= 120 else s[:117] + "..."
            print(f"✓ {name:<18} → {s}")


def main():
    p = argparse.ArgumentParser(
        description="Validate indicator/signal registry and run sample computations."
    )
    p.add_argument(
        "--list-only", action="store_true", help="Only list names; no samples"
    )
    p.add_argument(
        "--indicators",
        type=str,
        default="",
        help="Comma-separated indicator names to sample (optional)",
    )
    p.add_argument(
        "--symbol", type=str, default="BSE", help="Sample symbol (default: BSE)"
    )
    p.add_argument(
        "--timeframe",
        type=str,
        default="1d",
        help="Sample timeframe (e.g., 5m, 15m, 1d)",
    )
    p.add_argument(
        "--rows",
        type=int,
        default=180,
        help="Bars to load for sample compute (default: 180)",
    )
    args = p.parse_args()

    build_registry(force=True)

    inds = list_indicators()
    sigs = list_signals()

    _print_header("Registry Overview")
    print(f"Indicators: {len(inds)}")
    print(f"Signals   : {len(sigs)}")

    # Show a few names for quick glance
    show_n = min(20, len(inds))
    if show_n:
        print(
            "\nSample indicators:",
            ", ".join(inds[:show_n]) + (" ..." if len(inds) > show_n else ""),
        )
    show_n = min(20, len(sigs))
    if show_n:
        print(
            "Sample signals   :",
            ", ".join(sigs[:show_n]) + (" ..." if len(sigs) > show_n else ""),
        )

    if args.list_only:
        return

    # Prepare which indicators to sample
    names = [n.strip() for n in args.indicators.split(",") if n.strip()]
    if not names:
        # sensible defaults if not provided
        names = [
            n
            for n in (
                "ema",
                "ema_cross",
                "ema_slope",
                "vwap",
                "price_minus_vwap",
                "rsi",
            )
            if n in inds
        ]

    _print_header(
        f"Sample Compute → {args.symbol} @ {args.timeframe}  ({len(names)} indicators)"
    )
    asyncio.run(_sample_compute(args.symbol, args.timeframe, names, args.rows))


if __name__ == "__main__":
    main()
