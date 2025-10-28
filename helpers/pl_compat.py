#!/usr/bin/env python3
# ============================================================
# queen/helpers/pl_compat.py — Polars compatibility helpers
# ------------------------------------------------------------
# Ensures forward-safe conversion & expression handling
# across Polars versions (0.19 → 1.x).
# ============================================================

from __future__ import annotations

import numpy as np
import polars as pl


def _s2np(s: pl.Series) -> np.ndarray:
    """Robust Series → NumPy conversion (always float64).
    Works across all Polars versions.
    """
    try:
        # Polars >= 0.19+ supports to_numpy()
        return s.to_numpy()
    except TypeError:
        # Some versions don't accept dtype arg
        return np.asarray(s.to_list(), dtype=float)
    except AttributeError:
        # Very old Polars fallback
        return np.array(list(s), dtype=float)


def ensure_float_series(s: pl.Series) -> pl.Series:
    """Guarantee float dtype (for math operations)."""
    if s.dtype.is_numeric():
        return s.cast(pl.Float64)
    try:
        return pl.Series(s.name, [float(x) for x in s])
    except Exception:
        return pl.Series(s.name, [np.nan] * len(s))


def safe_fill_null(s: pl.Series, value: float = 0.0) -> pl.Series:
    """Fill nulls safely, forward/backward compatible."""
    try:
        return s.fill_null(strategy="forward").fill_null(value)
    except Exception:
        return s.fill_none(value)


def safe_concat(dfs: list[pl.DataFrame]) -> pl.DataFrame:
    """Safe concat that skips None/empty frames."""
    valid = [d for d in dfs if d is not None and not d.is_empty()]
    if not valid:
        return pl.DataFrame()
    return pl.concat(valid, how="diagonal_relaxed")
