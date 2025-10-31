#!/usr/bin/env python3
# ============================================================
# queen/tests/smoke_template_indicator.py
# ------------------------------------------------------------
# Verifies indicator template wiring (settings-driven).
# Asserts presence of: template_value, template_norm
# ============================================================

from __future__ import annotations

import polars as pl
from queen.technicals.signals.templates.indicator_template import (
    compute_indicator,
    summarize_indicator,
)


def test():
    n = 100
    df = pl.DataFrame(
        {"close": pl.Series([100 + (i % 7) * 0.2 for i in range(n)], dtype=pl.Float64)}
    )
    out = compute_indicator(df, timeframe="15m")

    required = {"template_value", "template_norm"}
    missing = required - set(out.columns)
    assert not missing, f"Missing columns: {sorted(missing)}"

    # summary should be a dict with 'value'/'bias' when data present
    summary = summarize_indicator(out)
    assert isinstance(summary, dict), "summary is not a dict"
    assert "value" in summary and "bias" in summary, f"summary keys missing: {summary}"

    print("✅ smoke_template_indicator: passed")


if __name__ == "__main__":
    test()
