#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_registry.py — v1.0
# ============================================================
from __future__ import annotations

import polars as pl
from queen.technicals.registry import build_registry, get_indicator, list_indicators


def test():
    build_registry(force=True)
    inds = list_indicators()
    assert isinstance(inds, list), "list_indicators() must return a list"
    # if the template is present, try invoking it
    if "template_indicator" in inds:
        fn = get_indicator("template_indicator")
        df = pl.DataFrame({"close": pl.Series([100 + i * 0.1 for i in range(50)])})
        out = fn(df, timeframe="15m")  # our template accepts timeframe kw
        assert isinstance(out, pl.DataFrame)
        assert {"template_value", "template_norm"}.issubset(set(out.columns))
    print("✅ smoke_registry: passed")


if __name__ == "__main__":
    test()
