#!/usr/bin/env python3
from __future__ import annotations

import polars as pl
from queen.helpers.logger import log
from queen.technicals.signals import registry


def _dummy_df(n=50) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": pl.datetime_range(
                low=pl.datetime(2025, 1, 1),
                high=pl.datetime(2025, 1, 1, 0, n - 1),
                interval="1m",
            ),
            "open": pl.Series([100 + i * 0.1 for i in range(n)]),
            "high": pl.Series([100 + i * 0.1 + 0.5 for i in range(n)]),
            "low": pl.Series([100 + i * 0.1 - 0.5 for i in range(n)]),
            "close": pl.Series(
                [100 + i * 0.1 + (1 if i % 10 == 0 else 0) for i in range(n)]
            ),
            "volume": pl.Series([1000 + (i % 7) * 50 for i in range(n)]),
        }
    )


def main():
    df = _dummy_df()
    names = registry.names()
    print(f"Discovered {len(names)} signal/indicator providers.")
    for name in names[:10]:  # quick sample
        fn = registry.get(name)
        try:
            obj = fn() if inspect.isclass(fn) else fn
            if hasattr(obj, "evaluate"):
                out = obj.evaluate(df)
            else:
                out = obj(df)  # compute(df)
            log.info(
                f"[Demo] {name}: OK → {out.shape if hasattr(out, 'shape') else type(out)}"
            )
        except Exception as e:
            log.warning(f"[Demo] {name}: FAILED → {e}")


if __name__ == "__main__":
    import inspect

    main()
