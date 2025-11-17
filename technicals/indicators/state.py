#!/usr/bin/env python3
# ============================================================
# queen/technicals/indicators/state.py — v1.0 (Bible v10.5 State Layer)
# ------------------------------------------------------------
# State features for Bible v10.5:
#   • Volume Delta (accumulation vs distribution)
#   • RSI Density (time spent above regime threshold)
#   • Liquidity Stability Score (LQS)
#   • Base_3w (structural base > ~3 weeks)
#   • Pattern Credibility hook (0–100 per pattern)
#
# This module is intentionally side-effect free and Polars/NumPy only.
# Fusion / tactical layers can:
#   1) call attach_state_features(df, context, patterns=[...])
#   2) then consume:
#        vol_delta, rsi_density, liquidity_stability,
#        base_3w, <pattern>_cred
# ============================================================

from __future__ import annotations

from typing import Iterable, List, Optional

import numpy as _np
import polars as pl

from queen.helpers.logger import log
from queen.settings import patterns as _PAT
from queen.settings import timeframes as TF
from queen.settings.timeframes import context_to_token

__all__ = [
    "volume_delta",
    "rsi_density",
    "liquidity_stability_score",
    "base_3w_flag",
    "pattern_credibility",
    "attach_state_features",
]

_EPS = 1e-9


# ------------------------------------------------------------
# 🧩 Small helpers
# ------------------------------------------------------------

def _ensure_series(df: pl.DataFrame, col: str, dtype=pl.Float64) -> Optional[pl.Series]:
    if col not in df.columns:
        return None
    s = df[col]
    if dtype is not None and s.dtype != dtype:
        try:
            s = s.cast(dtype)
        except Exception:
            return None
    return s


def _pattern_bias(name: str) -> str:
    """Return 'bullish' | 'bearish' | 'neutral' from settings.patterns."""
    nm = (name or "").strip().lower()
    cfg = _PAT.JAPANESE.get(nm) or _PAT.CUMULATIVE.get(nm) or {}
    return str(cfg.get("bias", "neutral")).lower()


# ------------------------------------------------------------
# 1️⃣ Volume Delta — accumulation vs distribution
# ------------------------------------------------------------
def volume_delta(
    df: pl.DataFrame,
    window: int = 20,
    volume_col: str = "volume",
    name: str = "vol_delta",
) -> pl.Series:
    """Volume Delta: normalized deviation of volume from rolling mean in [-1, 1]."""
    n = df.height
    if n == 0:
        return pl.Series(name, [], dtype=pl.Float64)

    v = _ensure_series(df, volume_col, dtype=pl.Float64)
    if v is None:
        return pl.Series(name, [0.0] * n, dtype=pl.Float64)

    roll_mean = v.rolling_mean(window_size=window, min_periods=1).fill_null(0.0)
    raw = (v - roll_mean) / (roll_mean + _EPS)
    arr = raw.to_numpy()
    # Clip extreme spikes so outliers don’t dominate (3σ approx)
    arr = _np.clip(arr, -3.0, 3.0) / 3.0  # → [-1, 1]
    return pl.Series(name, arr)


# ------------------------------------------------------------
# 2️⃣ RSI Density — fraction of bars above threshold
# ------------------------------------------------------------
def rsi_density(
    df: pl.DataFrame,
    window: int = 20,
    level: float = 55.0,
    rsi_col: str = "rsi_14",
    name: str = "rsi_density",
) -> pl.Series:
    """RSI Density: rolling fraction of bars with RSI >= level (0..1)."""
    n = df.height
    if n == 0:
        return pl.Series(name, [], dtype=pl.Float64)

    rsi = _ensure_series(df, rsi_col, dtype=pl.Float64)
    if rsi is None:
        return pl.Series(name, [0.0] * n, dtype=pl.Float64)

    above = (rsi >= float(level)).cast(pl.Float64)
    dens = above.rolling_mean(window_size=window, min_periods=1).fill_null(0.0)
    return dens.rename(name)


# ------------------------------------------------------------
# 3️⃣ Liquidity Stability Score (LQS)
# ------------------------------------------------------------
def liquidity_stability_score(
    df: pl.DataFrame,
    window: int = 20,
    volume_col: str = "volume",
    name: str = "liquidity_stability",
) -> pl.Series:
    """LQS: 1 - (rolling std(volume) / rolling mean(volume)), clipped to [0, 1].

    High LQS → stable, reliable liquidity.
    Low LQS  → choppy, regime-changing volume.
    """
    n = df.height
    if n == 0:
        return pl.Series(name, [], dtype=pl.Float64)

    v = _ensure_series(df, volume_col, dtype=pl.Float64)
    if v is None:
        return pl.Series(name, [0.0] * n, dtype=pl.Float64)

    m = v.rolling_mean(window_size=window, min_periods=1)
    s = v.rolling_std(window_size=window, min_periods=1)

    m_arr = _np.where(m.to_numpy() <= 0.0, 1.0, m.to_numpy())
    s_arr = _np.nan_to_num(s.to_numpy(), nan=0.0)

    ratio = s_arr / (m_arr + _EPS)
    lqs = 1.0 - ratio
    lqs = _np.clip(lqs, 0.0, 1.0)

    return pl.Series(name, lqs)


# ------------------------------------------------------------
# 4️⃣ Base_3w — structural base > ~3 weeks
# ------------------------------------------------------------
def base_3w_flag(
    df: pl.DataFrame,
    timeframe_token: str,
    *,
    price_col: str = "close",
    min_weeks: int = 3,
    max_range_pct: float = 0.18,
    name: str = "base_3w",
) -> pl.Series:
    """Detect a 'base > 3 weeks' style consolidation using price range.

    Logic (approx Bible v10.5):
      • Window ≈ min_weeks * 7 trading days (converted via TF.bars_for_days).
      • Compute rolling max/min of close.
      • If (max - min) / mid <= max_range_pct → in-base.
      • This is a *structural flag*, not an entry signal by itself.
    """
    n = df.height
    if n == 0:
        return pl.Series(name, [], dtype=pl.Boolean)

    price = _ensure_series(df, price_col, dtype=pl.Float64)
    if price is None:
        return pl.Series(name, [False] * n, dtype=pl.Boolean)

    token = (timeframe_token or "").strip().lower()
    try:
        bars = TF.bars_for_days(token, days=7 * min_weeks)
    except Exception as e:
        log.warning(f"[STATE] base_3w_flag: bars_for_days failed for token={token}: {e}")
        bars = 60  # reasonable fallback

    if bars <= 1:
        bars = 2

    roll_max = price.rolling_max(window_size=bars, min_periods=bars)
    roll_min = price.rolling_min(window_size=bars, min_periods=bars)
    mid = (roll_max + roll_min) / 2.0

    max_arr = roll_max.to_numpy()
    min_arr = roll_min.to_numpy()
    mid_arr = _np.where(mid.to_numpy() <= 0.0, 1.0, mid.to_numpy())

    rng_pct = _np.abs(max_arr - min_arr) / (mid_arr + _EPS)
    in_base = rng_pct <= float(max_range_pct)
    # Early bars (no full window) → False
    in_base[_np.isnan(rng_pct)] = False

    return pl.Series(name, in_base.astype(bool))


# ------------------------------------------------------------
# 5️⃣ Pattern Credibility — 0..100 hook
# ------------------------------------------------------------
def pattern_credibility(
    df: pl.DataFrame,
    pattern_col: str,
    context: str,
    *,
    timeframe_token: str | None = None,
    rsi_col: str = "rsi_14",
    volume_col: str = "volume",
    cpr_mid_col: str = "cpr_mid",
    cpr_lo_col: str = "cpr_lo",
    cpr_hi_col: str = "cpr_hi",
    name: str | None = None,
) -> pl.Series:
    """Compute a 0–100 credibility score for a given pattern column.

    Inputs:
      • pattern_col: boolean column (e.g. 'hammer', 'shooting_star', 'bullish_engulfing')
      • context: settings context key (e.g. 'intraday_15m', 'daily')
      • timeframe_token: optional override (otherwise derived from context)

    Bible-ish scoring (compressed):
      • Start from the pattern itself (must be True).
      • Location vs CPR:
          - Bullish best near CPR/low band.
          - Bearish best near CPR/high band.
      • RSI regime:
          - Bullish: prefer 25–55
          - Bearish: prefer 45–80
      • Volume:
          - Prefer non-collapsing / mildly increasing vs rolling mean.
    """
    n = df.height
    if n == 0:
        return pl.Series(name or f"{pattern_col}_cred", [], dtype=pl.Float64)

    if pattern_col not in df.columns:
        return pl.Series(name or f"{pattern_col}_cred", [0.0] * n, dtype=pl.Float64)

    pat = df[pattern_col].fill_null(False).cast(pl.Boolean)
    mask = pat.to_numpy()

    rsi = _ensure_series(df, rsi_col, dtype=pl.Float64)
    vol = _ensure_series(df, volume_col, dtype=pl.Float64)
    cpr_mid = _ensure_series(df, cpr_mid_col, dtype=pl.Float64)
    cpr_lo = _ensure_series(df, cpr_lo_col, dtype=pl.Float64)
    cpr_hi = _ensure_series(df, cpr_hi_col, dtype=pl.Float64)
    close = _ensure_series(df, "close", dtype=pl.Float64)

    scores = _np.zeros(n, dtype=float)
    if not mask.any():
        return pl.Series(name or f"{pattern_col}_cred", scores)

    # --- Location vs CPR (0..1) ---
    loc_score = _np.full(n, 0.5, dtype=float)
    bias = _pattern_bias(pattern_col)
    if close is not None and cpr_mid is not None:
        c = close.to_numpy()
        mid = cpr_mid.to_numpy()
        lo = cpr_lo.to_numpy() if cpr_lo is not None else mid - _np.abs(mid) * 0.02
        hi = cpr_hi.to_numpy() if cpr_hi is not None else mid + _np.abs(mid) * 0.02

        # Avoid division by zero
        span = _np.maximum(_np.abs(hi - lo), 1e-6)
        pos = (c - lo) / span  # 0 at low band, 1 at high band
        pos = _np.clip(pos, 0.0, 1.0)

        if bias == "bullish":
            # best: near 0–0.4 (lower half), worst: > 0.8
            loc_score = 1.0 - _np.clip((pos - 0.2) / 0.4, -1.0, 1.0) ** 2
        elif bias == "bearish":
            # best: near 0.6–1.0 (upper half)
            loc_score = 1.0 - _np.clip((pos - 0.8) / 0.4, -1.0, 1.0) ** 2
        else:
            loc_score = 1.0 - _np.abs(pos - 0.5)  # prefer mid-CPR for neutral

        loc_score = _np.clip(loc_score, 0.0, 1.0)

    # --- RSI score (0..1) ---
    rsi_score = _np.full(n, 0.5, dtype=float)
    if rsi is not None:
        r = rsi.to_numpy()
        if bias == "bullish":
            # ideal band 25–55
            center, width = 40.0, 30.0
        elif bias == "bearish":
            # ideal band 45–80
            center, width = 62.5, 35.0
        else:
            center, width = 50.0, 50.0

        rsi_score = 1.0 - (_np.clip((r - center) / (width / 2.0), -1.5, 1.5) ** 2)
        rsi_score = _np.clip(rsi_score, 0.0, 1.0)

    # --- Volume score (0..1) ---
    vol_score = _np.full(n, 0.5, dtype=float)
    if vol is not None:
        v = vol.to_numpy()
        win = min(20, max(5, n // 10))
        # simple rolling mean via convolution
        kernel = _np.ones(win) / float(win)
        v_pad = _np.r_[v[0], v]
        ma = _np.convolve(v_pad, kernel, mode="same")[1:]
        ma = _np.where(ma <= 0.0, 1.0, ma)
        vd = (v - ma) / ma
        vd = _np.clip(vd, -2.0, 2.0)  # compress
        if bias == "bullish":
            vol_score = 0.5 + 0.25 * _np.tanh(vd)  # prefer >= 0, but not crazy
        elif bias == "bearish":
            vol_score = 0.5 + 0.25 * _np.tanh(-vd)  # prefer <= 0
        else:
            vol_score = 0.5 - 0.25 * _np.abs(_np.tanh(vd))  # prefer neutral
        vol_score = _np.clip(vol_score, 0.0, 1.0)

    # Combine with weights
    combined = 0.4 * loc_score + 0.3 * rsi_score + 0.3 * vol_score

    # Zero out where pattern is not present
    combined[~mask] = 0.0

    # Context-based light penalty for ultra-short TFs (more noise)
    tf = timeframe_token or context_to_token(context)
    tf = (tf or "").strip().lower()
    if tf in {"1m", "3m"}:
        combined *= 0.7
    elif tf == "5m":
        combined *= 0.85

    combined = _np.clip(combined, 0.0, 1.0)
    out_name = name or f"{pattern_col}_cred"
    return pl.Series(out_name, (combined * 100.0).astype(float))


# ------------------------------------------------------------
# 6️⃣ Public: attach_state_features
# ------------------------------------------------------------
def attach_state_features(
    df: pl.DataFrame,
    context: str = "intraday_15m",
    *,
    patterns: Optional[Iterable[str]] = None,
) -> pl.DataFrame:
    """Attach Bible state features + optional per-pattern credibility.

    Columns added (if possible):
      • vol_delta                (float, -1..1)
      • rsi_density              (float, 0..1)
      • liquidity_stability      (float, 0..1)
      • base_3w                  (bool)
      • <pattern>_cred           (float, 0..100) for each requested pattern
    """
    if not isinstance(df, pl.DataFrame) or df.is_empty():
        return df

    tf_token = context_to_token(context)
    out = df.clone()

    # ---- core state metrics ----
    try:
        vd = volume_delta(out)
        rd = rsi_density(out)
        lqs = liquidity_stability_score(out)
        base = base_3w_flag(out, timeframe_token=tf_token)
        out = out.with_columns([vd, rd, lqs, base])
    except Exception as e:
        log.warning(f"[STATE] attach_state_features: base metrics failed → {e}")

    # ---- pattern credibility (Bible core by default) ----
    if patterns is None:
        # Bible v10.5 core Japanese reversal set
        patterns = [
            "hammer",
            "shooting_star",
            "bullish_engulfing",
            "bearish_engulfing",
            "doji",
        ]

    for name in patterns:
        if name not in out.columns:
            # pattern not present as boolean yet; skip silently
            continue
        try:
            cred = pattern_credibility(
                out,
                pattern_col=name,
                context=context,
                timeframe_token=tf_token,
            )
            out = out.with_columns(cred)
        except Exception as e:
            log.warning(f"[STATE] pattern_credibility failed for '{name}' → {e}")

    return out

# ------------------------------------------------------------
# 🧪 Local Dev Diagnostic
# ------------------------------------------------------------
if __name__ == "__main__":
    # Simple smoke test with synthetic data
    n = 200
    ts = pl.int_range(0, n, eager=True)
    close = pl.Series("close", _np.linspace(100, 110, n) + _np.random.normal(0, 0.5, n))
    high = close + 0.5
    low = close - 0.5
    open_ = close.shift(1).fill_null(close[0])
    volume = pl.Series("volume", _np.random.lognormal(mean=10, sigma=0.3, size=n))
    rsi = pl.Series("rsi", _np.clip(_np.random.normal(50, 10, n), 0, 100))

    df0 = pl.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "rsi": rsi,
            # fake CPR bands for location test
            "cpr_mid": close,
            "cpr_lo": close * 0.99,
            "cpr_hi": close * 1.01,
            # fake pattern booleans
            "hammer": [False] * (n - 3) + [True, True, False],
            "bearish_engulfing": [False] * (n - 5) + [True, False, True, False, False],
        }
    )

    df_state = attach_state_features(df0, context="intraday_15m", patterns=["hammer", "bearish_engulfing"])
    print(df_state.tail(5))
