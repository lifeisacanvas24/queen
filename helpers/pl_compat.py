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
    if s is None:
        return pl.Series("value", [], dtype=pl.Float64)
    try:
        # Newer Polars has .is_numeric(), older can use datatypes helper
        if hasattr(s.dtype, "is_numeric") and s.dtype.is_numeric():
            return s.cast(pl.Float64)
        try:
            if pl.datatypes.is_numeric_dtype(s.dtype):  # type: ignore[attr-defined]
                return s.cast(pl.Float64)
        except Exception:
            pass
        return pl.Series(s.name, [float(x) for x in s])
    except Exception:
        return pl.Series(s.name, [np.nan] * len(s))


def safe_fill_null(
    s: pl.Series,
    value: float = 0.0,
    *,
    forward: bool = True,
) -> pl.Series:
    """Fill nulls safely, forward/backward compatible.

    Args:
        value: scalar to use for final fill (after forward-fill).
        forward: if True, try a forward fill first, then scalar fill.
                 if False, only scalar fill is applied.

    Order:
        1) (optional) forward-fill nulls
        2) scalar fill of any remaining nulls
    """
    if s is None:
        return pl.Series("value", [], dtype=pl.Float64)

    out = s
    if forward:
        # 1) try forward fill on modern Polars
        try:
            out = out.fill_null(strategy="forward")
        except Exception:
            # 2) fallback for older Polars (fill_none may not exist everywhere)
            try:
                out = out.fill_none(strategy="forward")  # type: ignore[arg-type]
            except Exception:
                # if even that fails, just skip the forward step
                pass

    # 3) scalar value fill for whatever is still null/none
    try:
        out = out.fill_null(value)
    except Exception:
        try:
            out = out.fill_none(value)  # type: ignore[arg-type]
        except Exception:
            # absolute last resort: rebuild series
            out = pl.Series(out.name, [value if x is None else x for x in out])

    return out


def safe_concat(dfs: list[pl.DataFrame]) -> pl.DataFrame:
    """Safe concat that skips None/empty frames."""
    valid = [d for d in dfs if d is not None and not d.is_empty()]
    if not valid:
        return pl.DataFrame()
    # diagonal_relaxed keeps all cols even if schemas differ slightly
    return pl.concat(valid, how="diagonal_relaxed")
