#!/usr/bin/env python3
# ============================================================
# queen/cli/run_strategy.py — quick demo runner
# ============================================================
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict

import polars as pl
from queen.strategies.fusion import run_strategy
from rich.console import Console
from rich.table import Table


def _dummy_ohlcv(n: int = 180, interval: str = "1m") -> pl.DataFrame:
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
            "open": pl.Series(open_),
            "high": pl.Series(high),
            "low": pl.Series(low),
            "close": pl.Series(close),
            "volume": pl.Series(vol),
        }
    )


def _wire_minimals(
    df: pl.DataFrame,
    *,
    sps_level: float,
    regime_cycle: tuple[str, str, str] = ("TREND", "RANGE", "VOLATILE"),
) -> pl.DataFrame:
    idx = pl.arange(0, pl.len())
    return df.with_columns(
        [
            pl.lit(float(sps_level)).alias("SPS"),
            pl.when(idx % 3 == 0)
            .then(pl.lit(regime_cycle[0]))
            .when(idx % 3 == 1)
            .then(pl.lit(regime_cycle[1]))
            .otherwise(pl.lit(regime_cycle[2]))
            .alias("Regime_State"),
            pl.lit(1.10).alias("ATR_Ratio"),
        ]
    )


def main():
    frames: Dict[str, pl.DataFrame] = {
        "intraday_15m": _wire_minimals(_dummy_ohlcv(120, "1m"), sps_level=0.68),
        "hourly_1h": _wire_minimals(_dummy_ohlcv(240, "1m"), sps_level=0.62),
        "daily": _wire_minimals(_dummy_ohlcv(300, "1m"), sps_level=0.58),
    }
    out = run_strategy("DEMO", frames)

    console = Console()
    t = Table(title="Strategy Fusion — DEMO", header_style="bold green", expand=True)
    t.add_column("TF", justify="center")
    t.add_column("Score", justify="center")
    t.add_column("Bias", justify="center")
    t.add_column("Entry?", justify="center")
    t.add_column("Exit?", justify="center")
    t.add_column("Risk", justify="center")

    for tf, row in out["per_tf"].items():
        t.add_row(
            tf,
            f'{row["strategy_score"]:.3f}',
            row["bias"],
            str(row["entry_ok"]),
            str(row["exit_ok"]),
            row["risk_band"],
        )
    console.print(t)
    console.rule("[bold cyan]Fused")
    console.print(out["fused"])


if __name__ == "__main__":
    main()
