#!/usr/bin/env python3
# ============================================================
# queen/scripts/demo_ohlcv.py — v1.2 (Polars-safe demo)
# ============================================================
from __future__ import annotations

import math
from datetime import datetime, timedelta

import polars as pl


def _dummy_df(n: int = 120, interval: str = "1m") -> pl.DataFrame:
    end = datetime.now()
    start = end - timedelta(minutes=n - 1)
    ts = pl.datetime_range(start=start, end=end, interval=interval, eager=True)

    base = 100.0
    freq = 2 * math.pi / max(n, 1)
    close = [base + 2.0 * math.sin(i * freq) for i in range(n)]
    open_ = [c + (0.1 if i % 2 else -0.1) for i, c in enumerate(close)]
    high = [max(o, c) + 0.3 for o, c in zip(open_, close)]
    low = [min(o, c) - 0.3 for o, c in zip(open_, close)]
    vol = [1000 + (i % 10) * 10 for i in range(n)]

    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "oi": [0] * n,
            "symbol": ["DEMO"] * n,
            "isin": ["DEMO|ISIN"] * n,
        }
    )


def main():
    try:
        from queen.technicals.registry import get_indicator, list_indicators

        df = _dummy_df()
        names = list_indicators()[:3]
        print(f"[Demo] Found {len(names)} indicator(s): {names}")
        for name in names:
            fn = get_indicator(name)
            out = fn(df)
            if isinstance(out, pl.DataFrame):
                print(f"[Demo] {name} -> columns: {out.columns[:8]}...")
    except Exception as e:
        print(f"[Demo] Registry not available ({e}). Showing head() instead.")
        print(_dummy_df().head(5))


if __name__ == "__main__":
    main()
