#!/usr/bin/env python3
# ============================================================
# queen/technicals/patterns/runner.py — v1.0
# One-call aggregator for patterns:
#   • Core booleans from patterns/core.py
#   • Composite (name/bias/confidence/group) from patterns/composite.py
# Safe across Polars versions (Series-first style).
# ============================================================

from __future__ import annotations

from typing import Iterable, Optional

import polars as pl

from . import core as pc
from .composite import detect_composite_patterns


def run_patterns(
    df: pl.DataFrame,
    *,
    include_core: bool = True,
    include_composite: bool = True,
    core_subset: Optional[Iterable[str]] = None,
    drop_unhit_core: bool = False,
) -> pl.DataFrame:
    """Return a DataFrame with pattern outputs aligned to `df` rows.

    Columns added:
      • Core (bool): doji, hammer, shooting_star, bullish_engulfing, bearish_engulfing
      • Composite: pattern_name (Utf8), pattern_bias (Utf8), confidence (Int64), pattern_group (Utf8)
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    out = df

    if include_core:
        # Build set of core detectors from EXPORTS (skip 'required_lookback')
        all_core = [k for k in pc.EXPORTS.keys() if k != "required_lookback"]
        names = list(core_subset) if core_subset else all_core

        # Compute each detector safely and collect booleans
        core_cols: list[pl.Series] = []
        for name in names:
            fn = pc.EXPORTS.get(name)
            if not callable(fn):
                continue
            try:
                s = fn(out)
                # ensure boolean dtype + stable name
                if s.dtype != pl.Boolean:
                    s = s.cast(pl.Boolean)
                if not getattr(s, "name", None):
                    s = s.alias(name)
                core_cols.append(s.alias(name))
            except Exception:
                # skip on error (smoke tests will catch if needed)
                pass

        if core_cols:
            out = out.with_columns(core_cols)

        if drop_unhit_core:
            # remove core columns that are all False/Null
            drop = []
            for name in names:
                if name in out.columns:
                    col = out[name].fill_null(False)
                    if col.dtype == pl.Boolean and bool(col.sum()) is False:
                        drop.append(name)
            if drop:
                out = out.drop(drop)

    if include_composite:
        try:
            comp = detect_composite_patterns(out)
            # keep only the composite columns to avoid accidental overwrite
            keep = ["pattern_name", "pattern_bias", "confidence", "pattern_group"]
            comp = comp.select([c for c in keep if c in comp.columns])
            out = pl.concat([out, comp], how="horizontal")
        except Exception:
            # composite is optional; continue if it fails
            pass

    return out
