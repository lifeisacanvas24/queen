#!/usr/bin/env python3
# ============================================================
# queen/helpers/ta_math.py — v1.0 (Bible v10.5 TA Primitives)
# ------------------------------------------------------------
# Single source of truth for core TA math helpers.
#
# Pure NumPy, no Polars/settings/logging dependencies.
# Use these from indicators instead of re-implementing:
#
#   • to_np             → robust Series/iterable → np.ndarray
#   • sma               → simple moving average
#   • ema               → standard EMA
#   • wilder_ema        → Wilder-style EMA (1/period smoothing)
#   • true_range        → per-bar True Range
#   • atr_wilder        → ATR using Wilder smoothing
#   • normalize_0_1     → [0, 1] normalization
#   • normalize_sym     → [-1, +1] normalization
#   • gradient_norm     → normalized gradient for slope-style signals
#
# All functions are side-effect free and NaN-tolerant where sensible.
# ============================================================

from __future__ import annotations

from typing import Iterable, Union

import numpy as np

ArrayLike = Union[np.ndarray, Iterable[float]]


# ------------------------------------------------------------
# Core conversion helper
# ------------------------------------------------------------
def to_np(x: ArrayLike, *, dtype=float) -> np.ndarray:
    """Convert an iterable/array-like into a 1D NumPy array of given dtype.

    Safe to pass:
        • lists / tuples
        • NumPy arrays
        • Polars Series (relies on __array__ or list() fallback)
    """
    if isinstance(x, np.ndarray):
        arr = x
    else:
        # Polars Series, lists, etc.
        try:
            arr = np.asarray(x, dtype=dtype)
        except TypeError:
            # Some objects (e.g. polars Series) behave better via list()
            arr = np.asarray(list(x), dtype=dtype)

    if arr.ndim == 0:
        arr = arr.reshape(1)
    elif arr.ndim > 1:
        arr = arr.reshape(-1)

    return arr.astype(dtype, copy=False)


# ------------------------------------------------------------
# 1) Moving Averages
# ------------------------------------------------------------
def sma(series: ArrayLike, window: int, *, allow_short: bool = True) -> np.ndarray:
    """Simple Moving Average using a convolution kernel.

    Args:
        series: 1D price/volume array.
        window: MA length.
        allow_short: if False, the first (window-1) values are NaN.
                     if True, we scale by actual count (expanding SMA).

    Returns:
        np.ndarray of same length as input.

    """
    s = to_np(series, dtype=float)
    n = s.size
    if n == 0 or window <= 0:
        return np.zeros_like(s)

    window = int(window)
    kernel = np.ones(window, dtype=float)

    if allow_short:
        # expanding SMA for the first few samples
        cumsum = np.cumsum(s)
        denom = np.arange(1, n + 1, dtype=float)
        sma_full = cumsum / denom

        # then switch to full-window SMA once we have enough samples
        if n >= window:
            conv = np.convolve(s, kernel, mode="valid") / float(window)
            sma_full[window - 1 :] = conv
        return sma_full

    # classic SMA (NaN for first window-1)
    conv = np.convolve(s, kernel, mode="valid") / float(window)
    prefix = np.full(window - 1, np.nan, dtype=float)
    return np.concatenate([prefix, conv])


def ema(series: ArrayLike, span: int) -> np.ndarray:
    """Standard EMA with alpha = 2 / (span + 1).

    This is the canonical EMA for all indicators
    (MACD, Keltner baselines, etc.).
    """
    s = to_np(series, dtype=float)
    n = s.size
    if n == 0 or span <= 0:
        return np.zeros_like(s)

    alpha = 2.0 / (span + 1.0)
    out = np.zeros_like(s, dtype=float)
    out[0] = s[0]
    for i in range(1, n):
        out[i] = alpha * s[i] + (1.0 - alpha) * out[i - 1]
    return out


def wilder_ema(series: ArrayLike, period: int) -> np.ndarray:
    """Wilder-style EMA (used for ATR/ADX style measures).

    Smoothing:
        out[0] = mean(series[0:period])
        out[i] = ((out[i-1] * (period - 1)) + series[i]) / period
    """
    s = to_np(series, dtype=float)
    n = s.size
    if n == 0 or period <= 0:
        return np.zeros_like(s)

    period = int(period)
    out = np.zeros_like(s, dtype=float)
    if n < period:
        # not enough data: use simple mean of available values
        m = float(np.nanmean(s))
        out[:] = m
        return out

    out[period - 1] = float(np.nanmean(s[:period]))
    for i in range(period, n):
        out[i] = ((out[i - 1] * (period - 1)) + s[i]) / period

    # For the first period-1 values, we can either NaN or backfill
    # Here we backfill with the first computed value for simplicity
    out[: period - 1] = out[period - 1]
    return out


# ------------------------------------------------------------
# 2) True Range / ATR
# ------------------------------------------------------------
def true_range(
    high: ArrayLike, low: ArrayLike, prev_close: ArrayLike
) -> np.ndarray:
    """True Range per bar:

    TR = max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close),
    )
    """
    h = to_np(high, dtype=float)
    l = to_np(low, dtype=float)
    pc = to_np(prev_close, dtype=float)

    # Align lengths
    n = min(h.size, l.size, pc.size)
    h, l, pc = h[:n], l[:n], pc[:n]

    return np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])


def atr_wilder(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    period: int = 14,
) -> np.ndarray:
    """ATR using Wilder smoothing over True Range.

    Args:
        high, low, close: price arrays.
        period: ATR period (default 14).

    Returns:
        np.ndarray of ATR values (NaN-safe, NaNs converted to 0).

    """
    h = to_np(high, dtype=float)
    l = to_np(low, dtype=float)
    c = to_np(close, dtype=float)

    n = min(h.size, l.size, c.size)
    if n == 0:
        return np.array([], dtype=float)

    h, l, c = h[:n], l[:n], c[:n]
    prev_close = np.roll(c, 1)
    tr = true_range(h, l, prev_close)

    atr = wilder_ema(tr, period=period)
    return np.nan_to_num(atr, nan=0.0)


# ------------------------------------------------------------
# 3) Normalization helpers
# ------------------------------------------------------------
def normalize_0_1(x: ArrayLike, *, eps: float = 1e-9) -> np.ndarray:
    """Normalize an array to [0, 1] using running min/max.

    If range is ~0, falls back to all zeros.
    """
    arr = to_np(x, dtype=float)
    if arr.size == 0:
        return arr

    with np.errstate(all="ignore"):
        mn = np.nanmin(arr)
        mx = np.nanmax(arr)

    if not np.isfinite(mn) or not np.isfinite(mx) or mx - mn < eps:
        return np.zeros_like(arr)

    return np.clip((arr - mn) / (mx - mn), 0.0, 1.0)


def normalize_symmetric(x: ArrayLike, *, eps: float = 1e-9) -> np.ndarray:
    """Normalize an array to [-1, +1] by dividing by max absolute value.

    If all values are ~0, falls back to all zeros.
    """
    arr = to_np(x, dtype=float)
    if arr.size == 0:
        return arr

    with np.errstate(all="ignore"):
        max_abs = np.nanmax(np.abs(arr))

    if not np.isfinite(max_abs) or max_abs < eps:
        return np.zeros_like(arr)

    return np.clip(arr / max_abs, -1.0, 1.0)


def gradient_norm(x: ArrayLike, *, eps: float = 1e-9) -> np.ndarray:
    """Normalized gradient (slope) of a series.

    Computes np.gradient(x) and then applies normalize_symmetric.
    Useful for MACD_slope, KC_slope, etc.
    """
    arr = to_np(x, dtype=float)
    if arr.size == 0:
        return arr

    grad = np.gradient(arr)
    return normalize_symmetric(grad, eps=eps)


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------
__all__ = [
    "to_np",
    "sma",
    "ema",
    "wilder_ema",
    "true_range",
    "atr_wilder",
    "normalize_0_1",
    "normalize_symmetric",
    "gradient_norm",
]
